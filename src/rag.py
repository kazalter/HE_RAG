from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import chromadb
from openai import OpenAI

from . import settings


ROOT_DIR = settings.ROOT_DIR
DB_PATH = str(settings.CHROMA_PATH)
COLLECTION_NAME = settings.COLLECTION_NAME

LLM_MODEL = settings.DEFAULT_LLM_MODEL
AVAILABLE_LLM_MODELS = settings.AVAILABLE_LLM_MODELS

# 拒答提示语：检索不到足够相关的依据时返回，避免模型凭空编造。
INSUFFICIENT_EVIDENCE_MESSAGE = "资料中未检索到足够依据，无法回答该问题。请换个问法，或先上传相关资料。"


def best_distance(chunks):
    """返回命中片段里最小（最相关）的距离；没有命中时返回正无穷。"""
    distances = [chunk["distance"] for chunk in chunks if chunk.get("distance") is not None]
    return min(distances) if distances else float("inf")


def has_sufficient_evidence(chunks, threshold=None):
    """最佳命中距离不超过阈值时，认为检索到了足够依据。"""
    if threshold is None:
        threshold = settings.get_similarity_distance_threshold()
    return best_distance(chunks) <= threshold


def load_embedding_model():
    # 委托给进程级单例，使检索与上传建索引共用同一个模型实例（见 embedding.py）。
    from .embedding import get_embedding_model

    return get_embedding_model()


def load_retriever():
    print("Loading embedding model...")
    embedding_model = load_embedding_model()

    print("Loading Chroma vector database...")
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    print("Loading BM25 retriever...")
    from .bm25_retriever import get_bm25_retriever
    get_bm25_retriever()

    return embedding_model, collection


def retrieve_chunks(question, embedding_model, collection, top_k=3):
    import numpy as np
    from .bm25_retriever import get_bm25_retriever

    mode = settings.get_retrieval_mode()

    # 1. 向量检索 (Dense Search)
    def _dense_search(limit):
        query_embedding = embedding_model.encode(
            question,
            normalize_embeddings=True,
        ).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        chunks = []
        for document, metadata, distance in zip(docs, metadatas, distances):
            chunks.append(
                {
                    "chunk_id": metadata.get("chunk_id", "unknown"),
                    "document_id": metadata.get("document_id", ""),
                    "version_id": metadata.get("version_id", ""),
                    "source": metadata.get("source", ""),
                    "section_title": metadata.get("section_title", ""),
                    "char_count": metadata.get("char_count", 0),
                    "distance": float(distance),
                    "text": document,
                }
            )
        return chunks

    # 2. 文本检索 (BM25 Search)
    def _bm25_search(limit):
        bm25_retriever = get_bm25_retriever()
        bm25_results = bm25_retriever.retrieve(question, top_k=limit)

        if not bm25_results:
            return []

        # 补全平方 L2 距离，使其与阈值拒答逻辑兼容
        query_emb = embedding_model.encode(question, normalize_embeddings=True)
        texts = [c["text"] for c in bm25_results]
        embs = embedding_model.encode(texts, normalize_embeddings=True)

        chunks = []
        for c, emb in zip(bm25_results, embs):
            dist = float(np.sum((query_emb - emb) ** 2))
            chunks.append(
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "document_id": c.get("document_id", ""),
                    "version_id": c.get("version_id", ""),
                    "source": c.get("source", ""),
                    "section_title": c.get("section_title", ""),
                    "char_count": c.get("char_count", 0),
                    "distance": dist,
                    "text": c.get("text", ""),
                }
            )
        return chunks

    # 3. 按配置的检索模式分发
    if mode == "dense":
        return _dense_search(top_k)

    elif mode == "bm25":
        return _bm25_search(top_k)

    else:  # hybrid 混合检索
        # 适当扩大候选集（取 top_k * 3），提高 RRF 融合后的召回质量
        candidate_limit = max(top_k * 3, 10)
        dense_candidates = _dense_search(candidate_limit)
        bm25_candidates = _bm25_search(candidate_limit)

        # 互惠倒排融合 (RRF) 排序
        rrf_scores = {}  # chunk_id -> rrf_score
        chunk_map = {}   # chunk_id -> chunk dict

        for rank, chunk in enumerate(dense_candidates, start=1):
            cid = chunk["chunk_id"]
            chunk_map[cid] = chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (60.0 + rank)

        for rank, chunk in enumerate(bm25_candidates, start=1):
            cid = chunk["chunk_id"]
            if cid not in chunk_map:
                chunk_map[cid] = chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (60.0 + rank)

        # 按 RRF 分数倒序排序，截取前 top_k
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        final_chunk_ids = sorted_ids[:top_k]

        # 方案 B：对 BM25 检索中排名前 10 的强匹配片段进行向量距离微调补偿
        bm25_ranks = {c["chunk_id"]: rank for rank, c in enumerate(bm25_candidates, start=1)}
        final_chunks = []
        for cid in final_chunk_ids:
            chunk = chunk_map[cid]
            bm25_rank = bm25_ranks.get(cid)
            if bm25_rank is not None and bm25_rank <= 10:
                if bm25_rank == 1:
                    offset = 0.050
                elif bm25_rank <= 3:
                    offset = 0.030
                elif bm25_rank <= 6:
                    offset = 0.015
                else:
                    offset = 0.008
                orig_dist = chunk["distance"]
                chunk["distance"] = max(0.0, orig_dist - offset)
                import logging
                logging.getLogger("rag.retriever").info(
                    "Chunk %s (BM25 Rank %d) distance adjusted: %.4f -> %.4f (offset -%.3f)",
                    cid, bm25_rank, orig_dist, chunk["distance"], offset
                )
            final_chunks.append(chunk)

        return final_chunks


def build_context(chunks):
    context_parts = []

    for index, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Source {index}]\n"
            f"chunk_id: {chunk['chunk_id']}\n"
            f"section: {chunk['section_title']}\n"
            f"content:\n{chunk['text']}"
        )

    return "\n\n".join(context_parts)


def answer_with_deepseek(question, chunks, api_key=None, model=LLM_MODEL):
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    model = model or LLM_MODEL

    if model not in AVAILABLE_LLM_MODELS:
        allowed_models = ", ".join(AVAILABLE_LLM_MODELS)
        raise RuntimeError(f"不支持的模型：{model}。可用模型：{allowed_models}")

    if not api_key:
        raise RuntimeError("未配置 DeepSeek API Key。")

    client = OpenAI(
        api_key=api_key,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    context = build_context(chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful knowledge base QA assistant. Answer in Chinese. "
                "Only use the provided source chunks. If the sources do not contain "
                "the answer, say that the material does not mention it. Do not invent facts. "
                "Use plain text without Markdown formatting."
            ),
        },
        {
            "role": "user",
            "content": f"""
The following chunks were retrieved from the knowledge base:

{context}

User question:
{question}

Please answer based only on the chunks above. Do not include chunk_id values, source IDs, or source lists in the answer.
""",
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
    )

    return response.choices[0].message.content


def answer_with_deepseek_stream(question, chunks, api_key=None, model=LLM_MODEL):
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    model = model or LLM_MODEL

    if model not in AVAILABLE_LLM_MODELS:
        allowed_models = ", ".join(AVAILABLE_LLM_MODELS)
        raise RuntimeError(f"不支持的模型：{model}。可用模型：{allowed_models}")

    if not api_key:
        raise RuntimeError("未配置 DeepSeek API Key。")

    client = OpenAI(
        api_key=api_key,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    context = build_context(chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful knowledge base QA assistant. Answer in Chinese. "
                "Only use the provided source chunks. If the sources do not contain "
                "the answer, say that the material does not mention it. Do not invent facts. "
                "Use plain text without Markdown formatting."
            ),
        },
        {
            "role": "user",
            "content": f"""
The following chunks were retrieved from the knowledge base:

{context}

User question:
{question}

Please answer based only on the chunks above. Do not include chunk_id values, source IDs, or source lists in the answer.
""",
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )

    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def rewrite_query(question: str, history: list[dict[str, str]], api_key: str | None = None, model: str = LLM_MODEL) -> str:
    """若有对话历史，利用 LLM 进行指代消解和上下文补全，改写生成独立的检索 Question。"""
    if not history:
        return question

    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return question

    client = OpenAI(
        api_key=api_key,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    history_context = []
    for turn in history[-6:]:  # 最近 3 轮
        role = "用户" if turn.get("role") == "user" else "助手"
        content = turn.get("content", "")
        history_context.append(f"{role}: {content}")
    history_str = "\n".join(history_context)

    prompt = (
        "你是一个检索 Query 改写助手。给你一段对话历史和一个后续问题，"
        "你需要根据上下文，将后续问题改写为一个独立、完整的检索 Query（用于在知识库中进行信息检索，补齐代词和指代对象）。\n"
        "请只输出改写后的独立检索 Query 文本，不要有任何多余的解释、Markdown 格式或前缀说明。\n\n"
        f"对话历史：\n{history_str}\n\n"
        f"后续问题：\n{question}\n\n"
        "独立检索 Query："
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=0.1,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        rewritten = rewritten.strip('"`\'')
        if rewritten:
            # 记录日志或打印输出
            import logging
            logging.getLogger("rag.query").info("Query rewritten: '%s' -> '%s'", question, rewritten)
            return rewritten
    except Exception as e:
        import logging
        logging.getLogger("rag.query").warning("Query rewrite failed: %s, use original query", e)

    return question


def main():
    print("DeepSeek RAG QA system starting...")
    embedding_model, collection = load_retriever()

    print("Startup complete.")
    print(f"Default model: {LLM_MODEL}")
    print("Enter q to quit.")
    print("-" * 60)

    while True:
        question = input("Question: ").strip()

        if question.lower() in ["q", "quit", "exit"]:
            print("Exited.")
            break

        if not question:
            continue

        print("\nRetrieving relevant chunks...")
        chunks = retrieve_chunks(
            question=question,
            embedding_model=embedding_model,
            collection=collection,
            top_k=settings.get_top_k(),
        )

        print("Retrieved chunks:")
        for chunk in chunks:
            print(
                f"- {chunk['chunk_id']}, section: {chunk['section_title']}, "
                f"distance: {chunk['distance']:.4f}, chars: {chunk['char_count']}"
            )

        if not has_sufficient_evidence(chunks):
            print("\nAnswer:")
            print(INSUFFICIENT_EVIDENCE_MESSAGE)
            print("\n" + "=" * 60)
            continue

        print("\nGenerating answer with DeepSeek...\n")

        try:
            answer = answer_with_deepseek(question, chunks)
            print("Answer:")
            print(answer)
        except Exception as error:
            print("DeepSeek call failed:")
            print(error)

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

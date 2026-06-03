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

    return embedding_model, collection


def retrieve_chunks(question, embedding_model, collection, top_k=3):
    query_embedding = embedding_model.encode(
        question,
        normalize_embeddings=True,
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    chunks = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        chunks.append(
            {
                "chunk_id": metadata.get("chunk_id", "unknown"),
                "document_id": metadata.get("document_id", ""),
                "version_id": metadata.get("version_id", ""),
                "source": metadata.get("source", ""),
                "section_title": metadata.get("section_title", ""),
                "char_count": metadata.get("char_count", 0),
                "distance": distance,
                "text": document,
            }
        )

    return chunks


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

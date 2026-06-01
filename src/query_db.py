from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import chromadb
from sentence_transformers import SentenceTransformer


# 独立调试脚本（可直接 python src/query_db.py 运行），因此不走包内相对导入，
# 常量保持与 src/settings.py 一致即可。
APP_DIR = Path(__file__).resolve().parent
DB_PATH = str(APP_DIR.parent / "data" / "chroma")
COLLECTION_NAME = "thesis_chunks"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
LOCAL_MODEL_PATH = APP_DIR.parent / "models" / "bge-small-zh-v1.5"


def load_embedding_model():
    if LOCAL_MODEL_PATH.exists():
        return SentenceTransformer(str(LOCAL_MODEL_PATH))

    try:
        return SentenceTransformer(MODEL_NAME, local_files_only=True)
    except TypeError:
        return SentenceTransformer(MODEL_NAME)
    except Exception as error:
        raise RuntimeError(
            "本地没有找到 embedding 模型缓存，或缓存不可用。"
            "请先在网络正常时运行 build_vector_db.py 下载模型。"
        ) from error


def main():
    print("正在加载 embedding 模型...")
    model = load_embedding_model()

    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)

    print("向量库加载完成。")
    print("输入问题后，系统会返回最相关的 3 个文本块。")
    print("输入 q 退出。")
    print("-" * 60)

    while True:
        question = input("请输入问题：").strip()

        if question.lower() in ["q", "quit", "exit"]:
            print("已退出。")
            break

        if not question:
            continue

        query_embedding = model.encode(
            question,
            normalize_embeddings=True
        ).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        print("\n检索结果：")
        print("=" * 60)

        for i, (doc, metadata, distance) in enumerate(
            zip(documents, metadatas, distances),
            start=1
        ):
            print(f"\n结果 {i}")
            print(f"chunk_id：{metadata.get('chunk_id')}")
            print(f"所属章节：{metadata.get('section_title', '')}")
            print(f"字符数：{metadata.get('char_count')}")
            print(f"距离：{distance:.4f}")
            print("-" * 40)
            print(doc[:500])

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

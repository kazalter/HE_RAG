from __future__ import annotations

import pytest
from src.bm25_retriever import clean_and_tokenize, BM25Retriever
from src import settings, rag
import os


def test_clean_and_tokenize():
    text = "本系统，采用了什么 Web 开发框架？"
    tokens = clean_and_tokenize(text)
    assert "系统" in tokens
    assert "框架" in tokens
    assert "Web" in tokens
    # 标点符号应被清洗
    assert "，" not in tokens
    assert "？" not in tokens


def test_rrf_logic(monkeypatch):
    # Mock settings 为混合检索
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "hybrid")

    class DummyModel:
        def encode(self, texts, normalize_embeddings=True):
            import numpy as np
            if isinstance(texts, str):
                return np.zeros(384)
            return np.zeros((len(texts), 384))

    class DummyCollection:
        def query(self, *args, **kwargs):
            return {
                "documents": [["text a", "text b"]],
                "metadatas": [[
                    {"chunk_id": "chunk_a", "source": "a.txt", "section_title": "A"},
                    {"chunk_id": "chunk_b", "source": "b.txt", "section_title": "B"}
                ]],
                "distances": [[0.1, 0.2]]
            }

    # Mock get_bm25_retriever
    class DummyBM25Retriever:
        def retrieve(self, question, top_k):
            return [
                {
                    "chunk_id": "chunk_b",
                    "source": "b.txt",
                    "section_title": "B",
                    "char_count": 6,
                    "text": "text b"
                },
                {
                    "chunk_id": "chunk_c",
                    "source": "c.txt",
                    "section_title": "C",
                    "char_count": 6,
                    "text": "text c"
                }
            ]

    # 用 monkeypatch 注入 DummyBM25Retriever
    from src import bm25_retriever
    monkeypatch.setattr(bm25_retriever, "get_bm25_retriever", lambda: DummyBM25Retriever())

    chunks = rag.retrieve_chunks(
        question="test",
        embedding_model=DummyModel(),
        collection=DummyCollection(),
        top_k=3
    )

    assert len(chunks) == 3
    # 验证 RRF 排序：b 第一，其次 a，最后 c
    assert chunks[0]["chunk_id"] == "chunk_b"
    assert chunks[1]["chunk_id"] == "chunk_a"
    assert chunks[2]["chunk_id"] == "chunk_c"
    # 验证没有原始向量距离的 chunk_c 也计算了 L2 距离
    assert "distance" in chunks[2]
    assert chunks[2]["distance"] == 0.0


def test_bm25_compensation_logic(monkeypatch):
    # Mock settings 为混合检索
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "hybrid")

    class DummyModel:
        def encode(self, texts, normalize_embeddings=True):
            import numpy as np
            if isinstance(texts, str):
                return np.zeros(384)
            return np.zeros((len(texts), 384))

    class DummyCollection:
        def query(self, *args, **kwargs):
            return {
                "documents": [["text a", "text b"]],
                "metadatas": [[
                    {"chunk_id": "ver_test:chunk_a", "source": "a.txt", "section_title": "A"},
                    {"chunk_id": "ver_test:chunk_b", "source": "b.txt", "section_title": "B"}
                ]],
                "distances": [[0.864, 0.870]]
            }

    # Mock get_bm25_retriever
    class DummyBM25Retriever:
        def retrieve(self, question, top_k):
            # 返回包含了 ver_test:chunk_b 的强字面匹配，排名第 2 (Rank 2)
            return [
                {
                    "chunk_id": "ver_test:chunk_other",
                    "source": "other.txt",
                    "section_title": "Other",
                    "char_count": 5,
                    "text": "text other"
                },
                {
                    "chunk_id": "ver_test:chunk_b",
                    "source": "b.txt",
                    "section_title": "B",
                    "char_count": 6,
                    "text": "text b"
                }
            ]

    # 用 monkeypatch 注入 DummyBM25Retriever
    from src import bm25_retriever
    monkeypatch.setattr(bm25_retriever, "get_bm25_retriever", lambda: DummyBM25Retriever())

    chunks = rag.retrieve_chunks(
        question="test",
        embedding_model=DummyModel(),
        collection=DummyCollection(),
        top_k=2
    )

    # ver_test:chunk_b 原始 distance 是 0.870。
    # 因为它是 BM25 检索的 Rank 2，它的 offset 是 0.030。
    # 补偿后调整为：0.870 - 0.030 = 0.840。
    # 我们验证它的距离应该成功调整为 0.840！
    b_chunk = next(c for c in chunks if c["chunk_id"] == "ver_test:chunk_b")
    assert abs(b_chunk["distance"] - 0.840) < 1e-5


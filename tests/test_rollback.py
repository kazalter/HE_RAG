from __future__ import annotations

import pytest
from src import doc_index, settings
from pathlib import Path
import json


def test_rollback_document_not_found(monkeypatch):
    from src import doc_store
    monkeypatch.setattr(doc_store, "get_document", lambda *args: None)

    with pytest.raises(KeyError, match="Document not found"):
        doc_index.rollback_document_version("doc1", "ver1")


def test_rollback_version_invalid(monkeypatch):
    from src import doc_store
    monkeypatch.setattr(doc_store, "get_document", lambda *args: {"id": "doc1", "status": "active"})
    monkeypatch.setattr(doc_store, "get_version", lambda *args: None)

    with pytest.raises(ValueError, match="Version not found"):
        doc_index.rollback_document_version("doc1", "ver1")


def test_rollback_success(monkeypatch, tmp_path):
    from src import doc_store
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)

    # 模拟物理 JSON 文件
    chunks_dir = tmp_path / "data" / "chunks" / "doc1"
    chunks_dir.mkdir(parents=True)
    chunks_file = chunks_dir / "ver1.json"
    chunks_file.write_text(
        json.dumps(
            [{"text": "chunk text 1", "section_title": "Section 1", "char_count": 12}]
        ),
        encoding="utf-8",
    )

    db = {
        "doc": {"id": "doc1", "status": "active", "current_version_id": "ver_old"},
        "ver": {
            "id": "ver1",
            "document_id": "doc1",
            "status": "indexed",
            "original_filename": "test.txt",
            "chunks_path": "data/chunks/doc1/ver1.json",
            "text_path": "data/text/doc1/ver1.txt",
        },
    }

    monkeypatch.setattr(doc_store, "get_document", lambda id: db["doc"])
    monkeypatch.setattr(
        doc_store,
        "get_version",
        lambda id: db["ver"] if id == "ver1" else {"id": "ver_old", "document_id": "doc1"},
    )
    monkeypatch.setattr(doc_store, "get_chroma_ids_for_version", lambda id: ["old:chunk_001"])
    monkeypatch.setattr(doc_store, "delete_chunks_for_version", lambda id: None)
    monkeypatch.setattr(doc_store, "archive_version", lambda id: None)
    monkeypatch.setattr(doc_store, "insert_chunks", lambda chunks: None)
    monkeypatch.setattr(doc_store, "mark_version_indexed", lambda **kwargs: None)
    monkeypatch.setattr(doc_store, "set_current_version", lambda doc_id, ver_id: None)
    monkeypatch.setattr(doc_store, "log_event", lambda *args, **kwargs: None)

    collection_deleted = {"value": False}
    collection_added = {"value": False}

    class DummyCollection:
        def delete(self, ids):
            collection_deleted["value"] = True

        def add(self, ids, documents, metadatas, embeddings):
            collection_added["value"] = True
            assert ids == ["ver1:chunk_001"]
            assert documents == ["chunk text 1"]

    monkeypatch.setattr(doc_index, "collection", lambda: DummyCollection())
    monkeypatch.setattr(doc_index, "delete_chroma_ids", lambda ids: DummyCollection().delete(ids))

    class DummyModel:
        def encode(self, texts, normalize_embeddings=True):
            import numpy as np
            return np.zeros((len(texts), 384))

    from src import embedding
    monkeypatch.setattr(embedding, "get_embedding_model", lambda: DummyModel())

    res = doc_index.rollback_document_version("doc1", "ver1")

    assert res["document_id"] == "doc1"
    assert res["version_id"] == "ver1"
    assert res["chunk_count"] == 1
    assert collection_deleted["value"] is True
    assert collection_added["value"] is True

"""doc_store 单测：文档/版本的增删改，用临时 SQLite 库隔离。

doc_store 内部多数函数调用无参的 connect()，因此通过 monkeypatch
把 connect 重定向到临时库，既隔离测试又覆盖真实 SQL。
"""

import pytest

from src import doc_store


@pytest.fixture
def store(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    real_connect = doc_store.connect
    # 把所有无参 connect() 调用重定向到临时库
    monkeypatch.setattr(doc_store, "connect", lambda db_path=db_path: real_connect(db_path))
    doc_store.init_db(db_path)
    return doc_store


def _add_version(store, *, document_id="doc1", version_id="v1", filename="a.txt", sha256="sha-1"):
    store.create_version(
        version_id=version_id,
        document_id=document_id,
        original_filename=filename,
        stored_path=f"/store/{filename}",
        file_ext=".txt",
        file_size=123,
        sha256=sha256,
    )


def test_create_document_and_count(store):
    assert store.document_count() == 0

    store.create_document("doc1", "标题 A")

    assert store.document_count() == 1
    assert store.get_document("doc1")["title"] == "标题 A"


def test_version_index_lifecycle(store):
    store.create_document("doc1", "标题 A")
    _add_version(store)
    store.set_current_version("doc1", "v1")

    # 刚建版本是 pending
    assert store.get_version("v1")["status"] == "pending"

    docs = store.list_documents()
    assert len(docs) == 1
    assert docs[0]["original_filename"] == "a.txt"

    store.mark_version_indexed(
        version_id="v1",
        text_path="/t/a.txt",
        chunks_path="/c/a.json",
        chunk_count=5,
        embedding_model="bge-small-zh-v1.5",
        embedding_dim=512,
    )
    version = store.get_version("v1")
    assert version["status"] == "indexed"
    assert version["chunk_count"] == 5
    assert version["embedding_dim"] == 512


def test_mark_version_failed_records_error(store):
    store.create_document("doc1", "标题 A")
    _add_version(store)

    store.mark_version_failed("v1", "解析失败：文件损坏")

    version = store.get_version("v1")
    assert version["status"] == "failed"
    assert version["parse_error"] == "解析失败：文件损坏"


def test_get_version_by_sha256(store):
    store.create_document("doc1", "标题 A")
    _add_version(store, sha256="deadbeef")

    found = store.get_version_by_sha256("deadbeef")
    assert found is not None
    assert found["id"] == "v1"
    assert store.get_version_by_sha256("不存在的哈希") is None


def test_mark_document_deleted_hides_from_default_list(store):
    store.create_document("doc1", "标题 A")
    _add_version(store)
    store.set_current_version("doc1", "v1")
    assert len(store.list_documents()) == 1

    store.mark_document_deleted("doc1")

    assert len(store.list_documents()) == 0
    assert len(store.list_documents(include_deleted=True)) == 1
    assert store.get_version("v1")["status"] == "deleted"

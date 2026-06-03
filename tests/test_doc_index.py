"""doc_index 单测：上传入口的用户侧校验（类型 / 解码），中文友好报错。

只测不触发建库的纯校验逻辑，不加载 embedding 模型。
"""

import base64

import pytest

from src import doc_index


# --- 文件类型校验 ----------------------------------------------------------

@pytest.mark.parametrize("filename", ["a.docx", "b.PDF", "c.txt", "note.md"])
def test_validate_extension_accepts_supported(filename):
    assert doc_index.validate_extension(filename).startswith(".")


@pytest.mark.parametrize("filename", ["a.xlsx", "b.exe", "noext"])
def test_validate_extension_rejects_unsupported(filename):
    with pytest.raises(ValueError, match="不支持的文件类型"):
        doc_index.validate_extension(filename)


def test_create_document_rejects_bad_type_before_db_write(monkeypatch):
    # 不支持的类型应在建任何记录之前就被拒，避免留下孤儿 document
    called = {"create": False}
    monkeypatch.setattr(
        doc_index.document_store, "create_document",
        lambda *a, **k: called.__setitem__("create", True),
    )
    with pytest.raises(ValueError, match="不支持的文件类型"):
        doc_index.create_document_from_bytes(original_filename="x.zip", content=b"data")
    assert called["create"] is False


# --- base64 解码 -----------------------------------------------------------

def test_decode_base64_roundtrip():
    raw = "你好 RAG".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    assert doc_index.decode_base64_content(encoded) == raw


def test_decode_base64_strips_data_url_prefix():
    raw = b"hello"
    encoded = base64.b64encode(raw).decode("ascii")
    assert doc_index.decode_base64_content(f"data:application/octet-stream;base64,{encoded}") == raw


def test_decode_base64_invalid_raises_friendly():
    with pytest.raises(ValueError, match="解码失败"):
        doc_index.decode_base64_content("@@@not-valid-base64@@@")

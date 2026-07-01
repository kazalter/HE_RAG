"""API 测试：用 FastAPI TestClient，重点覆盖 /api/ask 的拒答路径。

不进入 lifespan（不用 `with TestClient`），因此不加载 embedding 模型；
检索与生成两个重活通过 monkeypatch 替换成可控桩。
"""

import json
import pytest
from fastapi.testclient import TestClient

from src import web


@pytest.fixture
def client():
    # 不用 with 上下文 → 不触发 lifespan → 不加载模型；state.ready 保持 False
    return TestClient(web.app)


@pytest.fixture
def ready_state():
    """把检索器标记为就绪（塞假对象），测完恢复，避免污染其它用例。"""
    web.state.embedding_model = object()
    web.state.collection = object()
    try:
        yield web.state
    finally:
        web.state.embedding_model = None
        web.state.collection = None


def _chunk(distance: float):
    return {
        "chunk_id": "chunk_001",
        "document_id": "doc1",
        "version_id": "v1",
        "source": "a.txt",
        "section_title": "第一章",
        "char_count": 100,
        "distance": distance,
        "text": "示例片段内容",
    }


def test_health_reports_calibrated_threshold(client, monkeypatch):
    monkeypatch.setattr(web.document_store, "list_documents", lambda: [])

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["ready"] is False  # 测试态未加载模型
    assert body["similarity_distance_threshold"] == 0.90
    assert body["document_count"] == 0


def test_list_documents(client, monkeypatch):
    monkeypatch.setattr(
        web.document_store, "list_documents", lambda: [{"id": "doc1", "title": "标题 A"}]
    )

    response = client.get("/api/documents")

    assert response.status_code == 200
    documents = response.json()["documents"]
    assert documents[0]["id"] == "doc1"


def test_document_detail_returns_versions_and_chunks(client, monkeypatch):
    monkeypatch.setattr(
        web.document_store, "get_document",
        lambda doc_id: {"id": doc_id, "status": "active", "current_version_id": "v1"},
    )
    monkeypatch.setattr(
        web.document_store, "list_versions",
        lambda doc_id: [{"id": "v1", "status": "indexed", "chunk_count": 2}],
    )
    monkeypatch.setattr(
        web.document_store, "list_chunks",
        lambda version_id: [{"chunk_index": 1, "section_title": "第一章", "text_preview": "片段"}],
    )

    response = client.get("/api/documents/doc1")

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["id"] == "doc1"
    assert body["versions"][0]["id"] == "v1"
    assert body["chunks"][0]["section_title"] == "第一章"


def test_document_detail_404_when_missing_or_deleted(client, monkeypatch):
    monkeypatch.setattr(web.document_store, "get_document", lambda doc_id: None)
    assert client.get("/api/documents/nope").status_code == 404

    monkeypatch.setattr(
        web.document_store, "get_document",
        lambda doc_id: {"id": doc_id, "status": "deleted", "current_version_id": "v1"},
    )
    assert client.get("/api/documents/doc1").status_code == 404


def test_ask_returns_503_when_retriever_not_ready(client):
    response = client.post("/api/ask", json={"question": "随便问问", "api_key": "k"})
    assert response.status_code == 503


def test_ask_refuses_when_evidence_insufficient(client, monkeypatch, ready_state):
    # 最佳命中距离 1.5 > 阈值 0.865 → 应拒答，且不调用 DeepSeek
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(1.5)])

    deepseek_called = {"value": False}

    def _must_not_call(**kwargs):
        deepseek_called["value"] = True
        return "不应被调用"

    monkeypatch.setattr(web, "answer_with_deepseek", _must_not_call)

    response = client.post("/api/ask", json={"question": "和资料无关的问题", "api_key": "k"})

    assert response.status_code == 200
    body = response.json()
    assert body["refused"] is True
    assert body["answer"] == web.INSUFFICIENT_EVIDENCE_MESSAGE
    assert deepseek_called["value"] is False  # 拒答路径不该触网


def test_ask_answers_when_evidence_sufficient(client, monkeypatch, ready_state):
    # 最佳命中距离 0.5 ≤ 阈值 → 正常生成
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(0.5)])
    monkeypatch.setattr(web, "answer_with_deepseek", lambda **kwargs: "这是基于资料的回答。")

    response = client.post("/api/ask", json={"question": "资料里讲了什么", "api_key": "k"})

    assert response.status_code == 200
    body = response.json()
    assert body["refused"] is False
    assert body["answer"] == "这是基于资料的回答。"
    assert body["chunks"][0]["relevance"] > 0  # 距离已转成相关度供前端展示


# --- §5.4 错误处理：用户侧友好提示 / 系统侧兜底 ---------------------------

def test_ask_missing_key_returns_friendly_chinese(client, monkeypatch, ready_state):
    # 请求未带 Key 且服务端也没存 Key → 友好中文提示，而非英文
    monkeypatch.setattr(web.app_config, "get_deepseek_api_key", lambda: "")

    response = client.post("/api/ask", json={"question": "问题", "api_key": ""})

    assert response.status_code == 400
    assert response.json()["detail"] == web.MISSING_API_KEY_MSG


def test_ask_config_error_maps_to_400(client, monkeypatch, ready_state):
    # answer_with_deepseek 抛 RuntimeError（我方前置校验）→ 400 且透传中文原因
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(0.5)])

    def _raise_config_error(**kwargs):
        raise RuntimeError("不支持的模型：gpt-x")

    monkeypatch.setattr(web, "answer_with_deepseek", _raise_config_error)

    response = client.post("/api/ask", json={"question": "问题", "api_key": "k"})

    assert response.status_code == 400
    assert "不支持的模型" in response.json()["detail"]


def test_ask_deepseek_failure_returns_502_fallback(client, monkeypatch, ready_state):
    # DeepSeek 网络/API 异常（非我方校验）→ 502 兜底文案，不外泄原始错误
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(0.5)])

    def _boom(**kwargs):
        raise ConnectionError("connection reset by peer")

    monkeypatch.setattr(web, "answer_with_deepseek", _boom)

    response = client.post("/api/ask", json={"question": "问题", "api_key": "k"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail == web.DEEPSEEK_FAILED_MSG
    assert "connection reset" not in detail  # 原始错误不应外泄给前端


def test_ask_streaming_success(client, monkeypatch, ready_state):
    # 模拟检索命中
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(0.5)])

    # 模拟流式生成
    def _dummy_stream(**kwargs):
        yield "答案第1字"
        yield "答案第2字"

    monkeypatch.setattr(web, "answer_with_deepseek_stream", _dummy_stream)

    response = client.post("/api/ask", json={"question": "问题", "api_key": "k", "stream": True})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # 解析流响应
    lines = [line for line in response.iter_lines()]
    non_empty_lines = [line for line in lines if line.strip()]

    # 第1条消息应带 chunks 且 refused=False
    assert non_empty_lines[0].startswith("data: ")
    data0 = json.loads(non_empty_lines[0][6:])
    assert "chunks" in data0
    assert data0["refused"] is False

    # 第2条和第3条消息是生成字
    data1 = json.loads(non_empty_lines[1][6:])
    assert data1["answer"] == "答案第1字"

    data2 = json.loads(non_empty_lines[2][6:])
    assert data2["answer"] == "答案第2字"

    # 最后一条是 [DONE]
    assert non_empty_lines[3] == "data: [DONE]"


def test_ask_streaming_refuses_when_insufficient(client, monkeypatch, ready_state):
    monkeypatch.setattr(web, "retrieve_chunks", lambda **kwargs: [_chunk(1.5)])

    stream_called = {"value": False}
    def _must_not_call(**kwargs):
        stream_called["value"] = True
        yield "不该产生"

    monkeypatch.setattr(web, "answer_with_deepseek_stream", _must_not_call)

    response = client.post("/api/ask", json={"question": "问题", "api_key": "k", "stream": True})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    lines = [line for line in response.iter_lines()]
    non_empty = [line for line in lines if line.strip()]

    # 消息 0 是 chunks 且 refused=True
    data0 = json.loads(non_empty[0][6:])
    assert data0["refused"] is True

    # 消息 1 是拒答提示
    data1 = json.loads(non_empty[1][6:])
    assert data1["answer"] == web.INSUFFICIENT_EVIDENCE_MESSAGE

    # 消息 2 是 DONE
    assert non_empty[2] == "data: [DONE]"
    assert stream_called["value"] is False

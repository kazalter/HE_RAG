from __future__ import annotations

import pytest
from src import rag


def test_rewrite_query_empty_history_returns_original():
    # 历史为空直接返回
    assert rag.rewrite_query("我的问题", []) == "我的问题"


def test_rewrite_query_no_api_key(monkeypatch):
    # 没有 API Key 降级返回原问题
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert rag.rewrite_query("我的问题", [{"role": "user", "content": "历史"}], api_key="") == "我的问题"


def test_rewrite_query_success(monkeypatch):
    called = {"value": False}

    class DummyMessage:
        def __init__(self, content):
            self.content = content

    class DummyChoice:
        def __init__(self, content):
            self.message = DummyMessage(content)

    class DummyResponse:
        def __init__(self, content):
            self.choices = [DummyChoice(content)]

    class DummyCompletions:
        def create(self, *args, **kwargs):
            called["value"] = True
            prompt = kwargs["messages"][0]["content"]
            assert "历史提问" in prompt
            assert "后续问题" in prompt
            return DummyResponse("改写后的检索词")

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletions()

    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = DummyChat()

    monkeypatch.setattr(rag, "OpenAI", DummyOpenAI)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy_key")

    result = rag.rewrite_query(
        question="后续问题",
        history=[{"role": "user", "content": "历史提问"}],
        api_key="k"
    )

    assert called["value"] is True
    assert result == "改写后的检索词"

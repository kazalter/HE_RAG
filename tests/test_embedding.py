"""embedding 单例的行为测试：只加载一次、全进程复用、reset 可清空。

不加载真实模型——把 _load 换成计数桩，验证缓存语义即可。
"""

from src import embedding, rag


def test_get_embedding_model_loads_once(monkeypatch):
    embedding.reset()
    calls = {"count": 0}
    sentinel = object()

    def fake_load():
        calls["count"] += 1
        return sentinel

    monkeypatch.setattr(embedding, "_load", fake_load)

    first = embedding.get_embedding_model()
    second = embedding.get_embedding_model()

    assert first is sentinel
    assert second is first          # 复用同一实例
    assert calls["count"] == 1       # 只加载一次
    embedding.reset()


def test_reset_forces_reload(monkeypatch):
    embedding.reset()
    calls = {"count": 0}

    def fake_load():
        calls["count"] += 1
        return object()

    monkeypatch.setattr(embedding, "_load", fake_load)

    embedding.get_embedding_model()
    embedding.reset()
    embedding.get_embedding_model()

    assert calls["count"] == 2
    embedding.reset()


def test_rag_load_embedding_model_delegates_to_singleton(monkeypatch):
    """rag.load_embedding_model 应返回同一个共享单例，确保检索与索引共用一份模型。"""
    embedding.reset()
    sentinel = object()
    monkeypatch.setattr(embedding, "_load", lambda: sentinel)

    assert rag.load_embedding_model() is sentinel
    assert rag.load_embedding_model() is embedding.get_embedding_model()
    embedding.reset()

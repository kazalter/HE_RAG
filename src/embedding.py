"""进程级共享的 embedding 模型单例。

此前 rag.py / chunker.py / doc_index.py 各自 load 一份 SentenceTransformer：
Web 端启动检索已加载一份，上传/替换走 doc_index 建索引时又加载第二份，
白白多占一份显存/内存、多花一次加载时间。这里用线程安全的懒加载单例，
让同一进程内的检索与索引共用同一个模型实例。

加载顺序与原 rag.load_embedding_model 一致：
本地 models/ 目录优先 → 离线缓存 → 联网下载（仅在前两者都没有时）。
"""

from __future__ import annotations

import os
from threading import Lock
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from . import settings


_model: Any = None
_lock = Lock()


def _load() -> Any:
    from sentence_transformers import SentenceTransformer

    local_path = settings.LOCAL_EMBEDDING_MODEL_PATH
    if local_path.exists():
        return SentenceTransformer(str(local_path))

    try:
        return SentenceTransformer(settings.EMBEDDING_MODEL_NAME, local_files_only=True)
    except TypeError:
        return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    except Exception as error:
        raise RuntimeError(
            "没有找到可用的本地 embedding 模型缓存。请把 BAAI/bge-small-zh-v1.5 "
            "放到 models/bge-small-zh-v1.5，或在联网环境下先下载模型。"
        ) from error


def get_embedding_model() -> Any:
    """返回进程级共享的 embedding 模型；首次调用加载，之后复用同一实例。"""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = _load()
    return _model


def reset() -> None:
    """清空缓存的模型实例（主要供测试使用）。"""
    global _model
    with _lock:
        _model = None

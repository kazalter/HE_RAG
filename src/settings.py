"""集中配置：路径、向量库、embedding 模型、LLM、检索参数、相似度阈值。

此前这些常量在 rag.py / chunker.py / doc_index.py / query_db.py / web.py 中
各自重复定义。现在统一到这里，改路径或换模型只改这一处。

可被环境变量或 .rag_config.json 覆盖的运行期参数：
- top_k：默认检索条数
- similarity_distance_threshold：拒答阈值（最佳命中距离超过它就拒答）
- default_llm_model：默认生成模型
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .config import load_config


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
# 兼容 PyInstaller 打包后的 _MEIPASS 临时目录。
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))

DATA_DIR = ROOT_DIR / "data"
MATERIAL_DIR = DATA_DIR / "material"
TEXT_DIR = DATA_DIR / "text"
CHUNKS_DIR = DATA_DIR / "chunks"
CHROMA_PATH = DATA_DIR / "chroma"
APP_DB_PATH = DATA_DIR / "app.db"
MODELS_DIR = ROOT_DIR / "models"

# ---------------------------------------------------------------------------
# 向量库
# ---------------------------------------------------------------------------
COLLECTION_NAME = "thesis_chunks"

# ---------------------------------------------------------------------------
# Embedding 模型
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
LOCAL_EMBEDDING_MODEL_PATH = MODELS_DIR / "bge-small-zh-v1.5"

# ---------------------------------------------------------------------------
# LLM（DeepSeek 走 OpenAI 兼容协议）
# ---------------------------------------------------------------------------
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# deepseek-v4-flash / deepseek-v4-pro 是 api.deepseek.com 当前官方 V4 模型 ID。
# deepseek-chat / deepseek-reasoner 是遗留别名（将于 2026-07-24 弃用，映射到
# v4-flash 的非思考/思考模式），故不再作为默认。
AVAILABLE_LLM_MODELS: dict[str, str] = {
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
}
DEFAULT_LLM_MODEL = "deepseek-v4-flash"

# ---------------------------------------------------------------------------
# 检索 / 拒答参数（可被 env 或 .rag_config.json 覆盖）
# ---------------------------------------------------------------------------
DEFAULT_TOP_K = 3
DEFAULT_RETRIEVAL_MODE = "hybrid"  # 可选：dense (仅向量), bm25 (仅关键字), hybrid (混合检索)

# 基于归一化向量，Chroma 默认平方 L2 距离与余弦单调相关，范围约 [0, 2]。
# 最佳命中距离超过该阈值 → 判定“资料中没有足够依据”，拒答而非强行生成。
# 该默认值由评测集标定（见 PLAN §3.2 与 eval/report.md）：当前样例资料上，
# 可回答问题的最佳命中距离 ≤0.862，无关问题 ≥0.869，故取 0.865 落在两者之间。
# 换资料后请重跑 eval/run_eval 重新标定。
DEFAULT_SIMILARITY_DISTANCE_THRESHOLD = 0.90

SUPPORTED_EXTENSIONS = {".docx", ".txt", ".md", ".pdf"}


# ---------------------------------------------------------------------------
# 运行期可覆盖项的取值（env 优先 > 配置文件 > 默认值）
# ---------------------------------------------------------------------------
def _config_value(key: str) -> Any:
    return load_config().get(key)


def _env_or_config_float(env_name: str, config_key: str, default: float) -> float:
    raw = os.environ.get(env_name)
    if raw is None:
        raw = _config_value(config_key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_or_config_int(env_name: str, config_key: str, default: int) -> int:
    raw = os.environ.get(env_name)
    if raw is None:
        raw = _config_value(config_key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def get_top_k() -> int:
    return _env_or_config_int("RAG_TOP_K", "top_k", DEFAULT_TOP_K)


def get_similarity_distance_threshold() -> float:
    return _env_or_config_float(
        "RAG_SIMILARITY_DISTANCE_THRESHOLD",
        "similarity_distance_threshold",
        DEFAULT_SIMILARITY_DISTANCE_THRESHOLD,
    )


def get_default_llm_model() -> str:
    raw = os.environ.get("RAG_DEFAULT_LLM_MODEL") or _config_value("default_llm_model")
    model = str(raw).strip() if raw else ""
    return model if model in AVAILABLE_LLM_MODELS else DEFAULT_LLM_MODEL


def get_retrieval_mode() -> str:
    raw = os.environ.get("RAG_RETRIEVAL_MODE") or _config_value("retrieval_mode")
    mode = str(raw).strip().lower() if raw else ""
    return mode if mode in {"dense", "bm25", "hybrid"} else DEFAULT_RETRIEVAL_MODE


def distance_to_relevance(distance: float) -> float:
    """把平方 L2 距离（约 [0, 2]）映射为 [0, 1] 的相关度，仅用于前端直观展示。"""
    relevance = 1.0 - (float(distance) / 2.0)
    if relevance < 0.0:
        return 0.0
    if relevance > 1.0:
        return 1.0
    return relevance

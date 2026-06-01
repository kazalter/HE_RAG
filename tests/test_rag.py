"""rag 模块单测：距离计算、阈值拒答判定、生成端入参校验。

不加载 embedding 模型、不联网——只测纯逻辑与异常路径。
"""

import math

import pytest

from src import rag, settings


# --- best_distance ---------------------------------------------------------

def test_best_distance_empty_returns_inf():
    assert rag.best_distance([]) == math.inf


def test_best_distance_returns_minimum():
    chunks = [{"distance": 0.9}, {"distance": 0.3}, {"distance": 0.7}]
    assert rag.best_distance(chunks) == 0.3


def test_best_distance_ignores_none():
    chunks = [{"distance": None}, {"distance": 0.5}]
    assert rag.best_distance(chunks) == 0.5


# --- has_sufficient_evidence ----------------------------------------------

@pytest.mark.parametrize(
    "distance, threshold, expected",
    [
        (0.5, 0.865, True),
        (0.865, 0.865, True),   # 边界相等：算有依据
        (0.9, 0.865, False),
        (1.5, 0.865, False),
    ],
)
def test_has_sufficient_evidence(distance, threshold, expected):
    assert rag.has_sufficient_evidence([{"distance": distance}], threshold=threshold) is expected


def test_has_sufficient_evidence_empty_chunks_refuses():
    # 没有任何命中（best_distance=inf）必须拒答
    assert rag.has_sufficient_evidence([], threshold=0.865) is False


# --- 阈值标定回归（核心）---------------------------------------------------
# eval 集标定的边界（见 PLAN §3.2 / eval/report.md）：
#   可回答问题最佳命中距离 ≤ 0.862；无关问题最佳命中距离 ≥ 0.869。
# 默认阈值必须落在两者之间，否则要么误拒真问题、要么放过无关问题。
# 这条测试把这个隐性标定约束固化下来——以后谁改坏阈值会立刻报警。
EVAL_ANSWERABLE_MAX_DISTANCE = 0.862
EVAL_IRRELEVANT_MIN_DISTANCE = 0.869


def test_default_threshold_separates_eval_distribution():
    threshold = settings.DEFAULT_SIMILARITY_DISTANCE_THRESHOLD

    assert EVAL_ANSWERABLE_MAX_DISTANCE <= threshold < EVAL_IRRELEVANT_MIN_DISTANCE, (
        f"默认阈值 {threshold} 未落在评测边界 "
        f"[{EVAL_ANSWERABLE_MAX_DISTANCE}, {EVAL_IRRELEVANT_MIN_DISTANCE}) 之间"
    )

    # 最难的可回答问题：必须能答
    assert rag.has_sufficient_evidence(
        [{"distance": EVAL_ANSWERABLE_MAX_DISTANCE}], threshold=threshold
    ) is True, "最难的可回答问题被误拒，阈值过低"

    # 最接近的无关问题：必须拒答
    assert rag.has_sufficient_evidence(
        [{"distance": EVAL_IRRELEVANT_MIN_DISTANCE}], threshold=threshold
    ) is False, "最接近的无关问题未被拒答，阈值过高"


# --- answer_with_deepseek 入参校验（不触网）-------------------------------

def test_answer_rejects_unknown_model():
    with pytest.raises(RuntimeError, match="Unsupported model"):
        rag.answer_with_deepseek("问题", [], api_key="dummy", model="gpt-不存在")


def test_answer_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        rag.answer_with_deepseek("问题", [], api_key="", model="deepseek-v4-flash")

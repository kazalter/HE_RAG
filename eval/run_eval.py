"""RAG 评测脚本。

一键评测当前向量库的检索质量（hit@1 / hit@3 / 章节命中率 / 拒答准确率），
并可选地评测生成质量（回答关键词覆盖率、LLM-as-judge 忠实度）。

用法（在项目根目录）：
  python -m eval.run_eval                      # 用 settings 默认 top_k 跑检索评测
  python -m eval.run_eval --top-k 5            # 指定 top_k
  python -m eval.run_eval --compare-top-k 1,3,5,8   # top_k 对比实验（论文 §3.4）
  python -m eval.run_eval --generate           # 额外评测生成（需 DeepSeek Key）
  python -m eval.run_eval --generate --judge   # 再加 LLM-as-judge 忠实度打分

结果写入 eval/report.md。
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from src import settings
from src.rag import (
    answer_with_deepseek,
    best_distance,
    load_retriever,
    retrieve_chunks,
)
from src.config import get_deepseek_api_key


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = EVAL_DIR / "questions.json"
DEFAULT_REPORT = EVAL_DIR / "report.md"

ANSWERABLE_TYPES = {"fact", "cross"}


def load_questions(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions", data) if isinstance(data, dict) else data
    if not questions:
        raise SystemExit(f"题库为空：{path}")
    return questions


def chunk_haystack(chunk: dict[str, Any]) -> str:
    return f"{chunk.get('section_title', '')}\n{chunk.get('text', '')}".lower()


def first_hit_rank(chunks: list[dict[str, Any]], keywords: list[str]) -> int | None:
    """返回首个命中任一关键词的片段排名（1 起）；无关键词或全不命中返回 None。"""
    if not keywords:
        return None
    lowered = [keyword.lower() for keyword in keywords]
    for rank, chunk in enumerate(chunks, start=1):
        haystack = chunk_haystack(chunk)
        if any(keyword in haystack for keyword in lowered):
            return rank
    return None


def section_hit(chunks: list[dict[str, Any]], keywords: list[str]) -> bool:
    if not keywords:
        return False
    lowered = [keyword.lower() for keyword in keywords]
    for chunk in chunks:
        title = str(chunk.get("section_title", "")).lower()
        if any(keyword in title for keyword in lowered):
            return True
    return False


def keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    text = (answer or "").lower()
    present = sum(1 for keyword in keywords if keyword.lower() in text)
    return present / len(keywords)


def judge_faithfulness(question: str, answer: str, chunks: list[dict[str, Any]], api_key: str, model: str) -> int | None:
    """用 LLM 给回答相对检索片段的忠实度打 1-5 分。失败返回 None。"""
    from openai import OpenAI

    context = "\n\n".join(
        f"[片段{index}] {chunk.get('text', '')}" for index, chunk in enumerate(chunks, start=1)
    )
    client = OpenAI(api_key=api_key, base_url=settings.DEEPSEEK_BASE_URL)
    prompt = (
        "你是严格的评分员。给定检索片段、用户问题和模型回答，"
        "评估回答是否完全基于片段（忠实度 faithfulness），不得引入片段之外的信息。"
        "只输出一个 1 到 5 的整数：5=完全忠于片段，1=大量臆造。\n\n"
        f"检索片段：\n{context}\n\n问题：{question}\n\n回答：{answer}\n\n忠实度分数（仅一个数字）："
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        raw = (response.choices[0].message.content or "").strip()
        for token in raw:
            if token.isdigit():
                score = int(token)
                return min(max(score, 1), 5)
    except Exception:
        return None
    return None


def evaluate(
    questions: list[dict[str, Any]],
    embedding_model: Any,
    collection: Any,
    top_k: int,
    threshold: float,
    *,
    generate: bool = False,
    judge: bool = False,
    api_key: str = "",
    model: str = settings.DEFAULT_LLM_MODEL,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for item in questions:
        chunks = retrieve_chunks(
            question=item["question"],
            embedding_model=embedding_model,
            collection=collection,
            top_k=top_k,
        )
        best = best_distance(chunks)
        refused = best > threshold
        rank = first_hit_rank(chunks, item.get("expected_sections", []))

        record: dict[str, Any] = {
            "id": item.get("id", ""),
            "type": item.get("type", ""),
            "question": item["question"],
            "best_distance": best,
            "refused": refused,
            "hit_rank": rank,
            "hit@1": rank == 1,
            "hit@3": rank is not None and rank <= 3,
            "section_hit": section_hit(chunks, item.get("expected_sections", [])),
        }

        if generate and not refused and item.get("type") in ANSWERABLE_TYPES and api_key:
            try:
                answer = answer_with_deepseek(item["question"], chunks, api_key=api_key, model=model)
            except Exception as error:
                answer = f"[生成失败] {error}"
            record["answer"] = answer
            record["keyword_coverage"] = keyword_coverage(answer, item.get("expected_keywords", []))
            if judge:
                record["faithfulness"] = judge_faithfulness(
                    item["question"], answer, chunks, api_key, model
                )

        records.append(record)

    import os
    return summarize(records, top_k, threshold, mode=os.environ.get("RAG_RETRIEVAL_MODE", "hybrid"))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(records: list[dict[str, Any]], top_k: int, threshold: float, mode: str = "hybrid") -> dict[str, Any]:
    answerable = [r for r in records if r["type"] in ANSWERABLE_TYPES]
    irrelevant = [r for r in records if r["type"] == "irrelevant"]

    answerable_distances = [r["best_distance"] for r in answerable]
    irrelevant_distances = [r["best_distance"] for r in irrelevant]

    correct_refusals = sum(1 for r in irrelevant if r["refused"])
    correct_answers = sum(1 for r in answerable if not r["refused"])
    total = len(records)

    coverage_values = [r["keyword_coverage"] for r in records if "keyword_coverage" in r]
    faithfulness_values = [r["faithfulness"] for r in records if r.get("faithfulness") is not None]

    return {
        "top_k": top_k,
        "threshold": threshold,
        "mode": mode,
        "counts": {
            "total": total,
            "answerable": len(answerable),
            "irrelevant": len(irrelevant),
        },
        "hit@1": _mean([1.0 if r["hit@1"] else 0.0 for r in answerable]),
        "hit@3": _mean([1.0 if r["hit@3"] else 0.0 for r in answerable]),
        "section_hit_rate": _mean([1.0 if r["section_hit"] else 0.0 for r in answerable]),
        "irrelevant_refusal_rate": correct_refusals / len(irrelevant) if irrelevant else 0.0,
        "answerable_false_refusal_rate": _mean([1.0 if r["refused"] else 0.0 for r in answerable]),
        "refusal_accuracy": (correct_refusals + correct_answers) / total if total else 0.0,
        "answerable_distance": _distance_stats(answerable_distances),
        "irrelevant_distance": _distance_stats(irrelevant_distances),
        "keyword_coverage": _mean(coverage_values) if coverage_values else None,
        "faithfulness": _mean(faithfulness_values) if faithfulness_values else None,
        "records": records,
    }


def _distance_stats(values: list[float]) -> dict[str, float] | None:
    finite = [v for v in values if v != float("inf")]
    if not finite:
        return None
    return {
        "min": min(finite),
        "median": statistics.median(finite),
        "max": max(finite),
    }


def _pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "-"


def render_report(summaries: list[dict[str, Any]], with_detail: bool) -> str:
    lines: list[str] = []
    lines.append("# RAG 评测报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    primary = summaries[0]
    counts = primary["counts"]
    lines.append(
        f"题量：{counts['total']}（可回答 {counts['answerable']} / 无关 {counts['irrelevant']}）"
    )
    lines.append("")

    lines.append("## 检索质量对比")
    lines.append("")
    lines.append("| 检索模式 | top_k | 阈值 | hit@1 | hit@3 | 章节命中率 | 无关拒答率 | 误拒率 | 拒答准确率 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for summary in summaries:
        mode_label = {
            "dense": "仅向量 (dense)",
            "bm25": "仅文本 (bm25)",
            "hybrid": "混合检索 (hybrid)"
        }.get(summary.get("mode", "hybrid"), summary.get("mode", "hybrid"))
        lines.append(
            f"| {mode_label} | {summary['top_k']} | {summary['threshold']:.3f} | "
            f"{_pct(summary['hit@1'])} | {_pct(summary['hit@3'])} | "
            f"{_pct(summary['section_hit_rate'])} | {_pct(summary['irrelevant_refusal_rate'])} | "
            f"{_pct(summary['answerable_false_refusal_rate'])} | {_pct(summary['refusal_accuracy'])} |"
        )
    lines.append("")

    lines.append("## 最佳命中距离分布（用于标定拒答阈值，PLAN §3.2）")
    lines.append("")
    lines.append("| 配置 | 可回答(min/中位/max) | 无关(min/中位/max) |")
    lines.append("|---|---|---|")
    for summary in summaries:
        mode_label = {
            "dense": "dense",
            "bm25": "bm25",
            "hybrid": "hybrid"
        }.get(summary.get("mode", "hybrid"), summary.get("mode", "hybrid"))
        ans = summary["answerable_distance"]
        irr = summary["irrelevant_distance"]
        ans_text = f"{ans['min']:.3f} / {ans['median']:.3f} / {ans['max']:.3f}" if ans else "-"
        irr_text = f"{irr['min']:.3f} / {irr['median']:.3f} / {irr['max']:.3f}" if irr else "-"
        lines.append(f"| {mode_label} (top_k={summary['top_k']}) | {ans_text} | {irr_text} |")
    lines.append("")
    lines.append(
        "> 标定建议：理想阈值应落在“可回答问题最佳距离的 max”与“无关问题最佳距离的 min”之间。"
        "若两者重叠，说明仅靠距离阈值难以完美区分，可在论文中作为局限讨论。"
    )
    lines.append("")

    if primary.get("keyword_coverage") is not None or primary.get("faithfulness") is not None:
        lines.append("## 生成质量")
        lines.append("")
        lines.append("| 配置 | 回答关键词覆盖率 | 忠实度(1-5) |")
        lines.append("|---|---|---|")
        for summary in summaries:
            coverage = _pct(summary["keyword_coverage"]) if summary["keyword_coverage"] is not None else "-"
            faith = f"{summary['faithfulness']:.2f}" if summary["faithfulness"] is not None else "-"
            lines.append(f"| top_k={summary['top_k']} | {coverage} | {faith} |")
        lines.append("")

    if with_detail:
        lines.append("## 逐题明细（首个配置）")
        lines.append("")
        lines.append("| id | 类型 | 命中排名 | 拒答 | 最佳距离 | 问题 |")
        lines.append("|---|---|---|---|---|---|")
        for record in primary["records"]:
            rank = record["hit_rank"] if record["hit_rank"] is not None else "-"
            refused = "是" if record["refused"] else "否"
            lines.append(
                f"| {record['id']} | {record['type']} | {rank} | {refused} | "
                f"{record['best_distance']:.3f} | {record['question']} |"
            )
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 检索/生成评测")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-k", type=int, default=None, help="单次评测的 top_k；默认取 settings")
    parser.add_argument("--compare-top-k", type=str, default=None, help='逗号分隔的 top_k 列表，如 "1,3,5,8"')
    parser.add_argument("--compare-mode", action="store_true", help="对 dense, bm25, hybrid 检索模式进行对比")
    parser.add_argument("--threshold", type=float, default=None, help="拒答距离阈值；默认取 settings")
    parser.add_argument("--generate", action="store_true", help="评测生成质量（需 DeepSeek Key）")
    parser.add_argument("--judge", action="store_true", help="LLM-as-judge 忠实度打分（需配合 --generate）")
    parser.add_argument("--model", type=str, default=settings.DEFAULT_LLM_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    threshold = args.threshold if args.threshold is not None else settings.get_similarity_distance_threshold()

    import os

    if args.compare_mode:
        modes = ["dense", "bm25", "hybrid"]
    else:
        modes = [settings.get_retrieval_mode()]

    if args.compare_top_k:
        top_k_list = [int(value) for value in args.compare_top_k.split(",") if value.strip()]
    else:
        top_k_list = [args.top_k if args.top_k is not None else settings.get_top_k()]

    api_key = ""
    if args.generate:
        api_key = get_deepseek_api_key()
        if not api_key:
            raise SystemExit("--generate 需要 DeepSeek API Key（环境变量 DEEPSEEK_API_KEY 或 .rag_config.json）。")

    questions = load_questions(args.questions)
    print(f"加载 {len(questions)} 道题，模式配置：{modes}，top_k 配置：{top_k_list}，阈值：{threshold}")

    embedding_model, collection = load_retriever()

    orig_mode = os.environ.get("RAG_RETRIEVAL_MODE")
    summaries = []

    try:
        for mode in modes:
            os.environ["RAG_RETRIEVAL_MODE"] = mode
            for top_k in top_k_list:
                print(f"评测 模式={mode}, top_k={top_k} ...")
                summary = evaluate(
                    questions,
                    embedding_model,
                    collection,
                    top_k=top_k,
                    threshold=threshold,
                    generate=args.generate,
                    judge=args.judge,
                    api_key=api_key,
                    model=args.model,
                )
                summaries.append(summary)
                print(
                    f"  hit@1={_pct(summary['hit@1'])} hit@3={_pct(summary['hit@3'])} "
                    f"无关拒答率={_pct(summary['irrelevant_refusal_rate'])} "
                    f"拒答准确率={_pct(summary['refusal_accuracy'])}"
                )
    finally:
        if orig_mode is not None:
            os.environ["RAG_RETRIEVAL_MODE"] = orig_mode
        elif "RAG_RETRIEVAL_MODE" in os.environ:
            del os.environ["RAG_RETRIEVAL_MODE"]

    report = render_report(summaries, with_detail=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"报告已写入：{args.report}")


if __name__ == "__main__":
    main()

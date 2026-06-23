"""Production-loop helpers: review queue and evaluation sample capture.

These helpers turn persisted task runs into operational assets:
- review queue items for failed / blocked / high-risk runs;
- JSONL evaluation samples for later regression evaluation.

All outputs are local JSONL files under logs/ and are ignored by git.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_REVIEW_QUEUE_DIR = Path("logs") / "review"
DEFAULT_EVAL_SAMPLE_DIR = Path("logs") / "eval_samples"
REVIEW_QUEUE_FILE_NAME = "review_queue.jsonl"
EVAL_SAMPLE_FILE_NAME = "agent_samples.jsonl"
REVIEW_EVENT_STAGES = {"tool_blocked", "tool_failed", "task_failed", "task_run_persist_failed"}
VALID_REVIEW_STATUSES = {"open", "reviewed", "fixed", "ignored"}


def get_review_queue_dir() -> Path:
    return Path(os.getenv("AGENT_REVIEW_QUEUE_DIR", str(DEFAULT_REVIEW_QUEUE_DIR)))


def get_eval_sample_dir() -> Path:
    return Path(os.getenv("AGENT_EVAL_SAMPLE_DIR", str(DEFAULT_EVAL_SAMPLE_DIR)))


def _json_dump_line(record: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(record), ensure_ascii=False) + "\n")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def review_reasons_for_task(record: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record.get("status") and record.get("status") != "completed":
        reasons.append(f"任务状态异常：{record.get('status')}")
    for event in record.get("events", []):
        stage = event.get("stage")
        metadata = event.get("metadata") or {}
        if stage in REVIEW_EVENT_STAGES:
            reasons.append(f"事件异常：{stage}")
        if metadata.get("status") == "blocked" or metadata.get("policy_allowed") is False:
            reasons.append(f"工具策略拦截：{metadata.get('tool_name', '-')}")
        if metadata.get("risk_level") == "high":
            reasons.append(f"高风险工具调用：{metadata.get('tool_name', '-')}")
    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


def build_review_item(record: Mapping[str, Any], reasons: Iterable[str] | None = None) -> dict[str, Any]:
    reason_list = list(reasons if reasons is not None else review_reasons_for_task(record))
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "review_id": f"review-{record.get('task_id')}",
        "task_id": record.get("task_id"),
        "scene": record.get("scene"),
        "status": "open",
        "created_at": now,
        "updated_at": now,
        "query": record.get("query"),
        "answer_preview": (record.get("answer") or "")[:160],
        "reasons": reason_list,
        "task_status": record.get("status"),
        "task_path": record.get("metadata", {}).get("task_path"),
    }


def enqueue_review_item(record: Mapping[str, Any], review_dir: Path | None = None, force: bool = False) -> Path | None:
    reasons = review_reasons_for_task(record)
    if not reasons and not force:
        return None
    item = build_review_item(record, reasons=reasons or ["人工抽检"])
    return _json_dump_line(item, (review_dir or get_review_queue_dir()) / REVIEW_QUEUE_FILE_NAME)


def list_review_items(limit: int = 20, status: str | None = "open", review_dir: Path | None = None) -> list[dict[str, Any]]:
    path = (review_dir or get_review_queue_dir()) / REVIEW_QUEUE_FILE_NAME
    records: dict[str, dict[str, Any]] = {}
    for item in _read_jsonl(path):
        if status and item.get("status") != status:
            continue
        records[str(item.get("review_id"))] = item
    return sorted(records.values(), key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)[:limit]


def update_review_status(
    review_id: str,
    status: str,
    note: str = "",
    reviewer: str = "",
    review_dir: Path | None = None,
) -> Path:
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    existing = next((item for item in list_review_items(limit=100000, status=None, review_dir=review_dir) if item.get("review_id") == review_id), None)
    if not existing:
        raise ValueError(f"Review item not found: {review_id}")
    updated = dict(existing)
    updated.update({
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "review_note": note,
        "reviewer": reviewer,
    })
    return _json_dump_line(updated, (review_dir or get_review_queue_dir()) / REVIEW_QUEUE_FILE_NAME)


def build_eval_sample(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scene": record.get("scene"),
        "query": record.get("query"),
        "answer": record.get("answer", ""),
        "expected_keywords": [],
        "source": "agent_task_run",
        "task_id": record.get("task_id"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "needs_labeling": True,
    }


def append_eval_sample(record: Mapping[str, Any], sample_dir: Path | None = None) -> Path:
    sample = build_eval_sample(record)
    return _json_dump_line(sample, (sample_dir or get_eval_sample_dir()) / EVAL_SAMPLE_FILE_NAME)


def should_capture_eval_sample(record: Mapping[str, Any]) -> bool:
    return bool(record.get("query") and record.get("answer") and record.get("status") == "completed")


def list_eval_samples(limit: int = 20, sample_dir: Path | None = None, needs_labeling: bool | None = None) -> list[dict[str, Any]]:
    path = (sample_dir or get_eval_sample_dir()) / EVAL_SAMPLE_FILE_NAME
    latest: dict[str, dict[str, Any]] = {}
    for sample in _read_jsonl(path):
        if needs_labeling is not None and sample.get("needs_labeling") is not needs_labeling:
            continue
        key = str(sample.get("task_id") or f"{sample.get('scene')}::{sample.get('query')}")
        latest[key] = sample
    return sorted(latest.values(), key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)[:limit]


def label_eval_sample(
    task_id: str,
    expected_keywords: Iterable[str],
    note: str = "",
    sample_dir: Path | None = None,
) -> Path:
    existing = next((item for item in list_eval_samples(limit=100000, sample_dir=sample_dir, needs_labeling=None) if item.get("task_id") == task_id), None)
    if not existing:
        raise ValueError(f"Eval sample not found: {task_id}")
    keywords = [keyword.strip() for keyword in expected_keywords if keyword and keyword.strip()]
    if not keywords:
        raise ValueError("expected_keywords must not be empty")
    updated = dict(existing)
    updated.update({
        "expected_keywords": keywords,
        "label_note": note,
        "needs_labeling": False,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })
    return _json_dump_line(updated, (sample_dir or get_eval_sample_dir()) / EVAL_SAMPLE_FILE_NAME)


def export_labeled_eval_dataset(output_path: Path, scene: str | None = None, sample_dir: Path | None = None) -> Path:
    samples = list_eval_samples(limit=100000, sample_dir=sample_dir, needs_labeling=False)
    if scene:
        samples = [sample for sample in samples if sample.get("scene") == scene]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            row = {
                "scene": sample.get("scene"),
                "query": sample.get("query"),
                "expected_keywords": sample.get("expected_keywords", []),
                "source_hint": f"agent_task_run:{sample.get('task_id')}",
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return output_path



def _count_dataset_cases(path: Path) -> tuple[int, Counter[str]]:
    scene_counts: Counter[str] = Counter()
    total = 0
    for row in _read_jsonl(path):
        total += 1
        scene = str(row.get("scene") or "unknown")
        scene_counts[scene] += 1
    return total, scene_counts


def build_production_dashboard(
    review_dir: Path | None = None,
    sample_dir: Path | None = None,
    dataset_dir: Path | None = None,
) -> dict[str, Any]:
    """Summarize review queue, captured samples and regression datasets."""
    dataset_root = dataset_dir or Path("eval") / "datasets"
    reviews = list_review_items(limit=100000, status=None, review_dir=review_dir)
    samples = list_eval_samples(limit=100000, sample_dir=sample_dir, needs_labeling=None)

    review_status_counts = Counter(str(item.get("status") or "unknown") for item in reviews)
    review_scene_counts = Counter(str(item.get("scene") or "unknown") for item in reviews)
    high_risk_reviews = sum(
        1 for item in reviews for reason in item.get("reasons", []) if "高风险" in str(reason)
    )

    sample_scene_counts = Counter(str(item.get("scene") or "unknown") for item in samples)
    labeled_samples = [item for item in samples if item.get("needs_labeling") is False]
    unlabeled_samples = [item for item in samples if item.get("needs_labeling") is not False]

    dataset_scene_summary: dict[str, dict[str, int]] = {}
    dataset_files: list[dict[str, Any]] = []
    seed_cases = 0
    reviewed_cases = 0
    if dataset_root.exists():
        for path in sorted(dataset_root.glob("*.jsonl")):
            dataset_type = "reviewed" if path.name.endswith("_reviewed.jsonl") else "seed" if path.name.endswith("_seed.jsonl") else "other"
            case_count, scenes = _count_dataset_cases(path)
            dataset_files.append({"path": str(path), "name": path.name, "type": dataset_type, "cases": case_count})
            if dataset_type == "seed":
                seed_cases += case_count
            elif dataset_type == "reviewed":
                reviewed_cases += case_count
            for scene, count in scenes.items():
                scene_stats = dataset_scene_summary.setdefault(scene, {"seed_cases": 0, "reviewed_cases": 0, "other_cases": 0, "total_cases": 0})
                scene_stats[f"{dataset_type}_cases"] = scene_stats.get(f"{dataset_type}_cases", 0) + count
                scene_stats["total_cases"] += count

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reviews": {
            "total": len(reviews),
            "open": review_status_counts.get("open", 0),
            "high_risk": high_risk_reviews,
            "by_status": dict(sorted(review_status_counts.items())),
            "by_scene": dict(sorted(review_scene_counts.items())),
        },
        "samples": {
            "total": len(samples),
            "labeled": len(labeled_samples),
            "unlabeled": len(unlabeled_samples),
            "label_rate": round(len(labeled_samples) / len(samples), 4) if samples else 0.0,
            "by_scene": dict(sorted(sample_scene_counts.items())),
        },
        "datasets": {
            "total_files": len(dataset_files),
            "seed_files": sum(1 for item in dataset_files if item["type"] == "seed"),
            "reviewed_files": sum(1 for item in dataset_files if item["type"] == "reviewed"),
            "seed_cases": seed_cases,
            "reviewed_cases": reviewed_cases,
            "total_cases": sum(item["cases"] for item in dataset_files),
            "by_scene": dict(sorted(dataset_scene_summary.items())),
            "files": dataset_files,
        },
    }


def format_production_dashboard_markdown(summary: Mapping[str, Any]) -> str:
    """Render a compact Markdown dashboard for CLI and docs."""
    reviews = summary.get("reviews", {})
    samples = summary.get("samples", {})
    datasets = summary.get("datasets", {})
    lines = [
        "# Agent 生产闭环质量看板",
        "",
        f"生成时间：{summary.get('generated_at', '')}",
        "",
        "## 总览",
        "",
        f"- 复核项：{reviews.get('total', 0)}（open: {reviews.get('open', 0)}，高风险: {reviews.get('high_risk', 0)}）",
        f"- 评测样本：{samples.get('total', 0)}（已标注: {samples.get('labeled', 0)}，待标注: {samples.get('unlabeled', 0)}，标注率: {samples.get('label_rate', 0):.2%}）",
        f"- 回归数据集：{datasets.get('total_files', 0)} 个文件，{datasets.get('total_cases', 0)} 条用例（seed: {datasets.get('seed_cases', 0)}，reviewed: {datasets.get('reviewed_cases', 0)}）",
        "",
        "## 回归数据集场景分布",
        "",
        "| 场景 | Seed 用例 | Reviewed 用例 | 总用例 |",
        "|---|---:|---:|---:|",
    ]
    by_scene = datasets.get("by_scene", {}) or {}
    if by_scene:
        for scene, stats in sorted(by_scene.items()):
            lines.append(
                f"| {scene} | {stats.get('seed_cases', 0)} | {stats.get('reviewed_cases', 0)} | {stats.get('total_cases', 0)} |"
            )
    else:
        lines.append("| - | 0 | 0 | 0 |")
    lines.extend([
        "",
        "## 复核状态分布",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
    ])
    for status, count in sorted((reviews.get("by_status") or {}).items()):
        lines.append(f"| {status} | {count} |")
    if not reviews.get("by_status"):
        lines.append("| - | 0 |")
    lines.extend([
        "",
        "## 样本场景分布",
        "",
        "| 场景 | 样本数 |",
        "|---|---:|",
    ])
    for scene, count in sorted((samples.get("by_scene") or {}).items()):
        lines.append(f"| {scene} | {count} |")
    if not samples.get("by_scene"):
        lines.append("| - | 0 |")
    return "\n".join(lines)

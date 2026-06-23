"""Persistent task-run storage and replay helpers.

Task runs are stored as one JSON file per task plus an append-only index. The
format is intentionally simple so Streamlit UI, CLI tools and future services can
all inspect or replay Agent execution traces without importing LangChain.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from utils.agent_workflow import TaskState


DEFAULT_TASK_RUN_DIR = Path("logs") / "tasks"
INDEX_FILE_NAME = "task_runs.jsonl"


def get_task_run_dir() -> Path:
    return Path(os.getenv("AGENT_TASK_RUN_DIR", str(DEFAULT_TASK_RUN_DIR)))


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def task_run_path(task_id: str, task_dir: Path | None = None) -> Path:
    target_dir = task_dir or get_task_run_dir()
    return target_dir / f"{task_id}.json"


def build_task_run_record(
    *,
    task_state: TaskState,
    query: str,
    answer: str = "",
    status: str = "completed",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "task_id": task_state.task_id,
        "scene": task_state.scene,
        "stage": task_state.stage,
        "status": status,
        "query": query,
        "answer": answer,
        "created_at": task_state.events[0]["time"] if task_state.events else datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "event_count": len(task_state.events),
        "events": list(task_state.events),
        "metadata": dict(metadata or {}),
    }


def save_task_run(record: Mapping[str, Any], task_dir: Path | None = None) -> Path:
    target_dir = task_dir or get_task_run_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    record_dict = dict(record)
    path = task_run_path(str(record_dict["task_id"]), target_dir)
    path.write_text(json.dumps(record_dict, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    index_record = {
        "task_id": record_dict.get("task_id"),
        "scene": record_dict.get("scene"),
        "status": record_dict.get("status"),
        "stage": record_dict.get("stage"),
        "query": record_dict.get("query"),
        "answer_preview": (record_dict.get("answer") or "")[:120],
        "event_count": record_dict.get("event_count", 0),
        "updated_at": record_dict.get("updated_at"),
        "path": str(path),
    }
    with (target_dir / INDEX_FILE_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(index_record, ensure_ascii=False, default=_json_default) + "\n")
    return path


def save_task_state_run(
    *,
    task_state: TaskState,
    query: str,
    answer: str = "",
    status: str = "completed",
    metadata: Mapping[str, Any] | None = None,
    task_dir: Path | None = None,
) -> Path:
    return save_task_run(
        build_task_run_record(
            task_state=task_state,
            query=query,
            answer=answer,
            status=status,
            metadata=metadata,
        ),
        task_dir=task_dir,
    )


def load_task_run(task_id: str, task_dir: Path | None = None) -> dict[str, Any] | None:
    path = task_run_path(task_id, task_dir or get_task_run_dir())
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_recent_task_runs(limit: int = 10, scene: str | None = None, task_dir: Path | None = None) -> list[dict[str, Any]]:
    target_dir = task_dir or get_task_run_dir()
    if not target_dir.exists():
        return []

    records: dict[str, dict[str, Any]] = {}
    index_path = target_dir / INDEX_FILE_NAME
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if scene and item.get("scene") != scene:
                continue
            records[str(item.get("task_id"))] = item

    if not records:
        for path in sorted(target_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.name == INDEX_FILE_NAME:
                continue
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if scene and item.get("scene") != scene:
                continue
            records[str(item.get("task_id"))] = {
                "task_id": item.get("task_id"),
                "scene": item.get("scene"),
                "status": item.get("status"),
                "stage": item.get("stage"),
                "query": item.get("query"),
                "answer_preview": (item.get("answer") or "")[:120],
                "event_count": item.get("event_count", len(item.get("events", []))),
                "updated_at": item.get("updated_at"),
                "path": str(path),
            }

    return sorted(records.values(), key=lambda item: item.get("updated_at") or "", reverse=True)[:limit]


def format_task_run_markdown(record: Mapping[str, Any]) -> str:
    lines = [
        f"# Task Run {record.get('task_id')}",
        "",
        f"- 场景：{record.get('scene')}",
        f"- 状态：{record.get('status')}",
        f"- 阶段：{record.get('stage')}",
        f"- 更新时间：{record.get('updated_at')}",
        f"- 问题：{record.get('query')}",
        "",
        "## 事件轨迹",
    ]
    for event in record.get("events", []):
        lines.append(f"- {event.get('time', '')} · {event.get('stage', '')} · {event.get('detail', '')}")
        metadata = event.get("metadata") or {}
        if metadata:
            lines.append(
                "  - "
                f"tool={metadata.get('tool_name', '-')} "
                f"status={metadata.get('status', '-')} "
                f"risk={metadata.get('risk_level', '-')} "
                f"scope={metadata.get('permission_scope', '-')} "
                f"allowed={metadata.get('policy_allowed', '-')}"
            )
    return "\n".join(lines)

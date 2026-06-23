"""Append-only audit log helpers for Agent tool calls.

The module is dependency-free and keeps all persisted audit records as JSONL so
future UI / replay jobs can consume them without coupling to LangChain.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


DEFAULT_AUDIT_LOG_DIR = Path("logs") / "audit"


def get_audit_log_dir() -> Path:
    return Path(os.getenv("AGENT_AUDIT_LOG_DIR", str(DEFAULT_AUDIT_LOG_DIR)))


def build_audit_record(
    *,
    task_id: str,
    scene: str | None,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "task_id": task_id,
        "scene": scene,
        "event": dict(event),
    }


def write_tool_audit_record(record: Mapping[str, Any], log_dir: Path | None = None) -> Path:
    target_dir = log_dir or get_audit_log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"tool_audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(record), ensure_ascii=False) + "\n")
    return path

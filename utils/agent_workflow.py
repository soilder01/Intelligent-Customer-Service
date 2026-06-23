"""Lightweight Agentic Workflow helpers.

This module intentionally has no LangChain dependency so task-state and
confirmation rules can be unit tested without external model packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

REPORT_INTENT_KEYWORDS = ("报告", "使用报告", "生成报告", "查询记录", "使用记录", "数据统计", "分析报告")
RISKY_ACTION_FETCH_EXTERNAL_DATA = "fetch_external_data"


@dataclass
class TaskState:
    """Minimal task state for observing multi-step Agent workflow progress."""

    task_id: str
    scene: str | None = None
    stage: str = "initialized"
    events: list[dict[str, Any]] = field(default_factory=list)

    def advance(self, stage: str, detail: str = "", metadata: Mapping[str, Any] | None = None) -> None:
        self.stage = stage
        event: dict[str, Any] = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "stage": stage,
            "detail": detail,
        }
        if metadata:
            event["metadata"] = dict(metadata)
        self.events.append(event)

    def audit_tool(self, tool_name: str, status: str, metadata: Mapping[str, Any] | None = None) -> None:
        detail = f"{tool_name} · {status}"
        self.advance("tool_audit", detail, metadata)


@dataclass(frozen=True)
class ConfirmationRequest:
    action: str
    title: str
    reason: str
    prompt: str


def is_report_intent(query: str) -> bool:
    normalized = (query or "").strip().lower()
    return any(keyword.lower() in normalized for keyword in REPORT_INTENT_KEYWORDS)


def required_confirmation(query: str, enabled_tools: Iterable[str] | None = None) -> ConfirmationRequest | None:
    tools = set(enabled_tools or [])
    if tools and RISKY_ACTION_FETCH_EXTERNAL_DATA not in tools:
        return None
    if not is_report_intent(query):
        return None
    return ConfirmationRequest(
        action=RISKY_ACTION_FETCH_EXTERNAL_DATA,
        title="读取外部使用记录",
        reason="生成使用报告需要读取用户外部记录数据，属于较高风险动作，需要用户确认后继续。",
        prompt=query,
    )


def is_action_confirmed(action: str, confirmed_actions: Iterable[str] | None = None) -> bool:
    return action in set(confirmed_actions or [])


def build_confirmation_message(request: ConfirmationRequest) -> str:
    return (
        f"⚠️ 需要确认：{request.title}\n\n"
        f"原因：{request.reason}\n\n"
        "请确认后我再继续执行该操作。"
    )

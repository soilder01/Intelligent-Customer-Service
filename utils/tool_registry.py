"""Tool registry with lightweight metadata for Agentic Workflow.

The registry keeps tool metadata importable without LangChain installed. Actual
LangChain tool objects are loaded lazily only when resolve_tools() is called.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Iterable, Mapping

from utils.agent_workflow import RISKY_ACTION_FETCH_EXTERNAL_DATA


SENSITIVE_ARG_NAMES = {"password", "pwd", "token", "api_key", "apikey", "key", "secret"}


@dataclass(frozen=True)
class ToolParameter:
    """Simple, dependency-free tool parameter schema."""

    name: str
    type: str
    description: str
    required: bool = True

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }


@dataclass(frozen=True)
class ToolPolicyDecision:
    """Result of validating whether a tool call is allowed to execute."""

    allowed: bool
    reasons: tuple[str, ...] = ()

    def message(self) -> str:
        if self.allowed:
            return "工具调用已通过参数、权限和确认校验。"
        return "工具调用已被安全策略拦截：" + "；".join(self.reasons)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    import_path: str
    description: str
    risk_level: str = "low"
    requires_confirmation: bool = False
    permission_scope: str = "public"
    audit_level: str = "basic"
    allowed_scenes: tuple[str, ...] = ("*",)
    parameters: tuple[ToolParameter, ...] = field(default_factory=tuple)

    def load_tool(self) -> Any:
        module_name, attr_name = self.import_path.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, attr_name)

    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {parameter.name: parameter.to_schema() for parameter in self.parameters},
            "required": [parameter.name for parameter in self.parameters if parameter.required],
        }

    def is_allowed_for_scene(self, scene_id: str | None) -> bool:
        return "*" in self.allowed_scenes or (scene_id in self.allowed_scenes if scene_id else False)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "rag_summarize": ToolSpec(
        "rag_summarize",
        "agent.tools.agent_tools.rag_summarize",
        "从当前场景知识库检索参考资料",
        permission_scope="knowledge_base",
        audit_level="basic",
        parameters=(ToolParameter("query", "string", "用户问题或检索关键词"),),
    ),
    "get_weather": ToolSpec(
        "get_weather",
        "agent.tools.agent_tools.get_weather",
        "查询指定城市实时天气",
        permission_scope="external_api",
        audit_level="basic",
        parameters=(ToolParameter("city", "string", "城市名称"),),
    ),
    "get_user_location": ToolSpec(
        "get_user_location",
        "agent.tools.agent_tools.get_user_location",
        "获取用户所在城市",
        risk_level="medium",
        permission_scope="location",
        audit_level="full",
    ),
    "get_user_id": ToolSpec(
        "get_user_id",
        "agent.tools.agent_tools.get_user_id",
        "获取当前用户 ID",
        risk_level="medium",
        permission_scope="user_profile",
        audit_level="full",
    ),
    "get_current_month": ToolSpec(
        "get_current_month",
        "agent.tools.agent_tools.get_current_month",
        "获取当前月份",
        permission_scope="system_time",
        audit_level="basic",
    ),
    RISKY_ACTION_FETCH_EXTERNAL_DATA: ToolSpec(
        RISKY_ACTION_FETCH_EXTERNAL_DATA,
        "agent.tools.agent_tools.fetch_external_data",
        "读取用户外部使用记录",
        risk_level="high",
        requires_confirmation=True,
        permission_scope="external_usage_record",
        audit_level="full",
        parameters=(
            ToolParameter("user_id", "string", "用户 ID"),
            ToolParameter("month", "string", "查询月份，格式如 2025-06"),
        ),
    ),
    "fill_context_for_report": ToolSpec(
        "fill_context_for_report",
        "agent.tools.agent_tools.fill_context_for_report",
        "触发报告生成上下文",
        permission_scope="workflow_context",
        audit_level="basic",
    ),
}


def get_tool_spec(name: str) -> ToolSpec | None:
    return TOOL_REGISTRY.get(name)


def resolve_tool_names(configured_names: Iterable[str] | None = None, scene_id: str | None = None) -> list[str]:
    names = list(TOOL_REGISTRY.keys()) if configured_names is None else [name for name in configured_names if name in TOOL_REGISTRY]
    return [name for name in names if TOOL_REGISTRY[name].is_allowed_for_scene(scene_id)]


def resolve_tools(configured_names: Iterable[str] | None = None, scene_id: str | None = None) -> list[Any]:
    return [TOOL_REGISTRY[name].load_tool() for name in resolve_tool_names(configured_names, scene_id=scene_id)]


def tools_requiring_confirmation(configured_names: Iterable[str] | None = None, scene_id: str | None = None) -> list[str]:
    return [
        name
        for name in resolve_tool_names(configured_names, scene_id=scene_id)
        if TOOL_REGISTRY[name].requires_confirmation
    ]


def tool_parameter_schemas(configured_names: Iterable[str] | None = None, scene_id: str | None = None) -> dict[str, dict[str, Any]]:
    return {
        name: TOOL_REGISTRY[name].parameter_schema()
        for name in resolve_tool_names(configured_names, scene_id=scene_id)
    }


def _redact_arg(name: str, value: Any) -> Any:
    normalized = name.lower().replace("-", "_")
    if normalized in SENSITIVE_ARG_NAMES or any(marker in normalized for marker in SENSITIVE_ARG_NAMES):
        return "***"
    if isinstance(value, str) and len(value) > 80:
        return value[:77] + "..."
    return value


def sanitized_tool_args(args: Mapping[str, Any] | None) -> dict[str, Any]:
    return {name: _redact_arg(name, value) for name, value in dict(args or {}).items()}


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def validate_tool_args(tool_name: str, args: Mapping[str, Any] | None) -> ToolPolicyDecision:
    spec = get_tool_spec(tool_name)
    if spec is None:
        return ToolPolicyDecision(False, (f"未知工具：{tool_name}",))

    raw_args = dict(args or {})
    expected = {parameter.name: parameter for parameter in spec.parameters}
    reasons: list[str] = []

    for parameter in spec.parameters:
        if parameter.required and parameter.name not in raw_args:
            reasons.append(f"缺少必填参数：{parameter.name}")
        elif parameter.name in raw_args and not _matches_type(raw_args[parameter.name], parameter.type):
            reasons.append(f"参数 {parameter.name} 类型不匹配，期望 {parameter.type}")

    unexpected = sorted(name for name in raw_args if name not in expected)
    if unexpected:
        reasons.append("存在未声明参数：" + ", ".join(unexpected))

    return ToolPolicyDecision(not reasons, tuple(reasons))


def _normalize_scopes(scopes: Iterable[str] | str | None) -> set[str]:
    if scopes is None:
        return {"*"}
    if isinstance(scopes, str):
        return {scope.strip() for scope in scopes.split(",") if scope.strip()} or {"*"}
    return {str(scope).strip() for scope in scopes if str(scope).strip()} or {"*"}


def can_execute_tool(
    tool_name: str,
    args: Mapping[str, Any] | None = None,
    confirmed_actions: Iterable[str] | None = None,
    allowed_permission_scopes: Iterable[str] | str | None = None,
) -> ToolPolicyDecision:
    spec = get_tool_spec(tool_name)
    if spec is None:
        return ToolPolicyDecision(False, (f"未知工具：{tool_name}",))

    decisions = [validate_tool_args(tool_name, args)]
    reasons: list[str] = [reason for decision in decisions for reason in decision.reasons]

    allowed_scopes = _normalize_scopes(allowed_permission_scopes)
    if "*" not in allowed_scopes and spec.permission_scope not in allowed_scopes:
        reasons.append(f"权限域未授权：{spec.permission_scope}")

    if spec.requires_confirmation and spec.name not in set(confirmed_actions or []):
        reasons.append(f"高风险工具未确认：{spec.name}")

    return ToolPolicyDecision(not reasons, tuple(reasons))


def build_tool_audit_event(
    tool_name: str,
    args: Mapping[str, Any] | None = None,
    status: str = "started",
    decision: ToolPolicyDecision | None = None,
) -> dict[str, Any]:
    spec = get_tool_spec(tool_name)
    base: dict[str, Any]
    if spec is None:
        base = {
            "tool_name": tool_name,
            "status": status,
            "risk_level": "unknown",
            "permission_scope": "unknown",
            "requires_confirmation": False,
            "args": sanitized_tool_args(args),
        }
    else:
        base = {
            "tool_name": spec.name,
            "status": status,
            "description": spec.description,
            "risk_level": spec.risk_level,
            "permission_scope": spec.permission_scope,
            "audit_level": spec.audit_level,
            "requires_confirmation": spec.requires_confirmation,
            "args": sanitized_tool_args(args),
        }
    if decision is not None:
        base["policy_allowed"] = decision.allowed
        base["policy_reasons"] = list(decision.reasons)
    return base

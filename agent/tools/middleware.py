from typing import Callable
from utils.prompt_loader import load_system_prompts, load_report_prompts
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger
from utils.agent_workflow import TaskState
from utils.audit_log import build_audit_record, write_tool_audit_record
from utils.tool_registry import build_tool_audit_event, can_execute_tool


def get_task_state(runtime: Runtime) -> TaskState:
    task_state = runtime.context.get("task_state")
    if isinstance(task_state, TaskState):
        return task_state
    task_state = TaskState(task_id=runtime.context.get("task_id", "default"), scene=runtime.context.get("scene_name"))
    runtime.context["task_state"] = task_state
    return task_state


def persist_tool_audit(runtime: Runtime, event: dict) -> None:
    try:
        record = build_audit_record(
            task_id=runtime.context.get("task_id", "default"),
            scene=runtime.context.get("scene_name"),
            event=event,
        )
        write_tool_audit_record(record)
    except Exception as e:
        logger.warning(f"[tool audit]写入审计日志失败：{str(e)}")


@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    tool_name = request.tool_call['name']
    tool_args = request.tool_call.get("args", {})
    logger.info(f"[tool monitor]执行工具：{tool_name}")
    logger.info(f"[tool monitor]传入参数：{tool_args}")
    task_state = get_task_state(request.runtime)

    policy_decision = can_execute_tool(
        tool_name,
        tool_args,
        confirmed_actions=request.runtime.context.get("confirmed_actions", []),
        allowed_permission_scopes=request.runtime.context.get("allowed_permission_scopes", "*"),
    )
    audit_started = build_tool_audit_event(tool_name, tool_args, status="started", decision=policy_decision)
    task_state.advance("tool_started", tool_name, audit_started)
    persist_tool_audit(request.runtime, audit_started)

    if request.runtime.context.get("enforce_tool_policy", True) and not policy_decision.allowed:
        audit_blocked = build_tool_audit_event(tool_name, tool_args, status="blocked", decision=policy_decision)
        task_state.advance("tool_blocked", policy_decision.message(), audit_blocked)
        persist_tool_audit(request.runtime, audit_blocked)
        logger.warning(f"[tool monitor]工具{tool_name}被策略拦截：{policy_decision.message()}")
        tool_call_id = request.tool_call.get("id") or request.tool_call.get("tool_call_id") or tool_name
        return ToolMessage(content=policy_decision.message(), tool_call_id=tool_call_id)

    try:
        result = handler(request)
        logger.info(f"[tool monitor]工具{tool_name}调用成功")
        audit_finished = build_tool_audit_event(tool_name, tool_args, status="succeeded", decision=policy_decision)
        persist_tool_audit(request.runtime, audit_finished)

        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True
            task_state.advance("report_context_ready", "报告上下文已触发", audit_finished)
        elif tool_name == "fetch_external_data":
            task_state.advance("external_data_loaded", "已读取外部记录数据", audit_finished)
        else:
            task_state.advance("tool_finished", tool_name, audit_finished)

        return result
    except Exception as e:
        audit_failed = build_tool_audit_event(tool_name, tool_args, status="failed", decision=policy_decision)
        task_state.advance("tool_failed", f"{tool_name}: {str(e)}", audit_failed)
        persist_tool_audit(request.runtime, audit_failed)
        logger.error(f"工具{tool_name}调用失败，原因：{str(e)}")
        raise e


@before_model
def log_before_model(
        state: AgentState,
        runtime: Runtime,
):
    task_state = get_task_state(runtime)
    task_state.advance("model_calling", f"messages={len(state['messages'])}")
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content.strip()}")
    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    scene_name = request.runtime.context.get("scene_name", None)
    is_report = request.runtime.context.get("report", False)

    try:
        if is_report:
            return load_report_prompts(scene_name=scene_name)
        else:
            return load_system_prompts(scene_name=scene_name)
    except Exception as e:
        logger.warning(f"[report_prompt_switch]加载Prompt失败，使用通用兜底Prompt：{str(e)}")
        return "你是一个专业的智能客服，礼貌、准确地回答用户的问题。"

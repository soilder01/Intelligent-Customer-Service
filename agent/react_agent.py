from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from dotenv import load_dotenv
from rag.vector_store import VectorStoreService
from rag.rag_service import RagSummarizeService
from typing import Optional, Dict, List
from utils.agent_workflow import TaskState, build_confirmation_message, is_action_confirmed, required_confirmation
from utils.tool_registry import resolve_tool_names, resolve_tools
from utils.task_store import load_task_run, save_task_state_run
from utils.production_loop import append_eval_sample, enqueue_review_item, should_capture_eval_sample
import os
import time


def parse_permission_scopes(raw_value: str | None) -> list[str]:
    if not raw_value:
        return ["*"]
    scopes = [scope.strip() for scope in raw_value.split(",") if scope.strip()]
    return scopes or ["*"]
load_dotenv()

class ReactAgent:
    def __init__(self, scene_config: Optional[Dict] = None):
        """
        多场景Agent初始化
        :param scene_config: 场景配置（来自 scenes.yml），不传则使用原有配置（向后兼容）
        """
        self.scene_config = scene_config
        self.last_task_state: TaskState | None = None
        self.last_task_run_path: str | None = None
        self.vs = VectorStoreService(scene_config=scene_config)
        self.rag_service = RagSummarizeService(scene_config=scene_config)

        scene_name = scene_config.get("id") if scene_config else None
        system_prompt = load_system_prompts(scene_name=scene_name)

        if scene_config and "tools" in scene_config:
            self.enabled_tool_names = resolve_tool_names(scene_config["tools"], scene_id=scene_name)
        else:
            self.enabled_tool_names = resolve_tool_names(scene_id=scene_name)
        tools = resolve_tools(self.enabled_tool_names, scene_id=scene_name)
        
        self.agent = create_agent(
            model=chat_model,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def _handle_persisted_task(self, task_state: TaskState, query: str, answer: str, status: str) -> None:
        run_path = save_task_state_run(
            task_state=task_state,
            query=query,
            answer=answer,
            status=status,
            metadata={"enabled_tools": self.enabled_tool_names},
        )
        self.last_task_run_path = str(run_path)
        record = load_task_run(task_state.task_id)
        if not record:
            return
        record.setdefault("metadata", {})["task_path"] = self.last_task_run_path
        enqueue_review_item(record)
        if os.getenv("AGENT_AUTO_CAPTURE_EVAL_SAMPLES", "true").lower() in {"1", "true", "yes"} and should_capture_eval_sample(record):
            append_eval_sample(record)

    def get_required_confirmation(self, query: str):
        return required_confirmation(query, self.enabled_tool_names)

    def execute_stream(self, query: str, confirmed_actions: Optional[List[str]] = None, require_confirmation: Optional[bool] = None):
        if require_confirmation is None:
            require_confirmation = os.getenv("AGENT_REQUIRE_CONFIRMATION", "false").lower() in {"1", "true", "yes"}
        confirmation = self.get_required_confirmation(query) if require_confirmation else None
        if confirmation and not is_action_confirmed(confirmation.action, confirmed_actions):
            full_response = build_confirmation_message(confirmation)
            for i in range(0, len(full_response), 1):
                yield full_response[i]
                time.sleep(0.03)
            return

        input_dict = {"messages": [{"role": "user", "content": query}]}
        scene_name = self.scene_config.get("id") if self.scene_config else None
        task_state = TaskState(task_id=str(int(time.time() * 1000)), scene=scene_name)
        task_state.advance("user_query_received", query[:120])
        self.last_task_state = task_state

        try:
            result = self.agent.invoke(
                input_dict,
                context={
                    "report": False,
                    "scene_name": scene_name,
                    "confirmed_actions": confirmed_actions or [],
                    "allowed_permission_scopes": parse_permission_scopes(os.getenv("AGENT_ALLOWED_PERMISSION_SCOPES")),
                    "enforce_tool_policy": os.getenv("AGENT_ENFORCE_TOOL_POLICY", "true").lower() in {"1", "true", "yes"},
                    "task_state": task_state,
                    "task_id": task_state.task_id,
                }
            )
        except Exception as e:
            task_state.advance("task_failed", f"{type(e).__name__}: {str(e)[:160]}")
            full_response = "抱歉，本次任务执行失败，已保存任务轨迹并进入人工复核队列。"
            try:
                self._handle_persisted_task(task_state, query, full_response, status="failed")
                task_state.advance("task_run_persisted", self.last_task_run_path or "")
            except Exception as persist_error:
                task_state.advance("task_run_persist_failed", str(persist_error)[:160])
            for i in range(0, len(full_response), 1):
                yield full_response[i]
                time.sleep(0.03)
            return

        full_response = ""
        if "messages" in result:
            last_msg = result["messages"][-1]
            if hasattr(last_msg, "content"):
                full_response = last_msg.content or ""
            elif isinstance(last_msg, dict):
                full_response = last_msg.get("content", "")
        else:
            full_response = str(result)

        task_state.advance("final_response_ready", f"chars={len(full_response)}")
        try:
            self._handle_persisted_task(task_state, query, full_response, status="completed")
            task_state.advance("task_run_persisted", self.last_task_run_path or "")
        except Exception as e:
            task_state.advance("task_run_persist_failed", str(e)[:160])

        for i in range(0, len(full_response), 1):
            yield full_response[i]
            time.sleep(0.03)  # 控制速度，可调

    def get_last_task_events(self) -> List[Dict[str, str]]:
        return list(self.last_task_state.events) if self.last_task_state else []

    def get_last_task_id(self) -> str | None:
        return self.last_task_state.task_id if self.last_task_state else None

    def get_last_task_run_path(self) -> str | None:
        return self.last_task_run_path

    def reload_knowledge_base(self):
        self.vs.load_document()
        print("✅ 全量知识库已重新加载")
    def upload_single_file(self, file_path: str):
        return self.vs.load_single_document(file_path)


if __name__ == '__main__':
    agent = ReactAgent()

    for chunk in agent.execute_stream("给我生成我的使用报告"):
        print(chunk, end="", flush=True)

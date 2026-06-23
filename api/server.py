"""FastAPI backend for the independent React Agent workbench."""
from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils.agent_workflow import required_confirmation
from utils.config_handler import get_all_scenes, get_scene_by_id
from utils.production_loop import (
    build_production_dashboard,
    export_labeled_eval_dataset,
    label_eval_sample,
    list_eval_samples,
    list_review_items,
    update_review_status,
)
from utils.task_store import list_recent_task_runs, load_task_run


class ChatRequest(BaseModel):
    scene_id: str
    message: str
    confirmed_actions: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    task_id: str | None = None
    events: list[dict[str, Any]] = []
    requires_confirmation: dict[str, str] | None = None
    mode: str = "live"


class ReviewStatusRequest(BaseModel):
    status: str


class LabelSampleRequest(BaseModel):
    expected_keywords: list[str]
    note: str = ""


class ExportDatasetRequest(BaseModel):
    scene_id: str | None = None


def model_key_configured() -> bool:
    return bool(os.getenv("DASHSCOPE_API_KEY"))


def build_demo_chat_response(request: ChatRequest, scene: dict[str, Any]) -> ChatResponse:
    task_id = f"demo-{int(time.time() * 1000)}"
    now = datetime.now().isoformat(timespec="seconds")
    scene_name = scene.get("name") or request.scene_id
    answer = (
        f"当前处于 Demo 模式，已模拟执行「{scene_name}」场景任务：{request.message}\n\n"
        "真实模型 Key 配置后，该入口会调用 ReactAgent、RAG 检索和工具治理链路，并返回真实回答与任务轨迹。"
    )
    return ChatResponse(
        answer=answer,
        task_id=task_id,
        mode="demo",
        events=[
            {"time": now, "stage": "demo_request_received", "detail": request.message[:120], "risk": "low"},
            {"time": now, "stage": "demo_agent_planned", "detail": f"绑定场景：{scene_name}", "risk": "low"},
            {"time": now, "stage": "demo_response_ready", "detail": "无 DASHSCOPE_API_KEY，返回可测模拟结果", "risk": "medium"},
        ],
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Service Workbench API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        configured = model_key_configured()
        return {
            "status": "ok",
            "mode": "live" if configured else "demo",
            "api_online": True,
            "model_key_configured": configured,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

    @app.get("/api/scenes")
    def scenes() -> list[dict[str, Any]]:
        return get_all_scenes()

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return build_production_dashboard(dataset_dir=Path("eval") / "datasets")

    @app.get("/api/messages")
    def messages() -> list[dict[str, str]]:
        return [{"role": "assistant", "content": "你好，我是企业 Agent 工作台。后端 API 已连接，可调用真实场景 Agent。"}]

    @app.get("/api/traces")
    def traces(scene_id: str | None = None) -> list[dict[str, Any]]:
        recent = list_recent_task_runs(limit=1, scene=scene_id)
        if not recent:
            return []
        run = load_task_run(str(recent[0].get("task_id")))
        return run.get("events", []) if run else []

    @app.get("/api/reviews")
    def reviews() -> list[dict[str, Any]]:
        return list_review_items(limit=100, status=None)

    @app.get("/api/samples")
    def samples() -> list[dict[str, Any]]:
        return list_eval_samples(limit=100, needs_labeling=None)

    @app.post("/api/reviews/{review_id}/status")
    def set_review_status(review_id: str, request: ReviewStatusRequest) -> dict[str, Any]:
        try:
            updated = update_review_status(review_id, request.status)
            return {"ok": updated, "review_id": review_id, "status": request.status}
        except ValueError as exc:
            return {"ok": False, "review_id": review_id, "status": request.status, "error": str(exc)}

    @app.post("/api/samples/{sample_id}/label")
    def label_sample(sample_id: str, request: LabelSampleRequest) -> dict[str, Any]:
        try:
            path = label_eval_sample(sample_id, request.expected_keywords, request.note)
            return {"ok": True, "sample_id": sample_id, "path": str(path)}
        except ValueError as exc:
            return {"ok": False, "sample_id": sample_id, "error": str(exc)}

    @app.post("/api/datasets/export-reviewed")
    def export_reviewed(request: ExportDatasetRequest) -> dict[str, Any]:
        scene = request.scene_id
        output = Path("eval") / "datasets" / (f"{scene}_reviewed.jsonl" if scene else "all_reviewed.jsonl")
        path = export_labeled_eval_dataset(output, scene=scene)
        return {"ok": True, "path": str(path), "scene": scene}

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> ChatResponse:
        scenes_data = get_all_scenes()
        scene = get_scene_by_id(request.scene_id) or (scenes_data[0] if scenes_data else {"id": request.scene_id, "tools": []})
        enabled_tools = scene.get("tools") or []
        confirmation = required_confirmation(request.message, enabled_tools)
        if confirmation and confirmation.action not in request.confirmed_actions:
            return ChatResponse(
                answer="该操作需要人工确认后继续。",
                mode="live" if model_key_configured() else "demo",
                requires_confirmation={"action": confirmation.action, "title": confirmation.title, "reason": confirmation.reason},
            )

        if not model_key_configured():
            return build_demo_chat_response(request, scene)

        try:
            from agent.react_agent import ReactAgent

            agent = ReactAgent(scene_config=scene)
            answer = "".join(agent.execute_stream(request.message, confirmed_actions=request.confirmed_actions))
            return ChatResponse(answer=answer, task_id=agent.get_last_task_id(), events=agent.get_last_task_events(), mode="live")
        except Exception as exc:
            now = datetime.now().isoformat(timespec="seconds")
            return ChatResponse(
                answer="真实 Agent 执行失败，已返回可观测错误信息。请检查模型 Key、依赖和后端日志后重试。",
                mode="error",
                events=[{"time": now, "stage": "live_agent_failed", "detail": f"{type(exc).__name__}: {str(exc)[:160]}", "risk": "high"}],
            )

    return app


app = create_app()

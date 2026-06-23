"""FastAPI backend for the independent React Agent workbench."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils.config_handler import get_all_scenes, get_scene_by_id
from utils.production_loop import build_production_dashboard, list_eval_samples, list_review_items
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
    def health() -> dict[str, str]:
        return {"status": "ok"}

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

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> ChatResponse:
        from agent.react_agent import ReactAgent

        scene = get_scene_by_id(request.scene_id) or (get_all_scenes()[0] if get_all_scenes() else {"id": request.scene_id})
        agent = ReactAgent(scene_config=scene)
        confirmation = agent.get_required_confirmation(request.message)
        if confirmation and confirmation.action not in request.confirmed_actions:
            return ChatResponse(
                answer="该操作需要人工确认后继续。",
                requires_confirmation={"action": confirmation.action, "title": confirmation.title, "reason": confirmation.reason},
            )
        answer = "".join(agent.execute_stream(request.message, confirmed_actions=request.confirmed_actions))
        return ChatResponse(answer=answer, task_id=agent.get_last_task_id(), events=agent.get_last_task_events())

    return app


app = create_app()

import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from agent.react_agent import ReactAgent
from utils.config_handler import get_all_scenes, get_scene_by_id
from utils.frontend_view import (
    inject_global_styles,
    quick_actions,
    render_animated_hero,
    render_status_strip,
    render_trace_timeline,
)
from utils.production_dashboard_view import render_production_dashboard
from utils.production_loop import export_labeled_eval_dataset, list_eval_samples, list_review_items
from utils.task_store import format_task_run_markdown, list_recent_task_runs, load_task_run

st.set_page_config(page_title="智能客服中心", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PWD = os.getenv("ADMIN_PWD", "change-me")


def init_session_state(scenes: list[dict]) -> None:
    defaults = {
        "login_status": False,
        "role": "user",
        "message": [],
        "confirmed_actions": [],
        "pending_confirmation": None,
        "last_task_events": [],
        "last_task_id": None,
        "selected_task_replay": None,
        "btn_prompt": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "current_scene_id" not in st.session_state:
        st.session_state.current_scene_id = scenes[0]["id"] if scenes else "default"


def reset_scene(scene_id: str) -> None:
    st.session_state.current_scene_id = scene_id
    st.session_state.pop("agent", None)
    st.session_state.message = []
    st.session_state.confirmed_actions = []
    st.session_state.pending_confirmation = None
    st.session_state.last_task_events = []
    st.session_state.last_task_id = None
    st.session_state.selected_task_replay = None
    st.session_state.btn_prompt = None


def current_scene_or_default(scenes: list[dict]) -> dict:
    scene = get_scene_by_id(st.session_state.current_scene_id)
    if scene:
        return scene
    return scenes[0] if scenes else {"id": "default", "name": "智能客服", "description": "多场景 Agent 工作台", "tools": []}


def ensure_agent(scene: dict) -> None:
    if "agent" not in st.session_state:
        st.session_state.agent = ReactAgent(scene_config=scene)


def render_sidebar(scene: dict, scenes: list[dict]) -> None:
    with st.sidebar:
        st.markdown("<div class='agent-mini-card'><div class='agent-kicker'>AI SERVICE OPS</div><h2 style='margin:.2rem 0;color:#f8fafc'>智能客服中心</h2><span class='agent-pill'>Agentic Workflow</span><span class='agent-pill'>RAG Quality</span></div>", unsafe_allow_html=True)

        scene_options = {item["id"]: item["name"] for item in scenes}
        selected_scene_id = st.selectbox(
            "🎯 当前业务场景",
            options=list(scene_options.keys()),
            format_func=lambda value: scene_options[value],
            index=list(scene_options.keys()).index(st.session_state.current_scene_id),
            key="scene_selector",
        )
        if selected_scene_id != st.session_state.current_scene_id:
            reset_scene(selected_scene_id)
            st.rerun()

        st.info(f"📝 {scene.get('description', '暂无描述')}")
        with st.expander("📊 生产质量看板", expanded=True):
            render_production_dashboard(st, current_scene_id=st.session_state.current_scene_id)
        render_task_replay_picker()
        render_review_queue()
        render_eval_samples(scene)
        render_admin_area(scene)


def render_task_replay_picker() -> None:
    with st.expander("🧾 最近任务记录", expanded=False):
        recent_runs = list_recent_task_runs(limit=5, scene=st.session_state.current_scene_id)
        if not recent_runs:
            st.caption("暂无持久化任务记录")
            return
        for run in recent_runs:
            label = f"{run.get('updated_at', '')} · {run.get('query', '')[:18]}"
            if st.button(label, key=f"task_run_{run.get('task_id')}", use_container_width=True):
                st.session_state.selected_task_replay = run.get("task_id")
        st.caption("点击任务可在主界面查看可回放轨迹")


def render_review_queue() -> None:
    with st.expander("🧑‍⚖️ 人工复核队列", expanded=False):
        review_items = [item for item in list_review_items(limit=20) if item.get("scene") == st.session_state.current_scene_id]
        if not review_items:
            st.caption("暂无待复核任务")
            return
        for item in review_items[:5]:
            st.warning(f"{item.get('review_id')}｜{'; '.join(item.get('reasons', []))}")
            st.caption(f"问题：{item.get('query', '')}")


def render_eval_samples(scene: dict) -> None:
    with st.expander("🧪 评测样本沉淀", expanded=False):
        samples = [sample for sample in list_eval_samples(limit=20) if sample.get("scene") == st.session_state.current_scene_id]
        labeled_samples = [sample for sample in samples if not sample.get("needs_labeling")]
        if not samples:
            st.caption("暂无自动沉淀样本")
            return
        st.caption(f"当前场景最近沉淀样本：{len(samples[:5])} 条；已标注：{len(labeled_samples)} 条")
        for sample in samples[:5]:
            label_state = "待标注" if sample.get("needs_labeling") else "已标注"
            st.write(f"{sample.get('created_at', '')} · {label_state} · {sample.get('query', '')[:24]}")
        if labeled_samples:
            export_path = Path("eval") / "datasets" / f"{scene.get('id')}_reviewed.jsonl"
            if st.button("导出已标注样本到回归评测集", key="export_reviewed_dataset", use_container_width=True):
                export_labeled_eval_dataset(export_path, scene=scene.get("id"))
                st.success(f"已导出到 {export_path}")


def render_admin_area(scene: dict) -> None:
    st.divider()
    if not st.session_state.login_status:
        with st.expander("🔒 管理员登录", expanded=False):
            username = st.text_input("管理员账号")
            password = st.text_input("管理员密码", type="password")
            if st.button("登录", type="primary", use_container_width=True):
                if username == ADMIN_USER and password == ADMIN_PWD:
                    st.session_state.login_status = True
                    st.session_state.role = "admin"
                    st.success("✅ 管理员登录成功")
                    st.rerun()
                else:
                    st.error("账号或密码错误")
        st.info("👤 普通用户模式\n仅可使用智能客服")
        return

    st.success("🟢 管理员模式")
    with st.expander("📁 知识库管理", expanded=True):
        uploaded_file = st.file_uploader(f"上传【{scene.get('name')}】知识库文件", type=["txt", "md", "pdf", "docx"])
        if uploaded_file:
            from utils.path_tool import get_abs_path

            scene_data_path = get_abs_path(scene.get("data_path", "data/default"))
            os.makedirs(scene_data_path, exist_ok=True)
            save_path = os.path.join(scene_data_path, uploaded_file.name)
            with open(save_path, "wb") as file:
                file.write(uploaded_file.getbuffer())
            status = st.session_state.agent.upload_single_file(str(save_path))
            status_messages = {
                "exists": (st.warning, "⚠️ 该知识库文件已经存在，无需重复上传！"),
                "success": (st.success, f"✅ {uploaded_file.name} 已成功加载到【{scene.get('name')}】知识库！"),
                "empty": (st.warning, "⚠️ 文件内无有效文本内容！"),
            }
            handler, message = status_messages.get(status, (st.error, "❌ 文件加载失败，请检查文件格式！"))
            handler(message)
    if st.button("🗑️ 清空对话历史", use_container_width=True):
        st.session_state.message = []
        st.rerun()
    if st.button("🚪 退出登录", type="secondary", use_container_width=True):
        st.session_state.login_status = False
        st.session_state.role = "user"
        st.rerun()


def render_replay_panel() -> None:
    if not st.session_state.selected_task_replay:
        return
    replay = load_task_run(st.session_state.selected_task_replay)
    if replay:
        with st.expander(f"📼 历史任务回放：{replay.get('task_id')}", expanded=True):
            st.markdown(format_task_run_markdown(replay))
    else:
        st.warning("未找到该任务记录，可能日志目录已清理。")


def render_pending_confirmation() -> None:
    if not st.session_state.pending_confirmation:
        return
    pending = st.session_state.pending_confirmation
    st.warning(f"需要确认后继续：{pending['title']}。{pending['reason']}")
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("✅ 确认继续", type="primary", use_container_width=True):
            st.session_state.confirmed_actions = list(set(st.session_state.confirmed_actions + [pending["action"]]))
            st.session_state.btn_prompt = pending["prompt"]
            st.session_state.pending_confirmation = None
            st.rerun()
    with cancel_col:
        if st.button("取消本次操作", use_container_width=True):
            st.session_state.pending_confirmation = None
            st.session_state.message.append({"role": "assistant", "content": "已取消本次高风险操作。"})
            st.rerun()


def render_chat_history(scene: dict) -> None:
    if not st.session_state.message:
        with st.chat_message("assistant", avatar="🤖"):
            st.write(f"👋 你好！我是{scene.get('name')}，有什么可以帮你的吗？")
    for msg in st.session_state.message:
        avatar = "👤" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])


def render_quick_action_bar(scene: dict) -> None:
    st.markdown("<div class='agent-command'>", unsafe_allow_html=True)
    cols = st.columns(3)
    for column, (icon, label, prompt) in zip(cols, quick_actions(scene.get("name", "智能客服"))):
        with column:
            if st.button(f"{icon} {label}", use_container_width=True, key=f"quick_{label}"):
                st.session_state.btn_prompt = prompt
    st.markdown("</div>", unsafe_allow_html=True)


def next_prompt() -> str | None:
    user_input = st.chat_input("输入任务、问题或报告诉求...")
    if st.session_state.btn_prompt:
        prompt = st.session_state.btn_prompt
        st.session_state.btn_prompt = None
        return prompt
    return user_input or None


def handle_prompt(prompt: str) -> None:
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
    st.session_state.message.append({"role": "user", "content": prompt})
    confirmation = st.session_state.agent.get_required_confirmation(prompt)
    if confirmation and confirmation.action not in st.session_state.confirmed_actions:
        confirmation_text = f"⚠️ 需要确认：{confirmation.title}\n\n原因：{confirmation.reason}\n\n请点击下方确认按钮后，我再继续执行该操作。"
        st.session_state.pending_confirmation = {
            "prompt": prompt,
            "action": confirmation.action,
            "title": confirmation.title,
            "reason": confirmation.reason,
        }
        with st.chat_message("assistant", avatar="🤖"):
            st.warning(confirmation_text)
        st.session_state.message.append({"role": "assistant", "content": confirmation_text})
        st.rerun()

    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        full_response = ""
        for chunk in st.session_state.agent.execute_stream(prompt, confirmed_actions=st.session_state.confirmed_actions):
            full_response += chunk
            message_placeholder.markdown(full_response)
        st.session_state.message.append({"role": "assistant", "content": full_response})
        st.session_state.last_task_events = st.session_state.agent.get_last_task_events()
        st.session_state.last_task_id = st.session_state.agent.get_last_task_id()
        st.session_state.confirmed_actions = []


all_scenes = get_all_scenes()
init_session_state(all_scenes)
current_scene = current_scene_or_default(all_scenes)
ensure_agent(current_scene)
inject_global_styles(st)
render_sidebar(current_scene, all_scenes)
render_animated_hero(components, current_scene, st.session_state.role)
render_status_strip(st, current_scene, len(st.session_state.message), st.session_state.last_task_id)
render_replay_panel()
render_pending_confirmation()
render_chat_history(current_scene)
render_trace_timeline(st, st.session_state.last_task_events, st.session_state.last_task_id)
render_quick_action_bar(current_scene)

prompt_text = next_prompt()
if prompt_text:
    handle_prompt(prompt_text)

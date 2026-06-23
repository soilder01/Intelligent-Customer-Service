"""Modern Streamlit UI helpers for the Agent workbench frontend."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

SCENE_ACCENTS = {
    "zhisaotong": ("#22d3ee", "#6366f1"),
    "ecommerce": ("#fb7185", "#f97316"),
    "hr": ("#a78bfa", "#2563eb"),
    "property": ("#34d399", "#14b8a6"),
}


def scene_accent(scene_id: str | None) -> tuple[str, str]:
    """Return a deterministic accent gradient for one scene."""
    return SCENE_ACCENTS.get(scene_id or "", ("#60a5fa", "#7c3aed"))


def quick_actions(scene_name: str) -> list[tuple[str, str, str]]:
    """Provide stable quick-action prompts for the chat command bar."""
    return [
        ("📖", "能力说明", f"你是{scene_name}，能帮我做什么？"),
        ("❓", "常见问题", "当前场景常见问题有哪些？"),
        ("📊", "生成报告", "请基于当前场景生成一份服务质量概览报告"),
    ]


def inject_global_styles(st_module: Any) -> None:
    """Inject the redesigned glassmorphism visual system for Streamlit."""
    st_module.markdown(
        """
<style>
:root {
  --agent-bg: #07111f;
  --agent-surface: rgba(15, 23, 42, 0.72);
  --agent-surface-strong: rgba(15, 23, 42, 0.92);
  --agent-border: rgba(148, 163, 184, 0.24);
  --agent-text: #e5eefb;
  --agent-muted: #94a3b8;
  --agent-cyan: #22d3ee;
  --agent-violet: #8b5cf6;
}
.stApp {
  color: var(--agent-text);
  background:
    radial-gradient(circle at 10% 10%, rgba(34, 211, 238, 0.20), transparent 30%),
    radial-gradient(circle at 90% 0%, rgba(139, 92, 246, 0.20), transparent 35%),
    linear-gradient(135deg, #07111f 0%, #0f172a 48%, #111827 100%);
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.92), rgba(15, 23, 42, 0.84));
  border-right: 1px solid var(--agent-border);
}
.block-container {padding-top: 1.4rem; max-width: 1280px;}
.agent-shell-card, .agent-mini-card {
  border: 1px solid var(--agent-border);
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.78), rgba(30, 41, 59, 0.56));
  box-shadow: 0 20px 60px rgba(2, 6, 23, 0.34);
  border-radius: 24px;
  padding: 18px 20px;
  backdrop-filter: blur(18px);
}
.agent-mini-card {border-radius: 18px; padding: 14px 16px; margin-bottom: 12px;}
.agent-kicker {font-size: 0.78rem; letter-spacing: .16em; text-transform: uppercase; color: var(--agent-cyan); font-weight: 700;}
.agent-title {font-size: clamp(2rem, 4vw, 4.5rem); line-height: .95; font-weight: 850; margin: 0.35rem 0; color: #f8fafc;}
.agent-subtitle {color: #cbd5e1; font-size: 1.02rem; max-width: 720px;}
.agent-pill {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid rgba(148, 163, 184, .30);
  border-radius: 999px; padding: 6px 10px; color: #cbd5e1;
  background: rgba(15, 23, 42, .55); font-size: .84rem; margin: 4px 6px 4px 0;
}
.agent-command button, div[data-testid="stButton"] button {
  border-radius: 999px !important;
  border: 1px solid rgba(125, 211, 252, 0.30) !important;
  background: linear-gradient(135deg, rgba(14,165,233,.18), rgba(139,92,246,.18)) !important;
  color: #e0f2fe !important;
  transition: transform .18s ease, box-shadow .18s ease, border .18s ease;
}
div[data-testid="stButton"] button:hover {
  transform: translateY(-1px);
  border-color: rgba(125, 211, 252, .58) !important;
  box-shadow: 0 12px 28px rgba(56, 189, 248, .16);
}
div[data-testid="stMetric"] {
  border: 1px solid rgba(148, 163, 184, .20);
  border-radius: 18px;
  padding: 12px;
  background: rgba(15, 23, 42, .45);
}
div[data-testid="stChatMessage"] {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, .16);
  background: rgba(15, 23, 42, .42);
}
.agent-trace-row {font-size: .88rem; color: #cbd5e1; border-left: 2px solid #38bdf8; padding: 6px 0 6px 10px; margin: 6px 0;}
.agent-upload-box {border: 1px dashed rgba(125, 211, 252, .45); padding: 1rem; border-radius: 1rem; background: rgba(15, 23, 42, .35);}
</style>
""",
        unsafe_allow_html=True,
    )


def render_animated_hero(components_module: Any, scene: Mapping[str, Any], role: str) -> None:
    """Render the anime.js + GSAP powered hero banner."""
    scene_id = str(scene.get("id", ""))
    scene_name = escape(str(scene.get("name", "智能客服中心")))
    description = escape(str(scene.get("description", "基于 RAG 智能检索 · 多轮任务执行")))
    accent_a, accent_b = scene_accent(scene_id)
    role_label = "管理员控制台" if role == "admin" else "用户工作台"
    components_module.html(
        f"""
<div class="aime-hero" style="font-family: Inter, ui-sans-serif, system-ui; position: relative; overflow: hidden; border: 1px solid rgba(148,163,184,.24); border-radius: 30px; padding: 28px; min-height: 240px; background: linear-gradient(135deg, rgba(15,23,42,.88), rgba(30,41,59,.72)); box-shadow: 0 28px 70px rgba(2,6,23,.35);">
  <div class="orb orb-a" style="position:absolute;width:170px;height:170px;border-radius:999px;background:{accent_a};filter:blur(42px);opacity:.34;right:14%;top:-42px;"></div>
  <div class="orb orb-b" style="position:absolute;width:210px;height:210px;border-radius:999px;background:{accent_b};filter:blur(56px);opacity:.28;right:-40px;bottom:-70px;"></div>
  <div style="position:relative;z-index:1;max-width:760px;">
    <div class="hero-kicker" style="letter-spacing:.18em;text-transform:uppercase;color:{accent_a};font-weight:800;font-size:12px;">Agentic Service OS · {escape(role_label)}</div>
    <h1 class="hero-title" style="margin:10px 0 10px;color:#f8fafc;font-size:54px;line-height:.95;font-weight:900;">{scene_name}<br/>智能工作台</h1>
    <p class="hero-desc" style="margin:0 0 18px;color:#cbd5e1;font-size:16px;line-height:1.65;">{description}</p>
    <div class="hero-pills" style="display:flex;flex-wrap:wrap;gap:8px;">
      <span style="border:1px solid rgba(148,163,184,.32);border-radius:999px;padding:8px 12px;color:#e0f2fe;background:rgba(15,23,42,.55);">RAG 可信引用</span>
      <span style="border:1px solid rgba(148,163,184,.32);border-radius:999px;padding:8px 12px;color:#e0f2fe;background:rgba(15,23,42,.55);">Tool Registry</span>
      <span style="border:1px solid rgba(148,163,184,.32);border-radius:999px;padding:8px 12px;color:#e0f2fe;background:rgba(15,23,42,.55);">Human-in-the-loop</span>
      <span style="border:1px solid rgba(148,163,184,.32);border-radius:999px;padding:8px 12px;color:#e0f2fe;background:rgba(15,23,42,.55);">Quality Gate</span>
    </div>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js"></script>
<script>
  gsap.from('.hero-kicker', {{y: -10, opacity: 0, duration: .7, ease: 'power3.out'}});
  gsap.from('.hero-title', {{y: 18, opacity: 0, duration: .9, delay: .08, ease: 'power3.out'}});
  gsap.from('.hero-desc', {{y: 14, opacity: 0, duration: .8, delay: .18, ease: 'power3.out'}});
  anime({{targets: '.orb', translateX: [0, 18, -12, 0], translateY: [0, -14, 16, 0], scale: [1, 1.08, .96, 1], duration: 6200, loop: true, easing: 'easeInOutSine'}});
  anime({{targets: '.hero-pills span', translateY: [12, 0], opacity: [0, 1], delay: anime.stagger(90, {{start: 320}}), duration: 560, easing: 'easeOutExpo'}});
</script>
""",
        height=280,
    )


def render_status_strip(st_module: Any, scene: Mapping[str, Any], message_count: int, task_id: str | None) -> None:
    """Render high-level scene and session indicators."""
    tools = scene.get("tools") or []
    cols = st_module.columns(4)
    cols[0].metric("场景", scene.get("name", "-") or "-")
    cols[1].metric("可用工具", len(tools))
    cols[2].metric("会话消息", message_count)
    cols[3].metric("最近任务", task_id or "暂无")


def render_trace_timeline(st_module: Any, events: list[Mapping[str, Any]], task_id: str | None) -> None:
    """Render recent Agent workflow events as a compact timeline."""
    if not events:
        return
    with st_module.expander("🧭 最近一次 Agent 执行轨迹", expanded=False):
        if task_id:
            st_module.caption(f"task_id: {task_id}")
        for event in events:
            metadata = event.get("metadata") or {}
            st_module.markdown(
                "<div class='agent-trace-row'>"
                f"<b>{escape(str(event.get('stage', '')))}</b> · "
                f"{escape(str(event.get('detail', '')))}<br/>"
                f"<span style='color:#94a3b8'>{escape(str(event.get('time', '')))}</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if metadata:
                st_module.caption(
                    f"工具：{metadata.get('tool_name', '-')}｜状态：{metadata.get('status', '-')}｜"
                    f"风险：{metadata.get('risk_level', '-')}｜权限域：{metadata.get('permission_scope', '-')}｜"
                    f"需确认：{metadata.get('requires_confirmation', False)}"
                )

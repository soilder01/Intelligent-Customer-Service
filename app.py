import time
import os
from pathlib import Path
import streamlit as st
# 导入你的Agent
from agent.react_agent import ReactAgent
# 导入场景配置
from utils.config_handler import get_all_scenes, get_scene_by_id

# ===================== 页面配置 =====================
st.set_page_config(
    page_title="智能客服中心",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== 核心配置 =====================
ADMIN_USER = "xxx"          # 管理员账号
ADMIN_PWD = "xxx"          # 管理员密码

st.markdown("""
<style>
    .main-title {font-size: 2rem; font-weight: 600; color: #2E4057;}
    .upload-box {border: 1px dashed #4f46e5; padding: 1rem; border-radius: 0.5rem;}
</style>
""", unsafe_allow_html=True)

# ===================== 登录/权限/场景状态管理 =====================
if "login_status" not in st.session_state:
    st.session_state.login_status = False
if "role" not in st.session_state:
    st.session_state.role = "user"
# 新增：当前场景状态
if "current_scene_id" not in st.session_state:
    # 默认使用第一个场景
    all_scenes = get_all_scenes()
    st.session_state.current_scene_id = all_scenes[0]["id"] if all_scenes else "default"

# ===================== 侧边栏 =====================
with st.sidebar:
    st.markdown('<p class="main-title">🤖 智能客服中心</p>', unsafe_allow_html=True)
    st.divider()

    # ===================== 新增：场景切换下拉框（所有人可见） =====================
    st.subheader("🎯 选择场景")
    all_scenes = get_all_scenes()
    scene_options = {scene["id"]: scene["name"] for scene in all_scenes}
    selected_scene_id = st.selectbox(
        "当前场景",
        options=list(scene_options.keys()),
        format_func=lambda x: scene_options[x],
        index=list(scene_options.keys()).index(st.session_state.current_scene_id),
        key="scene_selector",
        disabled=False
    )

    # 场景切换逻辑
    if selected_scene_id != st.session_state.current_scene_id:
        st.session_state.current_scene_id = selected_scene_id
        # 清空Agent和聊天记录，重新初始化
        st.session_state.pop("agent", None)
        st.session_state["message"] = []
        st.rerun()

    # 显示当前场景描述
    current_scene = get_scene_by_id(st.session_state.current_scene_id)
    if current_scene:
        st.info(f"📝 {current_scene.get('description', '暂无描述')}")

    st.divider()

    # 登录模块
    if not st.session_state.login_status:
        st.subheader("🔒 管理员登录")
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

    # 管理员功能区
    if st.session_state.login_status and st.session_state.role == "admin":
        st.success("🟢 管理员模式")
        st.subheader("📁 知识库管理")

        # 文件上传（自动保存到当前场景目录）
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            f"上传【{current_scene.get('name')}】知识库文件",
            type=["txt", "md", "pdf", "docx"]
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # 保存文件 + MD5校验逻辑
        if uploaded_file and current_scene:
            from utils.path_tool import get_abs_path
            # 获取项目内正确的场景数据路径：RAG/data/zhisaotong
            scene_data_path = get_abs_path(current_scene.get("data_path", "data/default"))
            # 创建目录
            os.makedirs(scene_data_path, exist_ok=True)
            # 拼接完整正确路径
            save_path = os.path.join(scene_data_path, uploaded_file.name)
            
            # 写入文件
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # 调用单文件加载 + MD5校验
            status = st.session_state.agent.upload_single_file(str(save_path))
            
            # 前端实时提示
            if status == "exists":
                st.warning("⚠️ 该知识库文件已经存在，无需重复上传！")
            elif status == "success":
                st.success(f"✅ {uploaded_file.name} 已成功加载到【{current_scene.get('name')}】知识库！")
            elif status == "empty":
                st.warning("⚠️ 文件内无有效文本内容！")
            else:
                st.error("❌ 文件加载失败，请检查文件格式！")

        st.divider()

        # 清空对话
        if st.button("🗑️ 清空对话历史", use_container_width=True):
            st.session_state["message"] = []
            st.rerun()

        # 退出登录
        st.divider()
        if st.button("🚪 退出登录", type="secondary", use_container_width=True):
            st.session_state.login_status = False
            st.session_state.role = "user"
            st.rerun()

    # 普通用户提示
    else:
        st.info("👤 普通用户模式\n仅可使用智能客服")

# ===================== 主界面：聊天功能 =====================
# 动态显示当前场景标题
st.markdown(f'<p class="main-title">{current_scene.get("name")}智能客服</p>', unsafe_allow_html=True)
st.caption(f"💡 {current_scene.get('description', '基于 RAG 智能检索 · 多轮对话')}")
st.divider()

# 初始化Agent（按当前场景）
if "agent" not in st.session_state:
    st.session_state.agent = ReactAgent(scene_config=current_scene)
if "message" not in st.session_state:
    st.session_state.message = []

# 欢迎语
if not st.session_state.message:
    with st.chat_message("assistant", avatar="🤖"):
        st.write(f"👋 你好！我是{current_scene.get('name')}，有什么可以帮你的吗？")

# 展示聊天历史
for msg in st.session_state.message:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# 快捷提问
col1, col2, col3 = st.columns(3)

# 初始化会话状态，存储按钮触发的问题
if "btn_prompt" not in st.session_state:
    st.session_state.btn_prompt = None

with col1:
    if st.button("📖 使用说明", use_container_width=True, key="btn1"):
        st.session_state.btn_prompt = "你能帮我做什么？"
with col2:
    if st.button("❓ 常见问题", use_container_width=True, key="btn2"):
        st.session_state.btn_prompt = "常见问题有哪些？"
with col3:
    if st.button("📞 联系管理员", use_container_width=True, key="btn3"):
        st.session_state.btn_prompt = "如何联系管理员？"

user_input = st.chat_input("请输入你的问题...")

prompt = None
if st.session_state.btn_prompt:
    prompt = st.session_state.btn_prompt
    st.session_state.btn_prompt = None 
elif user_input:
    prompt = user_input

if prompt:
    # 用户消息
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
    st.session_state.message.append({"role": "user", "content": prompt})

    # AI 逐字流式回复
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        full_response = ""
        
        # 流式接收数据
        for chunk in st.session_state.agent.execute_stream(prompt):
            full_response += chunk
            message_placeholder.markdown(full_response)
        
        # 保存对话
        st.session_state.message.append({"role": "assistant", "content": full_response})

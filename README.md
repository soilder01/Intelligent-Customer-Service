# 多场景智能Agent平台 🤖
> 基于 LangChain ReAct Agent + RAG + Streamlit 的**一键切换多场景智能Agent平台**，原生支持扫地机器人客服、电商售后、HR助手、园区物业等业务场景，开箱即用，10分钟即可完成新场景上线。

---
# 使用必看
1. 请务必安装好相关配置环境，其中`config/agent.yml`文件中的`gaodekey`需要改为实际申请的高德Web服务API Key
2. 管理员默认账号密码可在`app.py`中配置，用于知识库在线上传与场景管理
3. 多场景核心配置文件为`config/scenes.yml`，可自由扩展自定义业务场景
4. 本项目需配置阿里云DashScope API Key方可正常使用大模型与向量化能力

---

## 📖 项目简介
**多场景智能Agent平台**是一款可灵活扩展的企业级AI智能体应用，从单一场景的扫地机器人客服，升级为配置化多场景Agent平台。系统以 Streamlit 构建轻量级前端网页，后端基于 LangChain 搭建 ReAct（Reasoning + Acting）Agent，整合以下核心能力：

- **多场景一键切换**：前端下拉框一键切换业务场景，场景级Prompt、向量库、工具列表完全隔离，无知识串扰
- **管理员在线知识库管理**：支持前端在线上传知识库文件，MD5自动去重，向量库热更新，无需重启服务
- **场景级权限隔离**：普通用户仅可使用开放场景，仅管理员可上传/管理对应场景的知识库
- **RAG 增强检索**：将产品手册、常见问题、制度规范等文档向量化存储，AI 回答时优先检索对应场景知识库，确保答案准确可靠
- **高德地图服务**：调用高德地图 API 实时获取用户定位与天气信息，可按需配置到对应场景
- **总结汇报模式**：中间件通过识别特定意图，动态切换系统提示词，自动生成场景化使用情况报告（Markdown 格式）
- **多轮工具调用**：Agent 可自主规划并多轮调用所配备的工具，直至满足用户需求
- **流式响应**：最终结果在网页端以逐字流式方式呈现，提升交互体验
- **完善的日志与历史**：配备结构化日志（文件 + 控制台）与对话历史记录

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **多场景支持** | 配置化定义业务场景，原生支持智扫通客服、电商售后、HR助手、园区物业 |
| **场景级隔离** | 每个场景独立Prompt、独立向量库集合、独立知识库目录、独立工具列表 |
| **LLM** | 阿里云通义千问 `qwen3-max`（通过 `ChatTongyi`） |
| **Embedding** | 阿里云 DashScope `text-embedding-v4` |
| **向量数据库** | Chroma（本地持久化，支持多集合隔离） |
| **Agent 框架** | LangChain ReAct Agent + LangGraph |
| **前端** | Streamlit Web 界面，支持场景切换、对话历史 |
| **外部服务** | 高德地图 REST API（天气、IP 定位） |
| **动态提示词** | 中间件根据上下文信号量自动切换 System Prompt |
| **去重机制** | 场景级MD5 哈希追踪已处理文档，避免重复入库 |
| **在线知识库管理** | 管理员前端在线上传文件，向量库热更新，无需重启 |
| **日志** | 按天分文件，同时输出到控制台与文件 |

---

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────┐
│          Streamlit 前端 (app.py)                          │
│  - 场景切换下拉框  - 对话历史  - 流式显示  - 会话状态管理 │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│        多场景 ReAct Agent (agent/react_agent.py)          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  中间件层 (middleware.py)                            │ │
│  │  ├─ monitor_tool   工具调用监控与日志                │ │
│  │  ├─ log_before_model  模型调用前日志                 │ │
│  │  └─ report_prompt_switch 动态提示词切换              │ │
│  └─────────────────────────────────────────────────────┘ │
│  场景级工具集：rag_summarize / get_weather /              │
│         get_user_location / get_user_id /                 │
│         get_current_month / fetch_external_data            │
│         fill_context_for_report（按需配置）                │
└──┬──────────────┬───────────────┬────────────────────────┘
   │              │               │
   ▼              ▼               ▼
┌──────────┐ ┌─────────────┐ ┌────────────────┐
│ 多场景   │ │  高德 API   │ │  外部 CSV 数据 │
│ RAG 服务 │ │ 天气 / 定位 │ │ data/external/ │
│(rag/)    │ └─────────────┘ └────────────────┘
└────┬─────┘
     │
┌────▼──────────────────────────────────────┐
│  Chroma 向量数据库 (chroma_db/)            │
│  多集合隔离：zhisaotong / ecommerce / hr   │
│  Embedding: text-embedding-v4              │
│  场景级知识库目录：data/zhisaotong/ 等     │
│  ├─ PDF / TXT 文档                         │
│  └─ chunk_size=200, k=3                    │
└────────────────────────────────────────────┘
```

---

## 📂 目录结构

```
zhisaotong-Agent/
├── app.py                        # Streamlit 前端入口（含多场景切换、管理员权限）
├── agent/
│   ├── react_agent.py            # 多场景 ReAct Agent 核心逻辑
│   └── tools/
│       ├── agent_tools.py        # 工具函数定义
│       └── middleware.py         # Agent 中间件
├── rag/
│   ├── rag_service.py            # 多场景 RAG 检索摘要服务
│   └── vector_store.py           # 多场景 Chroma 向量库管理
├── model/
│   └── factory.py                # 模型工厂（LLM + Embedding）
├── utils/
│   ├── config_handler.py         # YAML 配置加载器（含多场景配置）
│   ├── logger_handler.py         # 日志工具
│   ├── prompt_loader.py          # 多场景提示词加载器
│   ├── file_handler.py           # 文档加载（PDF/TXT）
│   └── path_tool.py              # 路径工具
├── config/
│   ├── agent.yml                 # Agent 配置（高德 API Key 等）
│   ├── rag.yml                   # 模型名称配置
│   ├── chroma.yml                # 向量库配置
│   ├── prompts.yml               # 提示词文件路径
│   └── scenes.yml                # 多场景配置核心文件
├── prompts/（需自己完善）
│   ├── rag_summarize.txt         # 默认 RAG 摘要提示词
│   ├── zhisaotong.txt            # 智扫通场景系统Prompt
│   ├── zhisaotong_rag.txt        # 智扫通场景RAG Prompt
│   ├── zhisaotong_report.txt     # 智扫通场景Report Prompt
│   ├── ecommerce.txt              # 电商售后场景系统Prompt
│   ├── ecommerce_rag.txt          # 电商售后场景RAG Prompt
│   ├── hr.txt                     # HR助手场景系统Prompt
│   ├── hr_rag.txt                 # HR助手场景RAG Prompt
│   ├── property.txt               # 园区物业场景系统Prompt
│   └── property_rag.txt           # 园区物业场景RAG Prompt
├── data/（需自己完善）
│   ├── external/
│   │   └── records.csv           # 用户使用记录（外部数据）
│   ├── zhisaotong/               # 智扫通场景知识库目录
│   │   ├── 扫地机器人100问.pdf
│   │   ├── 故障排除.txt
│   │   └── .md5_store            # 场景独立MD5去重文件
│   ├── ecommerce/                 # 电商售后场景知识库目录
│   ├── hr/                        # HR助手场景知识库目录
│   └── property/                  # 园区物业场景知识库目录
├── chroma_db/                    # Chroma 持久化目录（自动生成，含多集合）
├── logs/                         # 日志文件目录（自动生成）
├── md5.text                      # 默认MD5去重记录
└── requirements.txt
```

---

## 📦 环境依赖

### Python 版本

建议使用 **Python 3.10+**（代码中使用了 `tuple[str, str]` 等 3.10+ 类型注解语法）。

### 主要依赖包

| 包名 | 用途 |
|------|------|
| `streamlit` | 前端 Web 框架 |
| `langchain` | Agent / Chain / Tool 框架 |
| `langchain-core` | LangChain 核心抽象 |
| `langchain-community` | 通义千问、DashScope Embedding 等集成 |
| `langgraph` | 基于图的 Agent 执行引擎（含 `Runtime`） |
| `langchain-chroma` | LangChain 与 Chroma 向量库集成 |
| `chromadb` | Chroma 向量数据库 |
| `dashscope` | 阿里云 DashScope SDK（Embedding / LLM） |
| `pypdf` / `pypdf2` | PDF 文档加载 |
| `pyyaml` | YAML 配置文件解析 |

### 一键部署（推荐）

```bash
python -m pip install -r requirements.txt
```

---

## ⚙️ 配置说明

### 1. 阿里云 API Key

本项目使用阿里云通义千问大模型和 DashScope Embedding，需要配置系统环境变量：

```bash
# Windows
set DASHSCOPE_API_KEY=your_dashscope_api_key

# Linux/Mac
export DASHSCOPE_API_KEY=your_dashscope_api_key
```

> 可在 [阿里云百炼平台](https://bailian.console.aliyun.com/) 获取 API Key。

### 2. 高德地图 API Key

编辑 `config/agent.yml`，将 `gaodekey` 替换为你的高德地图 Web 服务 API Key：

```yaml
# config/agent.yml
external_data_path: data/external/records.csv
gaodekey: 你的高德key!        # ← 替换这里
gaode_base_url: https://restapi.amap.com
gaode_timeout: 5
```

> 可在 [高德开放平台](https://console.amap.com/) 申请 Web 服务类型的 API Key。

### 3. 多场景配置（核心）

编辑 `config/scenes.yml`，定义你的业务场景：

```yaml
# config/scenes.yml
scenes:
  # 场景1：智扫通客服（原有场景）
  - id: zhisaotong
    name: 智扫通客服
    description: 设备使用、故障排查、知识库检索智能客服
    collection_name: zhisaotong_knowledge_base
    data_path: data/zhisaotong
    public: true  # 普通用户可见
    tools:
      - rag_summarize
      - get_weather
      - get_user_location
      - get_user_id
      - get_current_month
      - fetch_external_data
      - fill_context_for_report

  # 场景2：电商售后客服
  - id: ecommerce
    name: 电商售后客服
    description: 订单查询、退换货、产品使用、保修政策智能客服
    collection_name: ecommerce_knowledge_base
    data_path: data/ecommerce
    public: true
    tools:
      - rag_summarize
      - get_user_id
      - fetch_external_data

  # 场景3：企业HR助手
  - id: hr
    name: 企业HR助手
    description: 员工入职、考勤、薪酬、团建、人事制度智能助手
    collection_name: hr_knowledge_base
    data_path: data/hr
    public: false  # 仅管理员可见
    tools:
      - rag_summarize
      - get_current_month
      - fetch_external_data

  # 场景4：园区物业客服
  - id: property
    name: 园区物业客服
    description: 业主报修、物业费、停车、园区公告智能客服
    collection_name: property_knowledge_base
    data_path: data/property
    public: true
    tools:
      - rag_summarize
      - get_weather
      - get_user_location
```

### 4. 模型配置

编辑 `config/rag.yml` 可调整所使用的模型：

```yaml
# config/rag.yml
chat_model_name: qwen3-max          # 对话大模型
embedding_model_name: text-embedding-v4  # 向量化模型
```

### 5. 向量库配置

编辑 `config/chroma.yml` 可调整 RAG 检索参数：

```yaml
# config/chroma.yml
collection_name: agent              # 默认集合（向后兼容）
persist_directory: chroma_db
k: 3                                # 检索返回的最相关文档数量
data_path: data                     # 默认数据目录（向后兼容）
md5_hex_store: md5.text            # 默认MD5文件（向后兼容）
allow_knowledge_file_type: ["txt", "pdf"]
chunk_size: 200                     # 文本分块大小
chunk_overlap: 20                   # 分块重叠长度
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/soilder01/Intelligent-Customer-Service.git
cd Intelligent-Customer-Service
```

### 2. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
# 设置阿里云 DashScope API Key
export DASHSCOPE_API_KEY="your_dashscope_api_key"

# 在 config/agent.yml 中配置高德地图 API Key
```

### 4. 启动应用

```bash
streamlit run app.py
```

浏览器将自动打开 `http://localhost:8501`，即可开始使用多场景智能Agent平台。

---

## 💬 使用方式

### 场景切换
在侧边栏「选择场景」下拉框中，一键切换业务场景，切换后自动重新初始化Agent，清空对话历史。

### 产品咨询（以智扫通为例）
直接提问关于扫地机器人的使用、维护、故障排除等问题，Agent 会优先从当前场景知识库中检索相关资料进行回答：
```
用户：扫地机器人的滤网多久需要更换一次？
用户：扫拖一体机器人和扫地机器人有什么区别？
用户：扫地机器人吸力变弱了怎么办？
```

### 天气与定位查询（按需配置）
在支持天气/定位工具的场景中，Agent 可调用高德 API 获取实时信息：
```
用户：我现在所在城市今天的天气怎么样？
```

### 使用报告生成（按需配置）
在支持报告生成的场景中，Agent 会自动检测报告生成意图，切换到报告提示词，并调用外部数据生成 Markdown 格式的使用情况报告：
```
用户：帮我生成我的使用报告
用户：给我一份扫地机器人的使用分析和保养建议
```

### 管理员在线上传知识库
1. 在侧边栏登录管理员账号（默认：admin / 123456）
2. 选择要管理的场景
3. 上传知识库文件（支持 .txt / .md / .pdf）
4. 系统自动MD5去重，加载到当前场景向量库，无需重启服务

---

## 🛠 工具列表

Agent 配备了以下 7 个工具，可在 `config/scenes.yml` 中按场景配置启用：

| 工具名 | 描述 |
|--------|------|
| `rag_summarize` | 从当前场景向量知识库中检索参考资料 |
| `get_weather` | 获取指定城市的实时天气（高德 API） |
| `get_user_location` | 通过 IP 获取用户所在城市（高德 API） |
| `get_user_id` | 获取当前用户 ID |
| `get_current_month` | 获取当前月份 |
| `fetch_external_data` | 从外部系统获取指定用户指定月份的使用记录 |
| `fill_context_for_report` | 触发报告模式，通知中间件切换为报告生成提示词 |

---

## 🔄 中间件机制

Agent 的三个中间件负责监控、日志和动态提示词切换：

```
monitor_tool         工具调用监控
  ├─ 记录每次工具调用的名称和参数
  ├─ 记录工具调用成功/失败状态
  └─ 检测 fill_context_for_report 调用，将 context["report"] 置为 True

log_before_model     模型调用前日志
  └─ 记录当前消息数量及最新消息内容

report_prompt_switch 动态提示词切换
  ├─ context["report"] == True  → 使用报告生成提示词
  └─ context["report"] == False → 使用主 ReAct 提示词
```

---

## 📋 日志说明

日志文件存放在 `logs/` 目录下，按天自动创建：

```
logs/
└── agent_20250101.log    # 格式：{name}_{YYYYMMDD}.log
```

日志格式：
```
2025-01-01 12:00:00,123 - agent - INFO - middleware.py:19 - [tool monitor]执行工具：get_weather
```

- **控制台**：输出 INFO 及以上级别日志
- **文件**：输出 DEBUG 及以上级别日志（更详细）

---

## 📚 知识库

### 场景级知识库
每个场景有独立的知识库目录（在 `config/scenes.yml` 中配置 `data_path`），支持 `.txt`、`.md` 和 `.pdf` 格式。

### 在线上传
管理员登录后，在前端上传文件，系统会：
1. 自动保存到当前场景的 `data_path` 目录
2. 计算文件MD5，校验是否已存在
3. 若不存在，自动分片并向量化存入当前场景的 Chroma 集合
4. 保存MD5记录，避免重复入库

### 全量加载
首次启动或需要全量重新加载时，系统会自动扫描当前场景的 `data_path` 目录，加载所有新文件。

---

## 🔮 后续优化方向

- 将向量数据库从 Chroma 替换为 Milvus / Qdrant（更适合生产级多场景部署）
- 地点、天气等功能完整迁移至高德 MCP 协议
- 增加用户身份认证与多用户会话隔离
- 支持更多文档格式（Word、Excel 等）
- 增加场景级Prompt在线编辑功能
- 增加知识库文件在线预览与删除功能

---

## 📄 许可证

本项目仅供学习与参考使用。
感谢黑马程序员开源免费项目、阿里云和高德地图等开放平台。
```

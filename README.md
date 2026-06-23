<p align="center">
  <img src="docs/assets/project-cover-image2.png" alt="多场景智能 Agent 平台" width="100%" />
</p>

# Intelligent Customer Service Agent Platform

面向企业客服与运营复核的多场景智能 Agent 平台。

它不是单纯聊天 Demo，而是把 **React 前台、FastAPI、Agentic Workflow、Tool Registry、RAG、人工复核、样本沉淀、评测质量门禁和 Docker 交付** 串成一条完整链路。

<p align="center">
  <img src="docs/assets/project-architecture-flow.svg" alt="全局架构与流程图" width="100%" />
</p>

## 核心能力

- **多场景客服**：智扫通、电商售后、HR、园区物业，场景配置隔离。
- **现代前端**：Vite + React + TypeScript，包含 Chat、质量看板、轨迹、复核、样本管理。
- **Agent 工作流**：任务状态推进、工具审计、高风险动作确认、可回放执行轨迹。
- **RAG 可信回答**：Chroma 向量库 + 场景知识库，证据不足时拒答。
- **运营闭环**：真实问题 → 人工复核 → 样本补标 → reviewed 数据集 → 回归评测。
- **Demo / Live 双模式**：无 Key 可演示，有 `DASHSCOPE_API_KEY` 后走真实模型链路。
- **工程交付**：本地一键启动、Docker Compose、preflight 检查、密钥扫描。

## 快速启动

### 1. 本地联调

```bash
cp .env.example .env
python scripts/start_local.py
```

访问：

- 前端：<http://localhost:5173/>
- 后端：<http://localhost:8000/api/health>

只看前端 Mock：

```bash
python scripts/start_local.py --mock
```

### 2. Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

访问：<http://localhost:5173/>

## 环境变量

真实密钥只放本地 `.env`，不要提交到仓库。

```bash
DASHSCOPE_API_KEY=your_dashscope_key
GAODE_API_KEY=your_gaode_key
ADMIN_USER=admin
ADMIN_PWD=change_me
```

- 未配置 `DASHSCOPE_API_KEY`：Demo Mode
- 已配置 `DASHSCOPE_API_KEY`：Live Mode

## 项目结构

```text
frontend/              React 运营前台
api/                   FastAPI 服务与后端 Dockerfile
agent/                 Agent 主链路与工具调用
rag/                   RAG 检索与向量库
utils/                 workflow、tool registry、审计、生产闭环
eval/                  评测数据集与质量评估脚本
scripts/               启动、采集、评测、preflight 脚本
docs/                  交付说明、改造计划、数据采集说明
config/                场景、模型、RAG、Prompt 配置
data/                  示例知识库与评测种子数据
tests/                 单元测试
```

## 常用命令

```bash
# 后端 API
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm install && npm run dev

# 质量检查
python scripts/run_preflight.py
cd frontend && npm run build && npm run lint
```

## 文档

- [交付与启动说明](docs/DELIVERY.md)
- [现代化改造计划](docs/MODERNIZATION_PLAN.md)
- [数据采集与评测说明](docs/DATA_ACQUISITION.md)
- [前端工程说明](frontend/README.md)

## 当前状态

- 单测：51 tests
- Preflight：单测、编译、评测流水线、密钥扫描
- 默认分支：已更新为完整收口版本

## 安全说明

- `.env` / `.env.*` 默认忽略，`.env.example` 仅保留占位配置。
- `frontend/node_modules/`、`frontend/dist/`、`eval/reports/`、`logs/`、`chroma_db/` 等运行产物不入库。
- 提交前执行 `python scripts/run_preflight.py`，会进行 token-like 密钥扫描。

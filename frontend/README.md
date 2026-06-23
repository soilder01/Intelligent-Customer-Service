# Agent Service Workbench Frontend

独立现代前端工程，基于 Vite + React + TypeScript，使用 GSAP 与 anime.js 构建企业任务型 Agent 工作台。

## 能力范围

- 多场景 Agent 工作台首页
- 场景切换与工具能力展示
- Chat 面板与快捷指令
- 执行轨迹 Timeline
- 生产质量看板 Dashboard
- 人工复核队列
- 评测样本管理
- API client + mock fallback 数据层

## 运行

```bash
cd frontend
npm install
npm run dev
```

默认使用 mock fallback。后续接入 Python/FastAPI 后，可配置：

```bash
export VITE_AGENT_API_BASE=http://localhost:8000
```

## 构建

```bash
npm run build
```

## 前后端联调

启动 Python API：

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

启动 React 前端并指向 API：

```bash
cd frontend
VITE_AGENT_API_BASE=http://localhost:8000 npm run dev
```

已暴露接口：

- `GET /api/health`
- `GET /api/scenes`
- `GET /api/dashboard`
- `GET /api/messages`
- `GET /api/traces?scene_id=ecommerce`
- `GET /api/reviews`
- `GET /api/samples`
- `POST /api/chat`

前端未配置 `VITE_AGENT_API_BASE` 时继续使用 mock fallback；配置后会优先调用 Python Agent API。

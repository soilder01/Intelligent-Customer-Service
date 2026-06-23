
---

## 🚀 交付与启动路径

### 1. 本地开发联调（推荐）

```bash
cp .env.example .env
python scripts/start_local.py
```

启动后访问：

- 前端：`http://localhost:5173/`
- 后端健康检查：`http://localhost:8000/api/health`

注意：`0.0.0.0` 只用于服务监听，不是浏览器访问地址；本地访问请使用 `localhost`。

如需只看前端 Demo，不连接后端：

```bash
python scripts/start_local.py --mock
```

### 2. Docker Compose 一键启动

```bash
cp .env.example .env
docker compose up --build
```

启动后访问：

- 前端：`http://localhost:5173/`
- 后端：`http://localhost:8000/api/health`

Compose 中前端通过 Nginx 将 `/api/` 代理到 FastAPI 服务，适合本地演示和交付验收。

### 3. Demo / Live 模式说明

- **Demo Mode**：没有 `DASHSCOPE_API_KEY` 时，后端仍返回可观测的模拟回答和执行轨迹，保证产品可演示、可测试。
- **Live Mode**：配置 `DASHSCOPE_API_KEY` 后，`/api/chat` 会调用真实 `ReactAgent`、RAG 检索和工具治理链路。
- 前端顶部状态条会展示：`Demo/Live`、`API Online/Offline`、`Model Key Configured/Missing`。

### 4. 收口检查

```bash
python scripts/run_preflight.py
cd frontend && npm run build && npm run lint
```

Preflight 会执行单测、Python 编译、生产质量看板、无外部 Key 评测流水线和密钥扫描。

# 首批公开数据采集说明

## 目标

为了支撑后续 Agentic Workflow、RAG 优化和效果评测，本次先为现有四个场景补充一批可复用的公开文本数据：

- `zhisaotong`：清洁机器人 / 洗地机常见问题、维护保养、故障排查。
- `ecommerce`：售后政策、退换货、发票、七日无理由退货。
- `hr`：劳动合同、工资支付、社保与人社政策问答。
- `property`：物业费、物业服务、共用设施、投诉争议。

## 产物

### 知识库数据

采集后的文本已经写入各场景原有知识库目录，可直接参与当前项目的 Chroma 入库流程：

- `data/zhisaotong/public_knowledge_seed.txt`
- `data/ecommerce/public_knowledge_seed.txt`
- `data/hr/public_knowledge_seed.txt`
- `data/property/public_knowledge_seed.txt`

### 来源清单

- `data/collected/source_manifest.csv`

字段说明：

| 字段 | 说明 |
|---|---|
| scene | 对应业务场景 |
| title | 来源标题 |
| url | 来源链接 |
| kind | 数据类型 |
| chars | 成功抽取的文本字符数 |
| status | 采集状态 |

本轮共配置 13 个来源，成功 12 个，失败 1 个。失败原因已记录在 manifest 中，后续可重试或替换来源。

### 评测种子集

为了避免后续只堆功能、不评估效果，本次同步创建了四个场景的初版评测集：

- `eval/datasets/zhisaotong_seed.jsonl`
- `eval/datasets/ecommerce_seed.jsonl`
- `eval/datasets/hr_seed.jsonl`
- `eval/datasets/property_seed.jsonl`

每条记录包含：

- `scene`：场景 ID
- `query`：测试问题
- `expected_keywords`：期望回答中应覆盖的关键词
- `source_hint`：对应知识来源提示

## 采集脚本

脚本位置：

```bash
scripts/collect_public_knowledge.py
```

运行全量采集：

```bash
python scripts/collect_public_knowledge.py
```

只采集单个场景：

```bash
python scripts/collect_public_knowledge.py --scene ecommerce
```

## 密钥保护说明

本次数据采集不需要 Ark、Seed、DashScope 或高德密钥。用户提供的 Ark/Seed Key 不会写入任何文件。

后续如需接入 Ark/Seed 做自动评测，只允许通过环境变量读取：

```bash
export ARK_API_KEY="<your_api_key>"
export ARK_BASE_URL="https://ark-cn-beijing.bytedance.net/api/v3"
export ARK_SEED2_PRO_MODEL="ep-xxxxxxxx"
export ARK_SEEDANCE_MODEL="ep-xxxxxxxx"
export ARK_SEEDANCE_TASK_URL="https://ark-cn-beijing.bytedance.net/api/v3/contents/generations/tasks"
```

仓库中只保留变量名，不保存真实 key。

## 二次清洗

公开网页通常会包含导航、页脚、登录提示等噪声。可运行以下脚本对已采集的场景知识库文件做二次清洗：

```bash
python scripts/clean_knowledge_data.py
python scripts/clean_knowledge_data.py --scene ecommerce
```

清洗脚本会保留来源标题、URL、数据类型等元信息，同时过滤常见网页样板文本。

## 聚焦知识抽取

针对长网页和噪声较多的场景，可以从已采集公开语料中抽取与评测问题相关的证据窗口，形成更适合 RAG 召回的聚焦 FAQ 文件：

```bash
python scripts/build_focused_knowledge.py
python scripts/build_focused_knowledge.py --scene ecommerce
```

当前脚本默认处理：

- `ecommerce` → `data/ecommerce/focused_faq_seed.txt`
- `hr` → `data/hr/focused_faq_seed.txt`

脚本只从现有公开语料中截取证据片段，不额外编造事实。评测脚本会读取场景目录下所有 `.txt` 文件，更接近当前 RAG 入库的多文件行为。

## 离线基线评测

在接入真实 Agent 调用、Ark/Seed 自动评分之前，先用关键词覆盖做一个确定性的“数据覆盖基线”：

```bash
python scripts/evaluate_seed_dataset.py
python scripts/evaluate_seed_dataset.py --scene property
```

输出文件位于：

- `eval/reports/keyword_baseline_*.json`
- `eval/reports/keyword_baseline_*.md`

该基线只判断当前场景语料是否覆盖评测种子集中的关键证据，不代表最终 Agent 回答质量。后续接入 Ark/Seed 后，需要进一步评估答案正确性、引用质量、拒答能力和工具调用合理性。

## 本地 RAG 检索基线

为了在接入 Chroma / DashScope Embedding 之前先判断“检索链路是否有希望召回证据”，可运行本地词法检索基线：

```bash
python scripts/evaluate_retrieval_baseline.py
python scripts/evaluate_retrieval_baseline.py --scene ecommerce --top-k 5
```

输出文件位于：

- `eval/reports/retrieval_baseline_*.json`
- `eval/reports/retrieval_baseline_*.md`

该基线会对场景语料进行本地分块，并用确定性的词法打分检索 Top-K 片段，统计：

- Top-K 命中率：Top-K 中是否至少召回一个期望关键词；
- 平均关键词召回率：Top-K 片段覆盖了多少期望关键词；
- 未完全召回用例：用于定位 chunk、query、语料缺口。

它不是最终语义检索效果，但能作为 Chroma/Embedding 接入前的稳定下限指标。

## Chroma 向量检索基线

在完成本地词法检索基线后，可以进一步验证真实 Chroma + DashScope Embedding 链路：

```bash
export DASHSCOPE_API_KEY="your_dashscope_api_key"
python scripts/evaluate_chroma_baseline.py
python scripts/evaluate_chroma_baseline.py --scene ecommerce --top-k 5
```

如果未配置 `DASHSCOPE_API_KEY`，脚本会安全跳过，不会失败，也不会写入任何真实密钥。该脚本使用临时 Chroma 目录，不污染项目默认 `chroma_db/`。

输出文件位于：

- `eval/reports/chroma_baseline_*.json`
- `eval/reports/chroma_baseline_*.md`

该报告用于对比真实向量检索与本地词法检索的差异，后续再接 Ark/Seed 做答案级评审。

## 后续建议

1. 扩充每个场景的数据来源到 30-50 篇。
2. 继续完善清洗规则，去除更多导航、页脚、登录提示等噪声。
3. 用当前评测种子集跑 RAG/Agent 基线，生成质量报告。
4. 接入 Ark/Seed 自动评分，所有 key 只通过环境变量读取。
5. 根据基线结果优化 chunk、Prompt、工具调用和拒答策略。

## Agent 回答采集与 Ark/Seed 答案评审

完成检索链路验证后，可以采集当前 Agent 的真实回答：

```bash
export DASHSCOPE_API_KEY="your_dashscope_api_key"
python scripts/generate_agent_answers.py --limit 5
```

输出文件位于：

- `eval/predictions/agent_answers_*.jsonl`

如果没有 `DASHSCOPE_API_KEY`，脚本会安全跳过。

随后可用 Ark/Seed 对答案做自动评审：

```bash
export ARK_API_KEY="your_ark_api_key"
export ARK_BASE_URL="https://ark-cn-beijing.bytedance.net/api/v3"
export ARK_SEED2_PRO_MODEL="ep-20260609191630-7gkjm"
python scripts/evaluate_answers_with_ark.py eval/predictions/agent_answers_xxx.jsonl
```

如果没有 `ARK_API_KEY`，脚本仍会输出本地关键词覆盖报告，并将 Ark/Seed judge 标记为跳过。真实 key 只能通过环境变量传入，严禁写入仓库。


## 一键评测流水线

为避免每次改 RAG 参数、Prompt 或 Agent 工具后手动串联多条命令，可使用一键评测流水线：

```bash
# 默认执行本地确定性阶段，并在配置外部 Key 时追加真实 Chroma/Agent 阶段
python scripts/run_eval_pipeline.py

# 只执行不依赖外部 Key 的阶段，适合本地快速质量门禁
python scripts/run_eval_pipeline.py --no-external

# 仅打印将要执行的阶段，不真正运行
python scripts/run_eval_pipeline.py --dry-run
```

流水线当前按顺序执行：

1. `clean_knowledge_data.py`：清洗公开网页语料。
2. `build_focused_knowledge.py`：抽取聚焦证据窗口。
3. `evaluate_seed_dataset.py --include-reviewed`：关键词覆盖基线，会同时加载 `*_seed.jsonl` 和已导出的 `*_reviewed.jsonl`。 
4. `evaluate_retrieval_baseline.py --include-reviewed`：本地词法检索基线，会同时加载 `*_seed.jsonl` 和已导出的 `*_reviewed.jsonl`。
5. `evaluate_chroma_baseline.py`：真实 Chroma + DashScope 向量检索基线；缺少 `DASHSCOPE_API_KEY` 时跳过。
6. `generate_agent_answers.py`：采集当前 Agent 回答；缺少 `DASHSCOPE_API_KEY` 时跳过。
7. `evaluate_answers_with_ark.py`：对流水线生成的 `eval/predictions/pipeline_agent_answers.jsonl` 做答案级质量评测；没有 `ARK_API_KEY` 时只运行本地指标。

该脚本不会读取或写入真实密钥；所有外部依赖均通过环境变量判断和读取。建议把它作为后续 RAG/Agent 改动前后的固定回归检查。

## RAG 引用与无证据拒答约束

为让后续答案级评测更稳定，RAG 总结链路已增加两类质量约束：

1. `rag/rag_service.py` 会将检索结果格式化为 `【参考资料N】`，并附带来源信息，方便 Prompt 要求模型输出 `[N]` 引用。
2. 如果检索结果为空或全部为空片段，RAG 层会直接返回统一拒答语：`抱歉，当前知识库中没有检索到足够相关的资料，暂时无法准确回答这个问题。`

四个场景的 `prompts/*_rag.txt` 均已补充：

- 只能基于参考资料回答；
- 关键结论必须标注 `[1]`、`[2]` 等引用；
- 资料不足时使用统一拒答语；
- 不直接大段复制原文。

这一步是进入真实 Agent 答案采集和 Ark/Seed 评审前的基础约束，后续评审脚本可以继续增加“引用覆盖率”“无证据拒答率”等指标。

## 答案级本地质量指标

`evaluate_answers_with_ark.py` 现在即使没有 `ARK_API_KEY`，也会输出更完整的本地答案质量指标：

```bash
python scripts/evaluate_answers_with_ark.py eval/predictions/sample_agent_answers.jsonl
```

报告新增指标：

- 平均关键词覆盖率：答案是否覆盖评测用例的关键事实；
- 引用覆盖率：答案是否包含形如 `[1]`、`[2]` 的参考资料引用；
- 无证据拒答率：答案是否命中统一拒答语；
- 疑似脱离资料率：本地启发式指标，当答案未拒答、关键词覆盖不足且没有引用时标记为风险。

这些指标不能替代 Ark/Seed 语义评审，但可以作为无外部 Key 环境下的稳定质量门禁，并帮助定位 RAG Prompt、引用约束和拒答策略是否生效。

## 完整质量门禁流水线

`run_eval_pipeline.py` 已将答案级评测纳入流水线：

```bash
export DASHSCOPE_API_KEY="your_dashscope_api_key"
# 可选：如需 Ark/Seed 语义评审，再配置 ARK_API_KEY
export ARK_API_KEY="your_ark_api_key"
python scripts/run_eval_pipeline.py
```

当 `DASHSCOPE_API_KEY` 存在时，流水线会把 Agent 回答固定写入：

- `eval/predictions/pipeline_agent_answers.jsonl`

随后自动调用：

```bash
python scripts/evaluate_answers_with_ark.py eval/predictions/pipeline_agent_answers.jsonl
```

如果未配置 `ARK_API_KEY`，该阶段仍会输出关键词覆盖率、引用覆盖率、无证据拒答率和疑似脱离资料率；如果已配置 `ARK_API_KEY`，则在本地指标基础上追加 Ark/Seed judge 分数。

## 质量门禁阈值

三个核心评测脚本已支持阈值参数，低于门槛时会返回非 0 退出码，方便在 CI 或本地流水线中阻断回归：

```bash
python scripts/evaluate_seed_dataset.py --min-avg-coverage 1.0
python scripts/evaluate_retrieval_baseline.py --min-hit-rate 1.0 --min-avg-keyword-recall 0.9
python scripts/evaluate_answers_with_ark.py eval/predictions/sample_agent_answers.jsonl \
  --min-keyword-coverage 0.6 \
  --min-citation-rate 0.5 \
  --max-unsupported-risk-rate 0.2
```

`run_eval_pipeline.py` 默认已接入这些门禁：

- 关键词覆盖率不低于 `1.0`；
- 本地检索 Top-K 命中率不低于 `1.0`；
- 本地检索平均关键词召回率不低于 `0.9`；
- Agent 答案关键词覆盖率不低于 `0.6`；
- Agent 答案引用覆盖率不低于 `0.5`；
- Agent 答案疑似脱离资料率不高于 `0.2`。

可按需要覆盖默认阈值：

```bash
python scripts/run_eval_pipeline.py \
  --min-keyword-coverage 1.0 \
  --min-retrieval-hit-rate 1.0 \
  --min-retrieval-recall 0.9 \
  --min-answer-keyword-coverage 0.6 \
  --min-answer-citation-rate 0.5 \
  --max-answer-unsupported-risk 0.2
```

无外部 Key 场景下，外部依赖阶段仍会安全跳过；只要本地确定性门禁不过，流水线会立即失败。

## Agentic Workflow 基础能力

为后续从“聊天机器人”升级到“任务型 Agent 工作台”，当前已先落地两类轻量能力：

1. 任务状态记录：
   - 新增 `utils/agent_workflow.py` 中的 `TaskState`；
   - `agent/tools/middleware.py` 会在模型调用、工具开始、工具完成、报告上下文触发、外部数据读取等节点推进状态；
   - 当前先写入 `runtime.context["task_state"]`，为后续 UI 展示执行轨迹、失败恢复和可观测性打基础。

2. 高风险动作人工确认：
   - 新增报告意图识别与确认请求：`required_confirmation()`；
   - 当用户请求“生成报告 / 查询使用记录”等需要读取外部数据的任务，且场景启用了 `fetch_external_data`，会识别为高风险动作；
   - `app.py` 会在执行前展示确认按钮，用户确认后才继续调用 Agent；
   - `ReactAgent.execute_stream()` 同时支持 `confirmed_actions`，并保留环境变量 `AGENT_REQUIRE_CONFIRMATION` 作为非 Streamlit 调用的兜底开关。

该改造默认保持现有普通 RAG 问答无感；只对报告 / 外部数据读取链路增加确认。

## Tool Registry、参数 Schema 与执行轨迹展示



在 Agentic Workflow 基础上，当前进一步把工具注册改为带治理元数据的统一注册表：



- `utils/tool_registry.py`：集中维护工具名称、懒加载路径、描述、风险等级、权限域、审计级别、是否需要人工确认和参数 Schema；

- `agent/react_agent.py`：不再手写工具列表，改为通过 `resolve_tool_names()` / `resolve_tools()` 按场景配置加载工具；

- `fetch_external_data` 被标记为 `risk_level="high"`、`permission_scope="external_usage_record"` 且 `requires_confirmation=True`，后续可以继续扩展更多风险动作；

- `agent/tools/middleware.py` 会把工具名、调用状态、风险等级、权限域、确认要求和脱敏后的入参写入 `TaskState.events[*].metadata`；

- `ReactAgent` 会保存最近一次 `TaskState`，并提供 `get_last_task_events()`；

- `app.py` 已新增“最近一次 Agent 执行轨迹”折叠区，用于展示模型调用、工具调用、报告上下文、外部数据读取，以及工具风险 / 权限 / 审计元数据。



这一步为后续 MCP 化工具接入、多工具编排、参数校验、权限治理、风险动作审计和执行轨迹可观测性提供了统一入口。

## 工具策略拦截与审计日志落盘

当前已把工具治理从“只展示元数据”推进到“执行前可拦截、执行后可追溯”：

- `utils/tool_registry.py` 新增 `validate_tool_args()` / `can_execute_tool()`：
  - 校验工具是否存在；
  - 校验必填参数是否齐全；
  - 校验参数类型是否匹配；
  - 拦截未声明的额外参数；
  - 校验工具权限域是否在 `AGENT_ALLOWED_PERMISSION_SCOPES` 中；
  - 校验高风险工具是否已在 `confirmed_actions` 中确认。
- `agent/tools/middleware.py` 在真正调用工具前执行策略校验：
  - 默认启用 `AGENT_ENFORCE_TOOL_POLICY=true`；
  - 如果策略不通过，不再调用真实工具，而是返回安全拦截说明；
  - 拦截事件会写入 `TaskState`，前端可在执行轨迹中看到。
- `utils/audit_log.py` 新增 JSONL 审计日志：
  - 默认写入 `logs/audit/tool_audit_YYYYMMDD.jsonl`；
  - 可通过 `AGENT_AUDIT_LOG_DIR` 修改目录；
  - 审计内容包含任务 ID、场景、工具名、状态、风险等级、权限域、脱敏后的参数和策略判断结果。

相关环境变量：

```bash
# 默认开启。设置为 false 时只记录策略结果，不阻断工具执行。
export AGENT_ENFORCE_TOOL_POLICY=true

# 默认 * 表示允许所有权限域；生产环境可收窄为逗号分隔白名单。
export AGENT_ALLOWED_PERMISSION_SCOPES="knowledge_base,system_time,workflow_context"

# 可选：指定工具审计日志目录。
export AGENT_AUDIT_LOG_DIR="logs/audit"
```

这一步让高风险动作不再只依赖前端按钮保护；即使后续接入 API、批处理或多 Agent 调用，也能在中间件层统一执行参数、权限和确认校验。

## 任务轨迹持久化与回放

为了让 Agentic Workflow 不只停留在前端临时展示，当前已新增任务运行记录持久化能力：

- `utils/task_store.py`：保存、加载、列出和格式化任务运行记录；
- `ReactAgent.execute_stream()`：在生成最终回答后，把 `TaskState`、问题、答案、工具事件、治理元数据保存到 `logs/tasks/<task_id>.json`；
- `logs/tasks/task_runs.jsonl`：追加最近任务索引，便于前端和 CLI 快速列出历史任务；
- `app.py`：侧边栏新增“最近任务记录”，点击后可在主界面打开历史任务回放；
- `scripts/inspect_task_runs.py`：支持命令行查看最近任务和指定任务详情。

常用命令：

```bash
python scripts/inspect_task_runs.py list --limit 10
python scripts/inspect_task_runs.py list --scene ecommerce
python scripts/inspect_task_runs.py show <task_id>
python scripts/inspect_task_runs.py show <task_id> --json
```

相关环境变量：

```bash
export AGENT_TASK_RUN_DIR="logs/tasks"
```

任务记录目录已加入 `.gitignore`，不会把本地用户问题、答案或工具轨迹提交到仓库。这一步为后续任务失败恢复、人工复核队列、自动评测样本抽取和多 Agent 链路追踪提供基础数据结构。

## 生产闭环：失败恢复、人工复核和评测样本沉淀

当前已在任务轨迹持久化之上继续加入运营闭环：

- 失败恢复：`ReactAgent.execute_stream()` 捕获 Agent 调用异常，返回友好失败提示，并保存失败任务记录；
- 人工复核队列：`utils/production_loop.py` 会根据任务状态和事件轨迹生成复核原因，写入 `logs/review/review_queue.jsonl`；
- 评测样本沉淀：成功任务默认写入 `logs/eval_samples/agent_samples.jsonl`，用于后续人工补标 `expected_keywords` 或接入 Ark/Seed 评审；
- 前端入口：`app.py` 侧边栏展示当前场景的待复核任务和最近自动沉淀样本；
- CLI 入口：`scripts/inspect_production_loop.py` 支持离线查看生产闭环资产。

常用命令：

```bash
python scripts/inspect_production_loop.py reviews --limit 20
python scripts/inspect_production_loop.py samples --limit 20
```

相关环境变量：

```bash
export AGENT_REVIEW_QUEUE_DIR="logs/review"
export AGENT_EVAL_SAMPLE_DIR="logs/eval_samples"
export AGENT_AUTO_CAPTURE_EVAL_SAMPLES=true
```

复核触发条件包括：

- `status != completed`；
- `task_failed` / `tool_failed` / `tool_blocked` / `task_run_persist_failed`；
- 工具策略不通过；
- 高风险工具调用。

这一步将“可观测”进一步推进为“可运营”：失败任务有人看，成功任务能沉淀为评测数据，后续可继续扩展为人工标注、自动打分、质量趋势看板和 CI 评测集自动更新。

## 复核状态流转、样本补标与回归评测集导出

当前继续补齐生产闭环的最后一段：

- 复核队列状态流转：`open`、`reviewed`、`fixed`、`ignored`；
- 自动沉淀样本支持人工补标 `expected_keywords`；
- 已补标样本可导出为标准 `eval/datasets/*.jsonl`，继续复用现有质量门禁脚本。

常用命令：

```bash
python scripts/inspect_production_loop.py review-status review-<task_id> fixed --note "已修复" --reviewer "tester"
python scripts/inspect_production_loop.py label-sample <task_id> --keywords "关键词1,关键词2" --note "人工补标"
python scripts/inspect_production_loop.py export-dataset eval/datasets/reviewed_seed.jsonl
python scripts/inspect_production_loop.py export-dataset eval/datasets/ecommerce_reviewed.jsonl --scene ecommerce
```

导出的每行格式与现有种子集一致：

```json
{"scene":"ecommerce","query":"...","expected_keywords":["关键词1"],"source_hint":"agent_task_run:<task_id>"}
```

前端侧边栏也会显示当前场景样本的“待标注 / 已标注”状态，并在存在已标注样本时提供一键导出入口。

导出到 `eval/datasets/<scene>_reviewed.jsonl` 后，这些人工补标样本会自动接入一键评测流水线：

```bash
python scripts/run_eval_pipeline.py --no-external
```

流水线内部会对关键词覆盖和本地检索阶段追加 `--include-reviewed`，所以 `*_reviewed.jsonl` 会与原有 `*_seed.jsonl` 一起参与质量门禁。若需要单独调试数据集加载，也可以直接运行：

```bash
python scripts/evaluate_seed_dataset.py --include-reviewed
python scripts/evaluate_retrieval_baseline.py --include-reviewed --top-k 5
```

这一步使生产闭环真正连接到质量体系：用户真实问题不再只是日志，而可以经过人工复核和补标，沉淀为下一轮回归评测数据，并在后续每次改 RAG、Prompt、工具或 Agent Workflow 时自动参与回归检查。


## 生产闭环质量看板

为了让复核队列、样本池和回归数据集不只是分散文件，Streamlit 侧边栏已新增“📊 生产质量看板”，可查看当前场景 reviewed 用例数、待复核数、高风险数、待标注样本数和标注率。

也可使用 dashboard 命令查看当前质量资产状态：

```bash
python scripts/inspect_production_loop.py dashboard
python scripts/inspect_production_loop.py dashboard --json
```

看板会汇总：

- 复核项总数、open 数、高风险复核项数、状态分布；
- 自动沉淀样本总数、已标注 / 待标注数量、标注率和场景分布；
- `eval/datasets/*.jsonl` 中 seed / reviewed 文件数、用例数和场景分布。

这一步用于连接“生产运行资产”和“回归质量门禁”：先通过看板确认 reviewed 数据集和样本标注状态，再运行 `python scripts/run_eval_pipeline.py --no-external` 做确定性回归检查。


## 本地 preflight 一键检查

提交或创建 MR 前，建议运行本地 preflight，把基础工程检查、质量门禁和密钥扫描串成一个命令：

```bash
python scripts/run_preflight.py
```

默认检查内容：

1. `python -m unittest discover -s tests`：单元测试；
2. `python -m compileall scripts tests agent utils rag model app.py`：Python 编译检查；
3. `python scripts/inspect_production_loop.py dashboard`：生产闭环质量看板；
4. `python scripts/run_eval_pipeline.py --no-external`：无外部 Key 的确定性评测门禁；
5. token-like secret scan：扫描常见真实密钥形态，避免 Key 落盘。

可选参数：

```bash
# 只打印将执行的检查
python scripts/run_preflight.py --dry-run

# 已配置 DASHSCOPE_API_KEY / ARK_API_KEY 时，允许执行外部评测阶段
python scripts/run_preflight.py --include-external

# 快速调试时跳过单测或密钥扫描
python scripts/run_preflight.py --skip-tests
python scripts/run_preflight.py --skip-secret-scan
```

真实密钥仍必须只通过环境变量传入，禁止写入仓库文件。


## 前端整体重构与动效体系

收口前已对 Streamlit 前端做整体重构：

- `app.py` 从线性脚本改为模块化页面编排，拆分会话初始化、侧边栏、管理员区、复核/样本区、聊天区、确认区、任务回放区等逻辑；
- 新增 `utils/frontend_view.py`，集中维护现代化视觉系统、场景色板、快捷操作、执行轨迹展示和 Hero 动效；
- 前端主视觉使用 glassmorphism 深色控制台风格，并通过 CDN 引入 `anime.js` 与 `GSAP`：
  - GSAP 负责 Hero 文案入场动效；
  - anime.js 负责光球、标签等循环微动效；
- 新增 `utils/production_dashboard_view.py` 与侧边栏“📊 生产质量看板”联动，前端可直接查看当前场景 seed/reviewed 回归用例、待复核、高风险和样本标注状态；
- 仍保留原有核心功能：多场景切换、管理员知识库上传、聊天流式回答、高风险动作确认、任务回放、执行轨迹、样本导出。

该改造没有引入新的密钥配置，动画依赖只在浏览器侧加载，不影响后端评测与 preflight 流程。

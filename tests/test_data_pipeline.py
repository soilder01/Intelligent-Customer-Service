import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from utils.agent_workflow import (
    RISKY_ACTION_FETCH_EXTERNAL_DATA,
    TaskState,
    build_confirmation_message,
    is_action_confirmed,
    is_report_intent,
    required_confirmation,
)
from utils.tool_registry import (
    build_tool_audit_event,
    can_execute_tool,
    get_tool_spec,
    resolve_tool_names,
    sanitized_tool_args,
    tool_parameter_schemas,
    tools_requiring_confirmation,
    validate_tool_args,
)
from utils.audit_log import build_audit_record, write_tool_audit_record
from utils.task_store import (
    build_task_run_record,
    format_task_run_markdown,
    list_recent_task_runs,
    load_task_run,
    save_task_run,
    save_task_state_run,
)
from utils.production_loop import (
    append_eval_sample,
    build_eval_sample,
    build_production_dashboard,
    build_review_item,
    enqueue_review_item,
    export_labeled_eval_dataset,
    format_production_dashboard_markdown,
    label_eval_sample,
    list_eval_samples,
    list_review_items,
    review_reasons_for_task,
    should_capture_eval_sample,
    update_review_status,
)
from utils.frontend_view import quick_actions, scene_accent
from utils.production_dashboard_view import render_production_dashboard, scene_dataset_stats
from utils.rag_formatting import NO_EVIDENCE_RESPONSE, format_rag_context
from scripts.build_focused_knowledge import find_evidence_window
from scripts.clean_knowledge_data import clean_text, is_boilerplate
from scripts.evaluate_answers_with_ark import (
    AnswerRecord,
    build_judge_prompt,
    check_thresholds as check_answer_thresholds,
    extract_citations,
    is_no_evidence_answer,
    local_answer_quality,
    local_keyword_eval,
    summarize as summarize_answer_quality,
)
from scripts.evaluate_chroma_baseline import has_dashscope_key, split_text as chroma_split_text
from scripts.evaluate_retrieval_baseline import (
    check_thresholds as check_retrieval_thresholds,
    chunk_text,
    evaluate_retrieval_case,
    retrieve,
    tokenize,
)
from scripts.evaluate_seed_dataset import (
    EvalCase,
    check_thresholds as check_keyword_thresholds,
    discover_dataset_paths,
    evaluate_case,
    load_cases,
    summarize,
)
from scripts.generate_agent_answers import has_dashscope_key as has_agent_dashscope_key, write_predictions
from scripts.run_eval_pipeline import PIPELINE_PREDICTIONS, QualityGateConfig, build_stages, run_pipeline
from scripts.run_preflight import build_preflight_stages, scan_file_for_secrets, should_scan
from api.server import create_app


class KnowledgeCleaningTests(unittest.TestCase):
    def test_boilerplate_detection(self):
        self.assertTrue(is_boilerplate("你好，请登录"))
        self.assertTrue(is_boilerplate("网站首页"))
        self.assertFalse(is_boilerplate("1.房子没入住，要交物业费吗？"))

    def test_clean_text_keeps_source_metadata_and_content(self):
        raw = "# 来源：测试\nURL：https://example.com\n类型：public_web\n网站首页\n1.有效问题？\n有效回答。\n"
        cleaned = clean_text(raw)
        self.assertIn("# 来源：测试", cleaned)
        self.assertIn("URL：https://example.com", cleaned)
        self.assertIn("1.有效问题？", cleaned)
        self.assertNotIn("网站首页", cleaned)


class KeywordBaselineTests(unittest.TestCase):
    def test_evaluate_case_keyword_coverage(self):
        case = EvalCase(scene="demo", query="怎么退货？", expected_keywords=["退货地址", "联系电话"])
        result = evaluate_case(case, "商家应提供退货地址和退货联系人。")
        self.assertEqual(result.matched_keywords, ["退货地址"])
        self.assertEqual(result.missing_keywords, ["联系电话"])
        self.assertEqual(result.coverage, 0.5)

    def test_summarize(self):
        results = [
            evaluate_case(EvalCase("a", "q1", ["A"]), "A"),
            evaluate_case(EvalCase("a", "q2", ["A", "B"]), "A"),
        ]
        summary = summarize(results)
        self.assertEqual(summary["total_cases"], 2)
        self.assertEqual(summary["by_scene"]["a"]["cases"], 2)
        self.assertEqual(summary["by_scene"]["a"]["full_match"], 1)

    def test_keyword_threshold_check(self):
        self.assertEqual(check_keyword_thresholds({"avg_coverage": 1.0}, min_avg_coverage=1.0), [])
        self.assertTrue(check_keyword_thresholds({"avg_coverage": 0.5}, min_avg_coverage=0.9))


class FocusedKnowledgeTests(unittest.TestCase):
    def test_find_evidence_window_uses_existing_keyword(self):
        corpus = "前文\n消费者获得上述信息后应当及时退回商品，并保留退货凭证。\n后文"
        snippet = find_evidence_window(corpus, ["退货凭证"])
        self.assertIn("退货凭证", snippet)
        self.assertIn("及时退回商品", snippet)


class RetrievalBaselineTests(unittest.TestCase):
    def test_tokenize_contains_chinese_ngrams(self):
        tokens = tokenize("退货地址")
        self.assertIn("退", tokens)
        self.assertIn("退货", tokens)
        self.assertIn("退货地", tokens)

    def test_retrieve_returns_relevant_chunk(self):
        chunks = chunk_text("demo", "退货政策\n\n商家应提供退货地址、联系人和联系电话。", chunk_size=50, overlap=5)
        retrieved = retrieve("申请退货需要什么信息", chunks, top_k=1)
        self.assertTrue(retrieved)
        self.assertIn("退货地址", retrieved[0].text)

    def test_evaluate_retrieval_case(self):
        chunks = chunk_text("demo", "商家应提供退货地址和联系电话。", chunk_size=50, overlap=5)
        case = EvalCase(scene="demo", query="退货信息", expected_keywords=["退货地址", "联系电话"])
        result = evaluate_retrieval_case(case, chunks, top_k=1)
        self.assertTrue(result.hit)
        self.assertEqual(result.keyword_recall, 1.0)

    def test_retrieval_threshold_check(self):
        summary = {"hit_rate": 1.0, "avg_keyword_recall": 0.95}
        self.assertEqual(check_retrieval_thresholds(summary, min_hit_rate=1.0, min_avg_keyword_recall=0.9), [])
        self.assertTrue(check_retrieval_thresholds(summary, min_hit_rate=1.0, min_avg_keyword_recall=1.0))


class ChromaBaselineHelperTests(unittest.TestCase):
    def test_chroma_split_text_validates_overlap(self):
        with self.assertRaises(ValueError):
            chroma_split_text("abc", chunk_size=10, overlap=10)

    def test_chroma_split_text_splits_lines(self):
        chunks = chroma_split_text("第一行\n第二行\n第三行", chunk_size=8, overlap=2)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("第一行", chunks[0])

    def test_has_dashscope_key_returns_bool(self):
        self.assertIsInstance(has_dashscope_key(), bool)


class AnswerQualityTests(unittest.TestCase):
    def test_local_keyword_eval(self):
        record = AnswerRecord("demo", "q", "请保留退货凭证并及时退回商品", ["退货凭证", "退回商品"])
        matched, missing, coverage = local_keyword_eval(record)
        self.assertEqual(matched, ["退货凭证", "退回商品"])
        self.assertEqual(missing, [])
        self.assertEqual(coverage, 1.0)

    def test_build_judge_prompt_contains_json_requirement(self):
        record = AnswerRecord("demo", "怎么退货", "回答", ["退货凭证"])
        prompt = build_judge_prompt(record)
        self.assertIn("只输出 JSON", prompt)
        self.assertIn("怎么退货", prompt)

    def test_agent_dashscope_key_returns_bool(self):
        self.assertIsInstance(has_agent_dashscope_key(), bool)

    def test_write_predictions_supports_explicit_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "answers.jsonl"
            written = write_predictions([
                {"scene": "demo", "query": "q", "answer": "a", "expected_keywords": []}
            ], output_path=output_path)
            self.assertEqual(written, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("demo", output_path.read_text(encoding="utf-8"))

    def test_extract_citations_deduplicates_numeric_markers(self):
        self.assertEqual(extract_citations("结论一[1]，结论二[2]，重复[1]"), ["1", "2"])

    def test_no_evidence_answer_detection(self):
        self.assertTrue(is_no_evidence_answer(NO_EVIDENCE_RESPONSE))

    def test_local_answer_quality_flags_citation_and_risk(self):
        cited = AnswerRecord("demo", "q", "请保留退货凭证。[1]", ["退货凭证"])
        cited_quality = local_answer_quality(cited)
        self.assertTrue(cited_quality.has_citation)
        self.assertFalse(cited_quality.unsupported_risk)

        risky = AnswerRecord("demo", "q", "可以直接联系客服处理。", ["退货凭证"])
        risky_quality = local_answer_quality(risky)
        self.assertFalse(risky_quality.has_citation)
        self.assertTrue(risky_quality.unsupported_risk)

    def test_answer_quality_summary_contains_new_metrics(self):
        records = [
            AnswerRecord("demo", "q1", "保留退货凭证。[1]", ["退货凭证"]),
            AnswerRecord("demo", "q2", NO_EVIDENCE_RESPONSE, ["未知关键词"]),
        ]
        from scripts.evaluate_answers_with_ark import evaluate_records
        results = evaluate_records(records, use_ark=False, model="dummy", base_url="https://example.com")
        summary = summarize_answer_quality(results)
        self.assertEqual(summary["total_cases"], 2)
        self.assertEqual(summary["citation_rate"], 0.5)
        self.assertEqual(summary["no_evidence_rate"], 0.5)

    def test_answer_threshold_check(self):
        summary = {"avg_keyword_coverage": 0.8, "citation_rate": 0.7, "unsupported_risk_rate": 0.1}
        self.assertEqual(check_answer_thresholds(summary, 0.6, 0.5, 0.2), [])
        self.assertTrue(check_answer_thresholds(summary, 0.9, 0.5, 0.2))
        self.assertTrue(check_answer_thresholds(summary, 0.6, 0.8, 0.2))
        self.assertTrue(check_answer_thresholds(summary, 0.6, 0.5, 0.05))


class AgentWorkflowTests(unittest.TestCase):
    def test_report_intent_requires_external_data_confirmation(self):
        request = required_confirmation("帮我生成本月使用报告", [RISKY_ACTION_FETCH_EXTERNAL_DATA])
        self.assertIsNotNone(request)
        self.assertEqual(request.action, RISKY_ACTION_FETCH_EXTERNAL_DATA)
        self.assertIn("读取外部使用记录", request.title)

    def test_non_report_or_missing_tool_does_not_require_confirmation(self):
        self.assertFalse(is_report_intent("扫地机器人怎么保养？"))
        self.assertIsNone(required_confirmation("帮我生成本月使用报告", ["rag_summarize"]))

    def test_confirmation_helpers_and_task_state(self):
        request = required_confirmation("查询使用记录", [RISKY_ACTION_FETCH_EXTERNAL_DATA])
        self.assertFalse(is_action_confirmed(RISKY_ACTION_FETCH_EXTERNAL_DATA, []))
        self.assertTrue(is_action_confirmed(RISKY_ACTION_FETCH_EXTERNAL_DATA, [RISKY_ACTION_FETCH_EXTERNAL_DATA]))
        self.assertIn("需要确认", build_confirmation_message(request))

        state = TaskState(task_id="demo", scene="zhisaotong")
        state.advance("tool_started", "fetch_external_data")
        self.assertEqual(state.stage, "tool_started")
        self.assertEqual(state.events[-1]["detail"], "fetch_external_data")

    def test_tool_registry_exposes_risk_metadata(self):
        spec = get_tool_spec(RISKY_ACTION_FETCH_EXTERNAL_DATA)
        self.assertIsNotNone(spec)
        self.assertTrue(spec.requires_confirmation)
        self.assertEqual(spec.permission_scope, "external_usage_record")
        self.assertIn("user_id", spec.parameter_schema()["properties"])
        self.assertEqual(tools_requiring_confirmation(["rag_summarize", RISKY_ACTION_FETCH_EXTERNAL_DATA]), [RISKY_ACTION_FETCH_EXTERNAL_DATA])
        self.assertEqual(resolve_tool_names(["rag_summarize", "unknown"]), ["rag_summarize"])
        self.assertEqual(get_tool_spec("rag_summarize").import_path, "agent.tools.agent_tools.rag_summarize")

    def test_tool_registry_parameter_schema_and_audit_event(self):
        schemas = tool_parameter_schemas(["get_weather", RISKY_ACTION_FETCH_EXTERNAL_DATA])
        self.assertIn("city", schemas["get_weather"]["properties"])
        self.assertEqual(sanitized_tool_args({"api_key": "secret", "city": "北京"})["api_key"], "***")

        audit = build_tool_audit_event(RISKY_ACTION_FETCH_EXTERNAL_DATA, {"user_id": "1001", "month": "2025-06"}, status="started")
        self.assertEqual(audit["risk_level"], "high")
        self.assertEqual(audit["permission_scope"], "external_usage_record")
        self.assertTrue(audit["requires_confirmation"])
        self.assertEqual(audit["args"]["month"], "2025-06")

    def test_task_state_keeps_audit_metadata(self):
        state = TaskState(task_id="demo", scene="zhisaotong")
        state.advance("tool_started", "fetch_external_data", {"risk_level": "high"})
        self.assertEqual(state.events[-1]["metadata"]["risk_level"], "high")

    def test_tool_arg_validation_and_permission_policy(self):
        self.assertTrue(validate_tool_args("get_weather", {"city": "北京"}).allowed)
        invalid = validate_tool_args("get_weather", {})
        self.assertFalse(invalid.allowed)
        self.assertIn("缺少必填参数", invalid.message())

        blocked = can_execute_tool(RISKY_ACTION_FETCH_EXTERNAL_DATA, {"user_id": "1001", "month": "2025-06"}, confirmed_actions=[])
        self.assertFalse(blocked.allowed)
        self.assertIn("高风险工具未确认", blocked.message())

        denied = can_execute_tool("get_weather", {"city": "北京"}, allowed_permission_scopes=["knowledge_base"])
        self.assertFalse(denied.allowed)
        self.assertIn("权限域未授权", denied.message())

        allowed = can_execute_tool(RISKY_ACTION_FETCH_EXTERNAL_DATA, {"user_id": "1001", "month": "2025-06"}, confirmed_actions=[RISKY_ACTION_FETCH_EXTERNAL_DATA])
        self.assertTrue(allowed.allowed)

    def test_audit_log_record_can_be_written_as_jsonl(self):
        audit = build_tool_audit_event("get_weather", {"city": "北京"}, status="succeeded")
        record = build_audit_record(task_id="task-1", scene="demo", event=audit)
        self.assertEqual(record["task_id"], "task-1")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_tool_audit_record(record, log_dir=Path(tmpdir))
            self.assertTrue(path.exists())
            self.assertIn("get_weather", path.read_text(encoding="utf-8"))

    def test_task_run_store_supports_save_list_load_and_markdown(self):
        state = TaskState(task_id="task-2", scene="demo")
        state.advance("user_query_received", "问题")
        state.advance("final_response_ready", "chars=2")
        record = build_task_run_record(task_state=state, query="问题", answer="回答")
        self.assertEqual(record["event_count"], 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            path = save_task_run(record, task_dir=task_dir)
            self.assertTrue(path.exists())
            loaded = load_task_run("task-2", task_dir=task_dir)
            self.assertEqual(loaded["answer"], "回答")
            recent = list_recent_task_runs(limit=1, scene="demo", task_dir=task_dir)
            self.assertEqual(recent[0]["task_id"], "task-2")
            markdown = format_task_run_markdown(loaded)
            self.assertIn("Task Run task-2", markdown)

    def test_save_task_state_run_writes_task_file(self):
        state = TaskState(task_id="task-3", scene="demo")
        state.advance("user_query_received", "q")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_task_state_run(task_state=state, query="q", answer="a", task_dir=Path(tmpdir))
            self.assertTrue(path.exists())

    def test_review_queue_and_eval_sample_capture(self):
        record = {
            "task_id": "task-4",
            "scene": "demo",
            "status": "failed",
            "query": "q",
            "answer": "a",
            "events": [{"stage": "task_failed", "metadata": {}}],
            "metadata": {},
        }
        reasons = review_reasons_for_task(record)
        self.assertTrue(reasons)
        self.assertEqual(build_review_item(record, reasons)["review_id"], "review-task-4")

        with tempfile.TemporaryDirectory() as tmpdir:
            review_dir = Path(tmpdir) / "review"
            sample_dir = Path(tmpdir) / "samples"
            self.assertTrue(enqueue_review_item(record, review_dir=review_dir))
            self.assertEqual(list_review_items(review_dir=review_dir)[0]["task_id"], "task-4")
            update_review_status("review-task-4", "fixed", note="已修复", reviewer="tester", review_dir=review_dir)
            self.assertEqual(list_review_items(status="fixed", review_dir=review_dir)[0]["status"], "fixed")

            completed = dict(record, status="completed")
            self.assertTrue(should_capture_eval_sample(completed))
            sample = build_eval_sample(completed)
            self.assertTrue(sample["needs_labeling"])
            append_eval_sample(completed, sample_dir=sample_dir)
            self.assertEqual(list_eval_samples(sample_dir=sample_dir)[0]["task_id"], "task-4")
            label_eval_sample("task-4", ["关键词A", "关键词B"], sample_dir=sample_dir)
            self.assertFalse(list_eval_samples(sample_dir=sample_dir, needs_labeling=False)[0]["needs_labeling"])
            output_path = Path(tmpdir) / "dataset.jsonl"
            export_labeled_eval_dataset(output_path, sample_dir=sample_dir)
            self.assertIn("关键词A", output_path.read_text(encoding="utf-8"))

    def test_production_dashboard_summarizes_reviews_samples_and_datasets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            review_dir = root / "review"
            sample_dir = root / "samples"
            dataset_dir = root / "datasets"
            record = {
                "task_id": "task-dashboard",
                "scene": "ecommerce",
                "status": "failed",
                "query": "q",
                "answer": "a",
                "events": [{"stage": "tool_blocked", "metadata": {"risk_level": "high", "tool_name": "fetch_external_data"}}],
                "metadata": {},
            }
            enqueue_review_item(record, review_dir=review_dir)
            completed = dict(record, status="completed")
            append_eval_sample(completed, sample_dir=sample_dir)
            label_eval_sample("task-dashboard", ["关键词A"], sample_dir=sample_dir)
            dataset_dir.mkdir(parents=True)
            (dataset_dir / "ecommerce_seed.jsonl").write_text(
                '{"scene":"ecommerce","query":"seed","expected_keywords":["seed"]}\n',
                encoding="utf-8",
            )
            export_labeled_eval_dataset(dataset_dir / "ecommerce_reviewed.jsonl", sample_dir=sample_dir)

            summary = build_production_dashboard(review_dir=review_dir, sample_dir=sample_dir, dataset_dir=dataset_dir)
            self.assertEqual(summary["reviews"]["open"], 1)
            self.assertEqual(summary["reviews"]["high_risk"], 1)
            self.assertEqual(summary["samples"]["labeled"], 1)
            self.assertEqual(summary["datasets"]["reviewed_cases"], 1)
            markdown = format_production_dashboard_markdown(summary)
            self.assertIn("Agent 生产闭环质量看板", markdown)
            self.assertIn("ecommerce", markdown)


class FakeStreamlit:
    def __init__(self):
        self.calls = []

    def caption(self, text):
        self.calls.append(("caption", text))

    def metric(self, label, value):
        self.calls.append(("metric", label, value))

    def columns(self, count):
        self.calls.append(("columns", count))
        return [self for _ in range(count)]

    def expander(self, label, expanded=False):
        self.calls.append(("expander", label, expanded))
        return self

    def table(self, rows):
        self.calls.append(("table", rows))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FrontendViewTests(unittest.TestCase):
    def test_scene_accent_and_quick_actions_are_stable(self):
        self.assertEqual(scene_accent("ecommerce"), ("#fb7185", "#f97316"))
        self.assertEqual(scene_accent("unknown"), ("#60a5fa", "#7c3aed"))
        actions = quick_actions("电商售后客服")
        self.assertEqual(len(actions), 3)
        self.assertIn("电商售后客服", actions[0][2])
        self.assertIn("生成", actions[2][1])


class DatasetLoadingTests(unittest.TestCase):
    def test_reviewed_datasets_are_opt_in_and_filterable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir)
            (dataset_dir / "ecommerce_seed.jsonl").write_text(
                '{"scene":"ecommerce","query":"种子问题","expected_keywords":["种子"]}\n',
                encoding="utf-8",
            )
            (dataset_dir / "ecommerce_reviewed.jsonl").write_text(
                '{"scene":"ecommerce","query":"复核问题","expected_keywords":["复核"],"source_hint":"agent_task_run:t1"}\n',
                encoding="utf-8",
            )
            (dataset_dir / "hr_reviewed.jsonl").write_text(
                '{"scene":"hr","query":"HR复核","expected_keywords":["劳动"]}\n',
                encoding="utf-8",
            )

            self.assertEqual([path.name for path in discover_dataset_paths(dataset_dir)], ["ecommerce_seed.jsonl"])
            self.assertEqual(
                [path.name for path in discover_dataset_paths(dataset_dir, include_reviewed=True)],
                ["ecommerce_seed.jsonl", "ecommerce_reviewed.jsonl", "hr_reviewed.jsonl"],
            )
            cases = load_cases(dataset_dir=dataset_dir, scene="ecommerce", include_reviewed=True)
            self.assertEqual([case.query for case in cases], ["种子问题", "复核问题"])

    def test_dashboard_view_helpers_render_scene_metrics(self):
        summary = {
            "generated_at": "2026-06-23T00:00:00",
            "reviews": {"open": 2, "high_risk": 1},
            "samples": {"unlabeled": 3, "label_rate": 0.25},
            "datasets": {
                "seed_cases": 5,
                "reviewed_cases": 2,
                "total_cases": 7,
                "by_scene": {"ecommerce": {"seed_cases": 5, "reviewed_cases": 2, "total_cases": 7}},
            },
        }
        self.assertEqual(scene_dataset_stats(summary, "ecommerce")["reviewed_cases"], 2)
        fake_st = FakeStreamlit()

        import utils.production_dashboard_view as dashboard_view

        original_builder = dashboard_view.build_production_dashboard
        dashboard_view.build_production_dashboard = lambda: summary
        try:
            rendered = render_production_dashboard(fake_st, current_scene_id="ecommerce")
        finally:
            dashboard_view.build_production_dashboard = original_builder
        self.assertEqual(rendered, summary)
        self.assertIn(("metric", "待复核", 2), fake_st.calls)
        self.assertTrue(any(call[0] == "table" for call in fake_st.calls))


class RagContextFormattingTests(unittest.TestCase):
    def test_format_rag_context_adds_source_and_reference_number(self):
        docs = [SimpleNamespace(page_content="退货需保留退货凭证。", metadata={"source": "policy.txt"})]
        context = format_rag_context(docs)
        self.assertIn("【参考资料1】", context)
        self.assertIn("来源：policy.txt", context)
        self.assertIn("退货需保留退货凭证。", context)

    def test_format_rag_context_skips_empty_docs(self):
        docs = [SimpleNamespace(page_content="   ", metadata={"source": "empty.txt"})]
        self.assertEqual(format_rag_context(docs), "")

    def test_no_evidence_response_is_stable(self):
        self.assertIn("没有检索到足够相关的资料", NO_EVIDENCE_RESPONSE)


class EvalPipelineTests(unittest.TestCase):
    def test_build_stages_without_external(self):
        stages = build_stages(include_external=False)
        self.assertEqual([stage.name for stage in stages], [
            "clean_knowledge",
            "build_focused_knowledge",
            "keyword_baseline",
            "retrieval_baseline",
        ])
        self.assertTrue(all(stage.optional_env is None for stage in stages))
        self.assertIn("--include-reviewed", stages[2].command)
        self.assertIn("--include-reviewed", stages[3].command)

    def test_build_stages_with_answer_limit(self):
        gate = QualityGateConfig(min_answer_keyword_coverage=0.7, min_answer_citation_rate=0.6, max_answer_unsupported_risk=0.1)
        stages = build_stages(include_external=True, answer_limit=2, gate=gate)
        self.assertEqual(stages[-2].name, "generate_agent_answers")
        self.assertEqual(stages[-2].optional_env, "DASHSCOPE_API_KEY")
        self.assertIn("--limit", stages[-2].command)
        self.assertIn("2", stages[-2].command)
        self.assertIn(str(PIPELINE_PREDICTIONS), stages[-2].command)
        self.assertEqual(stages[-1].name, "answer_quality")
        self.assertEqual(stages[-1].optional_file, PIPELINE_PREDICTIONS)
        self.assertIn("0.7", stages[-1].command)
        self.assertIn("0.6", stages[-1].command)
        self.assertIn("0.1", stages[-1].command)

    def test_run_pipeline_dry_run(self):
        stages = build_stages(include_external=False)
        self.assertEqual(run_pipeline(stages, dry_run=True), 0)


class ApiServerTests(unittest.TestCase):
    def test_create_app_exposes_core_routes(self):
        app = create_app()
        routes = {route.path for route in app.routes}
        self.assertIn("/api/scenes", routes)
        self.assertIn("/api/dashboard", routes)
        self.assertIn("/api/chat", routes)


class PreflightTests(unittest.TestCase):
    def test_build_preflight_stages_defaults_to_no_external_eval(self):
        stages = build_preflight_stages()
        self.assertEqual([stage.name for stage in stages], ["unit_tests", "compileall", "quality_dashboard", "eval_pipeline"])
        self.assertIn("--no-external", stages[-1].command)

    def test_build_preflight_stages_can_skip_tests_and_include_external(self):
        stages = build_preflight_stages(include_external=True, skip_tests=True)
        self.assertEqual([stage.name for stage in stages], ["compileall", "quality_dashboard", "eval_pipeline"])
        self.assertNotIn("--no-external", stages[-1].command)

    def test_secret_scan_detects_token_like_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "secret.txt"
            fake_token = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
            path.write_text(f"token={fake_token}\n", encoding="utf-8")
            findings = scan_file_for_secrets(path)
            self.assertTrue(findings)

    def test_should_scan_skips_compiled_files(self):
        import scripts.run_preflight as preflight

        original_root = preflight.ROOT
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preflight.ROOT = root
            try:
                self.assertFalse(should_scan(root / "module.pyc"))
                text_path = root / "README.md"
                text_path.write_text("ok", encoding="utf-8")
                self.assertTrue(should_scan(text_path))
            finally:
                preflight.ROOT = original_root


if __name__ == "__main__":
    unittest.main()

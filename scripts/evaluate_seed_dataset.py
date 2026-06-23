"""Run a lightweight offline baseline for seed evaluation datasets.

This runner does not call LLMs or external embedding services. It checks whether
collected scene knowledge files contain the expected evidence for each seed query.
The output is a deterministic data-coverage baseline before introducing Ark/Seed
judge models and full Agent execution.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "eval" / "datasets"
REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
SCENE_KNOWLEDGE_FILE = "public_knowledge_seed.txt"


@dataclass(frozen=True)
class EvalCase:
    scene: str
    query: str
    expected_keywords: list[str]
    source_hint: str = ""


@dataclass(frozen=True)
class CaseResult:
    scene: str
    query: str
    expected_keywords: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    coverage: float
    corpus_chars: int
    snippet: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def load_jsonl(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw: dict[str, Any] = json.loads(line)
                cases.append(
                    EvalCase(
                        scene=str(raw["scene"]),
                        query=str(raw["query"]),
                        expected_keywords=[str(keyword) for keyword in raw.get("expected_keywords", [])],
                        source_hint=str(raw.get("source_hint", "")),
                    )
                )
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSONL case in {path}:{line_no}: {exc}") from exc
    return cases


def discover_dataset_paths(
    dataset_dir: Path = DATASET_DIR,
    include_reviewed: bool = False,
    extra_paths: Iterable[Path] | None = None,
) -> list[Path]:
    """Return evaluation dataset files in deterministic order.

    Seed datasets remain the default baseline. Reviewed datasets are opt-in so
    unit tests and one-off local checks can still evaluate only the curated seed
    set, while the full pipeline can include human-reviewed regression cases.
    """
    paths = list(sorted(dataset_dir.glob("*_seed.jsonl")))
    if include_reviewed:
        paths.extend(sorted(dataset_dir.glob("*_reviewed.jsonl")))
    if extra_paths:
        paths.extend(Path(path) for path in extra_paths)
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        unique_paths.append(path)
    return unique_paths


def load_cases(
    dataset_dir: Path = DATASET_DIR,
    scene: str | None = None,
    include_reviewed: bool = False,
    extra_paths: Iterable[Path] | None = None,
) -> list[EvalCase]:
    paths = discover_dataset_paths(dataset_dir=dataset_dir, include_reviewed=include_reviewed, extra_paths=extra_paths)
    cases: list[EvalCase] = []
    for path in paths:
        file_cases = load_jsonl(path)
        cases.extend(case for case in file_cases if scene is None or case.scene == scene)
    return cases


def load_scene_corpus(scene: str) -> str:
    scene_dir = PROJECT_ROOT / "data" / scene
    if not scene_dir.exists():
        return ""
    parts: list[str] = []
    for path in sorted(scene_dir.glob("*.txt")):
        try:
            parts.append(f"# 文件：{path.name}\n" + path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n\n---\n\n".join(parts)


def find_snippet(corpus: str, keywords: Iterable[str], max_chars: int = 240) -> str:
    if not corpus:
        return ""
    for keyword in keywords:
        if not keyword:
            continue
        index = corpus.find(keyword)
        if index >= 0:
            start = max(index - max_chars // 3, 0)
            end = min(start + max_chars, len(corpus))
            return corpus[start:end].replace("\n", " ").strip()
    return corpus[:max_chars].replace("\n", " ").strip()


def evaluate_case(case: EvalCase, corpus: str) -> CaseResult:
    normalized_corpus = normalize_text(corpus)
    matched: list[str] = []
    missing: list[str] = []
    for keyword in case.expected_keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword and normalized_keyword in normalized_corpus:
            matched.append(keyword)
        else:
            missing.append(keyword)
    coverage = len(matched) / len(case.expected_keywords) if case.expected_keywords else 0.0
    return CaseResult(
        scene=case.scene,
        query=case.query,
        expected_keywords=case.expected_keywords,
        matched_keywords=matched,
        missing_keywords=missing,
        coverage=round(coverage, 4),
        corpus_chars=len(corpus),
        snippet=find_snippet(corpus, matched or case.expected_keywords),
    )


def evaluate_cases(cases: Iterable[EvalCase]) -> list[CaseResult]:
    corpus_cache: dict[str, str] = {}
    results: list[CaseResult] = []
    for case in cases:
        corpus = corpus_cache.setdefault(case.scene, load_scene_corpus(case.scene))
        results.append(evaluate_case(case, corpus))
    return results


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    avg = sum(result.coverage for result in results) / total if total else 0.0
    by_scene: dict[str, dict[str, Any]] = {}
    for result in results:
        scene_stats = by_scene.setdefault(result.scene, {"cases": 0, "avg_coverage": 0.0, "full_match": 0})
        scene_stats["cases"] += 1
        scene_stats["avg_coverage"] += result.coverage
        if result.coverage >= 1.0:
            scene_stats["full_match"] += 1
    for scene_stats in by_scene.values():
        scene_stats["avg_coverage"] = round(scene_stats["avg_coverage"] / scene_stats["cases"], 4)
    return {"total_cases": total, "avg_coverage": round(avg, 4), "by_scene": by_scene}


def write_reports(results: list[CaseResult], output_dir: Path = REPORT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"keyword_baseline_{timestamp}.json"
    md_path = output_dir / f"keyword_baseline_{timestamp}.md"

    payload = {"summary": summarize(results), "results": [asdict(result) for result in results]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 关键词覆盖基线评测报告",
        "",
        f"生成时间：{timestamp}",
        "",
        "## 汇总",
        "",
        f"- 用例数：{payload['summary']['total_cases']}",
        f"- 平均关键词覆盖率：{payload['summary']['avg_coverage']:.2%}",
        "",
        "| 场景 | 用例数 | 平均覆盖率 | 全量命中用例 |",
        "|---|---:|---:|---:|",
    ]
    for scene, stats in sorted(payload["summary"]["by_scene"].items()):
        lines.append(
            f"| {scene} | {stats['cases']} | {stats['avg_coverage']:.2%} | {stats['full_match']} |"
        )
    lines.extend(["", "## 未完全覆盖用例", ""])
    partials = [result for result in results if result.coverage < 1.0]
    if not partials:
        lines.append("全部用例关键词均已在当前场景语料中覆盖。")
    else:
        for result in partials:
            lines.extend(
                [
                    f"### {result.scene}｜{result.query}",
                    f"- 覆盖率：{result.coverage:.2%}",
                    f"- 已命中：{', '.join(result.matched_keywords) or '无'}",
                    f"- 未命中：{', '.join(result.missing_keywords) or '无'}",
                    f"- 片段：{result.snippet or '无'}",
                    "",
                ]
            )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def check_thresholds(summary: dict[str, Any], min_avg_coverage: float = 0.0) -> list[str]:
    failures: list[str] = []
    if summary["avg_coverage"] < min_avg_coverage:
        failures.append(
            f"avg_coverage {summary['avg_coverage']:.2%} < required {min_avg_coverage:.2%}"
        )
    return failures



def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline keyword baseline for seed and optional reviewed datasets.")
    parser.add_argument("--scene", help="Only evaluate one scene")
    parser.add_argument("--include-reviewed", action="store_true", help="Also load eval/datasets/*_reviewed.jsonl regression cases")
    parser.add_argument(
        "--extra-dataset",
        action="append",
        type=Path,
        default=[],
        help="Additional JSONL dataset path to include; can be repeated",
    )
    parser.add_argument("--min-avg-coverage", type=float, default=0.0, help="Fail when average keyword coverage is below this threshold")
    args = parser.parse_args()

    cases = load_cases(scene=args.scene, include_reviewed=args.include_reviewed, extra_paths=args.extra_dataset)
    if not cases:
        print("No evaluation cases found.")
        return 1
    results = evaluate_cases(cases)
    json_path, md_path = write_reports(results)
    summary = summarize(results)
    print(f"[baseline] cases={summary['total_cases']} avg_coverage={summary['avg_coverage']:.2%}")
    print(f"[report] {json_path}")
    print(f"[report] {md_path}")
    failures = check_thresholds(summary, min_avg_coverage=args.min_avg_coverage)
    if failures:
        for failure in failures:
            print(f"[quality-gate][failed] {failure}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

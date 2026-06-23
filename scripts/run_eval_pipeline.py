"""Run the project evaluation pipeline with safe optional external steps.

Pipeline stages:
1. clean collected knowledge
2. build focused knowledge
3. keyword coverage baseline with quality gate
4. local lexical retrieval baseline with quality gate
5. optional Chroma/DashScope baseline
6. optional Agent answer generation
7. optional Agent answer quality evaluation for generated predictions

External-key dependent stages are safe: they skip when corresponding env vars are
missing. This script is intended as the one-command quality gate before changing
RAG prompts, chunking, tools or Agent workflow.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PIPELINE_PREDICTIONS = PROJECT_ROOT / "eval" / "predictions" / "pipeline_agent_answers.jsonl"


@dataclass(frozen=True)
class Stage:
    name: str
    command: list[str]
    optional_env: str | None = None
    optional_file: Path | None = None


@dataclass(frozen=True)
class QualityGateConfig:
    min_keyword_coverage: float = 1.0
    min_retrieval_hit_rate: float = 1.0
    min_retrieval_recall: float = 0.9
    min_answer_keyword_coverage: float = 0.6
    min_answer_citation_rate: float = 0.5
    max_answer_unsupported_risk: float = 0.2


def has_env(name: str | None) -> bool:
    return bool(name and (os.getenv(name) or "").strip())


def build_stages(
    include_external: bool = True,
    answer_limit: int | None = None,
    gate: QualityGateConfig | None = None,
) -> list[Stage]:
    gate = gate or QualityGateConfig()
    stages = [
        Stage("clean_knowledge", [PYTHON, "scripts/clean_knowledge_data.py"]),
        Stage("build_focused_knowledge", [PYTHON, "scripts/build_focused_knowledge.py"]),
        Stage(
            "keyword_baseline",
            [
                PYTHON,
                "scripts/evaluate_seed_dataset.py",
                "--include-reviewed",
                "--min-avg-coverage",
                str(gate.min_keyword_coverage),
            ],
        ),
        Stage(
            "retrieval_baseline",
            [
                PYTHON,
                "scripts/evaluate_retrieval_baseline.py",
                "--include-reviewed",
                "--min-hit-rate",
                str(gate.min_retrieval_hit_rate),
                "--min-avg-keyword-recall",
                str(gate.min_retrieval_recall),
            ],
        ),
    ]
    if include_external:
        stages.append(Stage("chroma_baseline", [PYTHON, "scripts/evaluate_chroma_baseline.py"], optional_env="DASHSCOPE_API_KEY"))
        answer_cmd = [PYTHON, "scripts/generate_agent_answers.py", "--output", str(PIPELINE_PREDICTIONS)]
        if answer_limit is not None:
            answer_cmd.extend(["--limit", str(answer_limit)])
        stages.append(Stage("generate_agent_answers", answer_cmd, optional_env="DASHSCOPE_API_KEY"))
        stages.append(
            Stage(
                "answer_quality",
                [
                    PYTHON,
                    "scripts/evaluate_answers_with_ark.py",
                    str(PIPELINE_PREDICTIONS),
                    "--min-keyword-coverage",
                    str(gate.min_answer_keyword_coverage),
                    "--min-citation-rate",
                    str(gate.min_answer_citation_rate),
                    "--max-unsupported-risk-rate",
                    str(gate.max_answer_unsupported_risk),
                ],
                optional_file=PIPELINE_PREDICTIONS,
            )
        )
    return stages


def run_stage(stage: Stage, dry_run: bool = False) -> int:
    if stage.optional_env and not has_env(stage.optional_env):
        print(f"[pipeline][skip] {stage.name}: {stage.optional_env} is not set")
        return 0
    if stage.optional_file and not stage.optional_file.exists():
        print(f"[pipeline][skip] {stage.name}: {stage.optional_file} does not exist")
        return 0
    printable = " ".join(stage.command)
    if dry_run:
        print(f"[pipeline][dry-run] {stage.name}: {printable}")
        return 0
    print(f"[pipeline][run] {stage.name}: {printable}")
    completed = subprocess.run(stage.command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        print(f"[pipeline][failed] {stage.name}: exit={completed.returncode}", file=sys.stderr)
    return completed.returncode


def run_pipeline(stages: list[Stage], dry_run: bool = False) -> int:
    for stage in stages:
        code = run_stage(stage, dry_run=dry_run)
        if code != 0:
            return code
    print("[pipeline][done] all stages completed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run data/RAG/Agent evaluation pipeline.")
    parser.add_argument("--no-external", action="store_true", help="Skip DashScope/Ark dependent stages")
    parser.add_argument("--answer-limit", type=int, default=5, help="Limit Agent answer generation when enabled")
    parser.add_argument("--dry-run", action="store_true", help="Print stages without executing")
    parser.add_argument("--min-keyword-coverage", type=float, default=1.0, help="Gate for offline keyword coverage")
    parser.add_argument("--min-retrieval-hit-rate", type=float, default=1.0, help="Gate for local retrieval Top-K hit rate")
    parser.add_argument("--min-retrieval-recall", type=float, default=0.9, help="Gate for local retrieval average keyword recall")
    parser.add_argument("--min-answer-keyword-coverage", type=float, default=0.6, help="Gate for generated-answer keyword coverage")
    parser.add_argument("--min-answer-citation-rate", type=float, default=0.5, help="Gate for generated-answer citation rate")
    parser.add_argument("--max-answer-unsupported-risk", type=float, default=0.2, help="Gate for generated-answer unsupported risk rate")
    args = parser.parse_args()

    gate = QualityGateConfig(
        min_keyword_coverage=args.min_keyword_coverage,
        min_retrieval_hit_rate=args.min_retrieval_hit_rate,
        min_retrieval_recall=args.min_retrieval_recall,
        min_answer_keyword_coverage=args.min_answer_keyword_coverage,
        min_answer_citation_rate=args.min_answer_citation_rate,
        max_answer_unsupported_risk=args.max_answer_unsupported_risk,
    )
    stages = build_stages(include_external=not args.no_external, answer_limit=args.answer_limit, gate=gate)
    return run_pipeline(stages, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

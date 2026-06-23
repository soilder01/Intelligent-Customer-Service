#!/usr/bin/env python3
"""Run local preflight checks before committing Agent platform changes.

The preflight is intentionally deterministic by default: it runs unit tests,
Python compilation, the no-external evaluation pipeline, the production dashboard
and a lightweight secret scan. Optional external evaluation stages can be enabled
explicitly when API keys are configured in the environment.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SCAN_EXCLUDED_PARTS = {".git", "__pycache__", "logs", "reports", "node_modules", "dist"}
SCAN_EXCLUDED_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".pdf", ".sqlite3"}
SENSITIVE_TOKEN_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
]


@dataclass(frozen=True)
class PreflightStage:
    name: str
    command: list[str]


def build_preflight_stages(include_external: bool = False, skip_tests: bool = False) -> list[PreflightStage]:
    stages: list[PreflightStage] = []
    if not skip_tests:
        stages.append(PreflightStage("unit_tests", [PYTHON, "-m", "unittest", "discover", "-s", "tests"]))
    stages.extend(
        [
            PreflightStage("compileall", [PYTHON, "-m", "compileall", "scripts", "tests", "agent", "utils", "rag", "model", "api", "app.py"]),
            PreflightStage("quality_dashboard", [PYTHON, "scripts/inspect_production_loop.py", "dashboard"]),
            PreflightStage(
                "eval_pipeline",
                [PYTHON, "scripts/run_eval_pipeline.py"] + ([] if include_external else ["--no-external"]),
            ),
        ]
    )
    return stages


def run_stage(stage: PreflightStage, dry_run: bool = False) -> int:
    printable = " ".join(stage.command)
    if dry_run:
        print(f"[preflight][dry-run] {stage.name}: {printable}")
        return 0
    print(f"[preflight][run] {stage.name}: {printable}")
    completed = subprocess.run(stage.command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        print(f"[preflight][failed] {stage.name}: exit={completed.returncode}", file=sys.stderr)
    return completed.returncode


def should_scan(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in SCAN_EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix.lower() in SCAN_EXCLUDED_SUFFIXES:
        return False
    if not path.is_file():
        return False
    return True


def iter_scan_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if should_scan(path):
            yield path


def scan_file_for_secrets(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in SENSITIVE_TOKEN_PATTERNS:
            if pattern.search(line):
                try:
                    display_path = path.relative_to(ROOT)
                except ValueError:
                    display_path = path
                findings.append(f"{display_path}:{line_no}: token-like secret matched {pattern.pattern}")
    return findings


def run_secret_scan() -> int:
    findings: list[str] = []
    for path in iter_scan_files():
        findings.extend(scan_file_for_secrets(path))
    if findings:
        print("[preflight][failed] secret_scan found token-like secrets", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        return 2
    print("[preflight][ok] secret_scan: no token-like secrets found")
    return 0


def run_preflight(stages: list[PreflightStage], dry_run: bool = False, skip_secret_scan: bool = False) -> int:
    for stage in stages:
        code = run_stage(stage, dry_run=dry_run)
        if code != 0:
            return code
    if not skip_secret_scan:
        if dry_run:
            print("[preflight][dry-run] secret_scan")
        else:
            code = run_secret_scan()
            if code != 0:
                return code
    print("[preflight][done] all checks passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local preflight checks before commit/MR.")
    parser.add_argument("--include-external", action="store_true", help="Allow DashScope/Ark dependent evaluation stages when keys are configured")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unit tests for a faster local check")
    parser.add_argument("--skip-secret-scan", action="store_true", help="Skip token-like secret scan")
    parser.add_argument("--dry-run", action="store_true", help="Print checks without executing them")
    args = parser.parse_args()

    stages = build_preflight_stages(include_external=args.include_external, skip_tests=args.skip_tests)
    return run_preflight(stages, dry_run=args.dry_run, skip_secret_scan=args.skip_secret_scan)


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate Agent answers for seed evaluation datasets.

The script exercises the current ReactAgent without Streamlit. It is safe by
default: if DASHSCOPE_API_KEY is not set, it exits with code 0 and prints a skip
message. Generated answers can then be judged by evaluate_answers_with_ark.py.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from evaluate_seed_dataset import EvalCase, load_cases
except ModuleNotFoundError:
    from scripts.evaluate_seed_dataset import EvalCase, load_cases

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREDICTION_DIR = PROJECT_ROOT / "eval" / "predictions"


def has_dashscope_key() -> bool:
    return bool((os.getenv("DASHSCOPE_API_KEY") or "").strip())


def answer_case(case: EvalCase) -> dict[str, Any]:
    from utils.config_handler import get_scene_by_id
    from agent.react_agent import ReactAgent

    scene_config = get_scene_by_id(case.scene)
    if not scene_config:
        raise ValueError(f"Unknown scene: {case.scene}")
    agent = ReactAgent(scene_config=scene_config)
    answer = "".join(agent.execute_stream(case.query))
    return {
        "scene": case.scene,
        "query": case.query,
        "answer": answer,
        "expected_keywords": case.expected_keywords,
        "source_hint": case.source_hint,
    }


def write_predictions(records: list[dict[str, Any]], output_dir: Path = PREDICTION_DIR, output_path: Path | None = None) -> Path:
    if output_path is None:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"agent_answers_{timestamp}.jsonl"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Agent answers for seed eval datasets.")
    parser.add_argument("--scene", help="Only answer one scene")
    parser.add_argument("--limit", type=int, help="Limit number of cases for smoke testing")
    parser.add_argument("--output", type=Path, help="Write predictions to this JSONL path")
    args = parser.parse_args()

    if not has_dashscope_key():
        print("[skip] DASHSCOPE_API_KEY is not set; skip Agent answer generation.")
        return 0

    cases = load_cases(scene=args.scene)
    if args.limit is not None:
        cases = cases[: args.limit]
    records = [answer_case(case) for case in cases]
    output_path = write_predictions(records, output_path=args.output)
    print(f"[answers] cases={len(records)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

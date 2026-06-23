#!/usr/bin/env python3
"""Inspect persisted Agent task runs.

Examples:
  python scripts/inspect_task_runs.py list --limit 5
  python scripts/inspect_task_runs.py show 1782181405000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.task_store import format_task_run_markdown, list_recent_task_runs, load_task_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect persisted Agent task runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent task runs")
    list_parser.add_argument("--limit", type=int, default=10)
    list_parser.add_argument("--scene", default=None)
    list_parser.add_argument("--json", action="store_true", help="Output JSON instead of a table")

    show_parser = subparsers.add_parser("show", help="Show one task run")
    show_parser.add_argument("task_id")
    show_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.command == "list":
        records = list_recent_task_runs(limit=args.limit, scene=args.scene)
        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return 0
        if not records:
            print("No task runs found.")
            return 0
        for record in records:
            print(
                f"{record.get('updated_at', '')}\t{record.get('task_id', '')}\t"
                f"{record.get('scene', '')}\t{record.get('status', '')}\t{record.get('query', '')}"
            )
        return 0

    if args.command == "show":
        record = load_task_run(args.task_id)
        if not record:
            print(f"Task run not found: {args.task_id}")
            return 1
        if args.json:
            print(json.dumps(record, ensure_ascii=False, indent=2))
        else:
            print(format_task_run_markdown(record))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

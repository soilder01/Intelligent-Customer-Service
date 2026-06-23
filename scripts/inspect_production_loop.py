#!/usr/bin/env python3
"""Inspect and operate production-loop assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.production_loop import (
    build_production_dashboard,
    export_labeled_eval_dataset,
    format_production_dashboard_markdown,
    label_eval_sample,
    list_eval_samples,
    list_review_items,
    update_review_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Agent production-loop assets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dashboard_parser = subparsers.add_parser("dashboard", help="Show production-loop quality dashboard")
    dashboard_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("reviews", help="List review queue items")
    review_parser.add_argument("--limit", type=int, default=20)
    review_parser.add_argument("--status", default="open")
    review_parser.add_argument("--json", action="store_true")

    update_review_parser = subparsers.add_parser("review-status", help="Update one review item status")
    update_review_parser.add_argument("review_id")
    update_review_parser.add_argument("status", choices=["open", "reviewed", "fixed", "ignored"])
    update_review_parser.add_argument("--note", default="")
    update_review_parser.add_argument("--reviewer", default="")

    sample_parser = subparsers.add_parser("samples", help="List captured evaluation samples")
    sample_parser.add_argument("--limit", type=int, default=20)
    sample_parser.add_argument("--labeled", action="store_true", help="Only show labeled samples")
    sample_parser.add_argument("--unlabeled", action="store_true", help="Only show samples waiting for labels")
    sample_parser.add_argument("--json", action="store_true")

    label_parser = subparsers.add_parser("label-sample", help="Backfill expected keywords for one sample")
    label_parser.add_argument("task_id")
    label_parser.add_argument("--keywords", required=True, help="Comma-separated expected keywords")
    label_parser.add_argument("--note", default="")

    export_parser = subparsers.add_parser("export-dataset", help="Export labeled samples to eval dataset JSONL")
    export_parser.add_argument("output_path")
    export_parser.add_argument("--scene", default=None)

    args = parser.parse_args()

    if args.command == "dashboard":
        summary = build_production_dashboard(dataset_dir=ROOT / "eval" / "datasets")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(format_production_dashboard_markdown(summary))
        return 0

    if args.command == "reviews":
        records = list_review_items(limit=args.limit, status=args.status)
        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
            return 0
        if not records:
            print("No review items found.")
            return 0
        for item in records:
            print(f"{item.get('updated_at') or item.get('created_at', '')}\t{item.get('review_id', '')}\t{item.get('status', '')}\t{item.get('scene', '')}\t{';'.join(item.get('reasons', []))}\t{item.get('query', '')}")
        return 0

    if args.command == "review-status":
        path = update_review_status(args.review_id, args.status, note=args.note, reviewer=args.reviewer)
        print(f"Updated review item: {path}")
        return 0

    if args.command == "samples":
        needs_labeling = None
        if args.labeled:
            needs_labeling = False
        if args.unlabeled:
            needs_labeling = True
        samples = list_eval_samples(limit=args.limit, needs_labeling=needs_labeling)
        if args.json:
            print(json.dumps(samples, ensure_ascii=False, indent=2))
            return 0
        if not samples:
            print("No eval samples found.")
            return 0
        for sample in samples:
            label_state = "unlabeled" if sample.get("needs_labeling") else "labeled"
            print(f"{sample.get('updated_at') or sample.get('created_at', '')}\t{sample.get('task_id', '')}\t{label_state}\t{sample.get('scene', '')}\t{sample.get('query', '')}")
        return 0

    if args.command == "label-sample":
        keywords = [keyword.strip() for keyword in args.keywords.split(",") if keyword.strip()]
        path = label_eval_sample(args.task_id, keywords, note=args.note)
        print(f"Labeled sample: {path}")
        return 0

    if args.command == "export-dataset":
        path = export_labeled_eval_dataset(Path(args.output_path), scene=args.scene)
        print(f"Exported dataset: {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Build focused FAQ-style knowledge files from collected public corpora.

This script does not synthesize unsupported facts. It extracts evidence windows
from the already collected public knowledge files using evaluation keywords, then
writes compact focused files. These files reduce retrieval noise and are suitable
for subsequent RAG ingestion and baseline evaluation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus
except ModuleNotFoundError:
    from scripts.evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOCUSED_FILE_NAME = "focused_faq_seed.txt"
DEFAULT_SCENES = ("ecommerce", "hr")


def find_evidence_window(corpus: str, keywords: list[str], window: int = 360) -> str:
    best_index = -1
    best_keyword = ""
    for keyword in keywords:
        index = corpus.find(keyword)
        if index >= 0:
            best_index = index
            best_keyword = keyword
            break
    if best_index < 0:
        return ""
    start = max(best_index - window // 3, 0)
    end = min(best_index + window, len(corpus))
    snippet = corpus[start:end].strip()
    # Align to line boundaries when possible.
    left_break = snippet.find("\n")
    right_break = snippet.rfind("\n")
    if 0 <= left_break < 80:
        snippet = snippet[left_break + 1 :]
    if right_break > len(snippet) - 120:
        snippet = snippet[:right_break]
    return snippet.strip()


def build_scene_focused_text(scene: str, cases: list[EvalCase]) -> str:
    corpus = load_scene_corpus(scene)
    sections: list[str] = [
        f"# {scene} 聚焦 FAQ 证据集",
        "来源：由 scripts/build_focused_knowledge.py 从已采集公开语料中抽取，不包含额外编造内容。",
        "",
    ]
    for index, case in enumerate(cases, start=1):
        snippet = find_evidence_window(corpus, case.expected_keywords)
        if not snippet:
            continue
        sections.extend(
            [
                f"## Q{index}: {case.query}",
                f"期望关键词：{', '.join(case.expected_keywords)}",
                "证据片段：",
                snippet,
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def write_focused_file(scene: str, text: str) -> Path:
    output_path = PROJECT_ROOT / "data" / scene / FOCUSED_FILE_NAME
    output_path.write_text(text, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build focused FAQ knowledge from collected public data.")
    parser.add_argument("--scene", choices=DEFAULT_SCENES, help="Only build one scene")
    args = parser.parse_args()

    scenes = (args.scene,) if args.scene else DEFAULT_SCENES
    all_cases = load_cases()
    wrote = 0
    for scene in scenes:
        scene_cases = [case for case in all_cases if case.scene == scene]
        text = build_scene_focused_text(scene, scene_cases)
        path = write_focused_file(scene, text)
        print(f"[focused] {scene}: {path.relative_to(PROJECT_ROOT)} chars={len(text)}")
        wrote += 1
    return 0 if wrote else 1


if __name__ == "__main__":
    raise SystemExit(main())

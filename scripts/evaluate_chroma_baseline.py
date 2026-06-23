"""Run a real Chroma/DashScope retrieval baseline for seed datasets.

This script validates the actual vector retrieval path used by the project. It is
safe by default: if DASHSCOPE_API_KEY is not configured, it exits with code 0 and
prints a skip message instead of failing CI or leaking secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus, normalize_text
except ModuleNotFoundError:
    from scripts.evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus, normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
DEFAULT_TOP_K = 5
DEFAULT_CHUNK_SIZE = 450
DEFAULT_CHUNK_OVERLAP = 80
DEFAULT_EMBEDDING_MODEL = "text-embedding-v4"


@dataclass(frozen=True)
class ChromaRetrievedDoc:
    rank: int
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ChromaCaseResult:
    scene: str
    query: str
    expected_keywords: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    keyword_recall: float
    hit: bool
    retrieved: list[ChromaRetrievedDoc]


def has_dashscope_key() -> bool:
    return bool((os.getenv("DASHSCOPE_API_KEY") or "").strip())


def split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    chunks: list[str] = []
    buffer = ""
    for line in lines:
        if not buffer:
            buffer = line
            continue
        if len(buffer) + 1 + len(line) <= chunk_size:
            buffer = f"{buffer}\n{line}"
        else:
            chunks.append(buffer)
            tail = buffer[-overlap:] if overlap else ""
            buffer = f"{tail}\n{line}" if tail else line
    if buffer:
        chunks.append(buffer)
    return chunks


def build_documents(scene: str, corpus: str, chunk_size: int, overlap: int):
    from langchain_core.documents import Document

    return [
        Document(page_content=chunk, metadata={"scene": scene, "chunk_index": index})
        for index, chunk in enumerate(split_text(corpus, chunk_size=chunk_size, overlap=overlap))
    ]


def evaluate_case(case: EvalCase, docs: list[Any], top_k: int) -> ChromaCaseResult:
    joined = "\n".join(doc.page_content for doc in docs)
    normalized_joined = normalize_text(joined)
    matched = [keyword for keyword in case.expected_keywords if normalize_text(keyword) in normalized_joined]
    missing = [keyword for keyword in case.expected_keywords if keyword not in matched]
    recall = len(matched) / len(case.expected_keywords) if case.expected_keywords else 0.0
    return ChromaCaseResult(
        scene=case.scene,
        query=case.query,
        expected_keywords=case.expected_keywords,
        matched_keywords=matched,
        missing_keywords=missing,
        keyword_recall=round(recall, 4),
        hit=bool(matched),
        retrieved=[
            ChromaRetrievedDoc(rank=index + 1, content=doc.page_content[:500], metadata=dict(doc.metadata))
            for index, doc in enumerate(docs[:top_k])
        ],
    )


def summarize(results: list[ChromaCaseResult]) -> dict[str, Any]:
    total = len(results)
    hit_rate = sum(1 for result in results if result.hit) / total if total else 0.0
    avg_recall = sum(result.keyword_recall for result in results) / total if total else 0.0
    by_scene: dict[str, dict[str, Any]] = {}
    for result in results:
        stats = by_scene.setdefault(result.scene, {"cases": 0, "hit_cases": 0, "avg_keyword_recall": 0.0, "full_recall_cases": 0})
        stats["cases"] += 1
        stats["hit_cases"] += int(result.hit)
        stats["avg_keyword_recall"] += result.keyword_recall
        stats["full_recall_cases"] += int(result.keyword_recall >= 1.0)
    for stats in by_scene.values():
        stats["hit_rate"] = round(stats["hit_cases"] / stats["cases"], 4)
        stats["avg_keyword_recall"] = round(stats["avg_keyword_recall"] / stats["cases"], 4)
    return {"total_cases": total, "hit_rate": round(hit_rate, 4), "avg_keyword_recall": round(avg_recall, 4), "by_scene": by_scene}


def run_chroma_baseline(cases: list[EvalCase], top_k: int, chunk_size: int, overlap: int, embedding_model: str) -> list[ChromaCaseResult]:
    from langchain_chroma import Chroma
    from langchain_community.embeddings import DashScopeEmbeddings

    embedding = DashScopeEmbeddings(model=embedding_model)
    grouped_cases: dict[str, list[EvalCase]] = {}
    for case in cases:
        grouped_cases.setdefault(case.scene, []).append(case)

    results: list[ChromaCaseResult] = []
    with tempfile.TemporaryDirectory(prefix="ics_chroma_eval_") as temp_dir:
        for scene, scene_cases in grouped_cases.items():
            corpus = load_scene_corpus(scene)
            documents = build_documents(scene, corpus, chunk_size=chunk_size, overlap=overlap)
            if not documents:
                continue
            store = Chroma.from_documents(
                documents=documents,
                embedding=embedding,
                collection_name=f"eval_{scene}",
                persist_directory=str(Path(temp_dir) / scene),
            )
            for case in scene_cases:
                docs = store.similarity_search(case.query, k=top_k)
                results.append(evaluate_case(case, docs, top_k=top_k))
    return results


def write_reports(results: list[ChromaCaseResult], output_dir: Path = REPORT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"chroma_baseline_{timestamp}.json"
    md_path = output_dir / f"chroma_baseline_{timestamp}.md"
    payload = {"summary": summarize(results), "results": [asdict(result) for result in results]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Chroma 向量检索基线评测报告",
        "",
        f"生成时间：{timestamp}",
        "",
        f"- 用例数：{payload['summary']['total_cases']}",
        f"- Top-K 命中率：{payload['summary']['hit_rate']:.2%}",
        f"- 平均关键词召回率：{payload['summary']['avg_keyword_recall']:.2%}",
        "",
        "| 场景 | 用例数 | Top-K 命中率 | 平均关键词召回率 | 全关键词召回用例 |",
        "|---|---:|---:|---:|---:|",
    ]
    for scene, stats in sorted(payload["summary"]["by_scene"].items()):
        lines.append(f"| {scene} | {stats['cases']} | {stats['hit_rate']:.2%} | {stats['avg_keyword_recall']:.2%} | {stats['full_recall_cases']} |")
    lines.extend(["", "## 未完全召回用例", ""])
    partials = [result for result in results if result.keyword_recall < 1.0]
    if not partials:
        lines.append("全部用例均在 Chroma Top-K 检索片段中召回全部期望关键词。")
    else:
        for result in partials:
            top = result.retrieved[0] if result.retrieved else None
            lines.extend([
                f"### {result.scene}｜{result.query}",
                f"- 关键词召回率：{result.keyword_recall:.2%}",
                f"- 已召回：{', '.join(result.matched_keywords) or '无'}",
                f"- 未召回：{', '.join(result.missing_keywords) or '无'}",
                f"- Top1 片段：{top.content[:240].replace(chr(10), ' ') if top else '无'}",
                "",
            ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Chroma/DashScope retrieval baseline.")
    parser.add_argument("--scene", help="Only evaluate one scene")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--embedding-model", default=os.getenv("DASHSCOPE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    args = parser.parse_args()

    if not has_dashscope_key():
        print("[skip] DASHSCOPE_API_KEY is not set; skip Chroma/DashScope retrieval baseline.")
        return 0

    cases = load_cases(scene=args.scene)
    if not cases:
        print("No evaluation cases found.")
        return 1
    results = run_chroma_baseline(cases, top_k=args.top_k, chunk_size=args.chunk_size, overlap=args.overlap, embedding_model=args.embedding_model)
    json_path, md_path = write_reports(results)
    summary = summarize(results)
    print(f"[chroma-baseline] cases={summary['total_cases']} hit_rate={summary['hit_rate']:.2%} avg_keyword_recall={summary['avg_keyword_recall']:.2%}")
    print(f"[report] {json_path}")
    print(f"[report] {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

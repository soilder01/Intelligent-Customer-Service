"""Run a local lexical RAG retrieval baseline.

This script evaluates whether a simple deterministic retriever can surface chunks
that contain the expected evidence for seed questions. It intentionally does not
call external embedding/LLM providers, so it can be used as a stable pre-flight
baseline before running Chroma/DashScope/Ark evaluations.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus, normalize_text
except ModuleNotFoundError:  # Allow importing from unit tests as scripts.evaluate_retrieval_baseline
    from scripts.evaluate_seed_dataset import EvalCase, load_cases, load_scene_corpus, normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
DEFAULT_CHUNK_SIZE = 450
DEFAULT_CHUNK_OVERLAP = 80
DEFAULT_TOP_K = 5

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class Chunk:
    scene: str
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class RetrievedChunk:
    index: int
    score: float
    matched_terms: list[str]
    text: str


@dataclass(frozen=True)
class RetrievalCaseResult:
    scene: str
    query: str
    expected_keywords: list[str]
    top_k: int
    retrieved: list[RetrievedChunk]
    matched_keywords: list[str]
    missing_keywords: list[str]
    keyword_recall: float
    hit: bool


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in TOKEN_RE.findall(text or ""):
        token = raw_token.lower().strip()
        if not token:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(token)
            tokens.extend(token[index : index + 2] for index in range(0, max(len(token) - 1, 0)))
            tokens.extend(token[index : index + 3] for index in range(0, max(len(token) - 2, 0)))
        else:
            tokens.append(token)
    return tokens


def chunk_text(scene: str, text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    paragraphs = [line.strip() for line in (text or "").splitlines() if line.strip()]
    chunks: list[Chunk] = []
    buffer = ""
    start = 0

    def append_buffer(content: str, start_pos: int) -> None:
        if content.strip():
            chunks.append(Chunk(scene=scene, index=len(chunks), text=content.strip(), start=start_pos, end=start_pos + len(content)))

    for paragraph in paragraphs:
        if not buffer:
            start = text.find(paragraph, start)
            buffer = paragraph
            continue
        if len(buffer) + 2 + len(paragraph) <= chunk_size:
            buffer = f"{buffer}\n\n{paragraph}"
        else:
            append_buffer(buffer, start)
            tail = buffer[-overlap:] if overlap else ""
            start = max(text.find(paragraph, start), 0)
            buffer = f"{tail}\n\n{paragraph}" if tail else paragraph

    append_buffer(buffer, start)

    # Split any oversized chunk by fixed window as fallback.
    normalized_chunks: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.text) <= chunk_size * 1.5:
            normalized_chunks.append(Chunk(scene, len(normalized_chunks), chunk.text, chunk.start, chunk.end))
            continue
        step = chunk_size - overlap
        for offset in range(0, len(chunk.text), step):
            piece = chunk.text[offset : offset + chunk_size]
            if piece.strip():
                normalized_chunks.append(
                    Chunk(scene, len(normalized_chunks), piece.strip(), chunk.start + offset, chunk.start + offset + len(piece))
                )
    return normalized_chunks


def score_chunk(query: str, chunk: Chunk, document_frequency: Counter[str], total_chunks: int) -> tuple[float, list[str]]:
    query_terms = sorted(set(tokenize(query)))
    if not query_terms:
        return 0.0, []
    chunk_terms = tokenize(chunk.text)
    chunk_counts = Counter(chunk_terms)
    matched_terms = [term for term in query_terms if chunk_counts.get(term, 0) > 0]
    if not matched_terms:
        return 0.0, []

    # BM25-style lexical score. This is intentionally deterministic and local,
    # giving more weight to discriminative terms and reducing short boilerplate wins.
    avg_len = 180.0
    k1 = 1.2
    b = 0.75
    chunk_len = max(len(chunk_terms), 1)
    score = 0.0
    for term in matched_terms:
        tf = chunk_counts[term]
        df = max(document_frequency.get(term, 0), 1)
        idf = max(0.1, math_log((total_chunks - df + 0.5) / (df + 0.5) + 1.0))
        denominator = tf + k1 * (1 - b + b * chunk_len / avg_len)
        score += idf * (tf * (k1 + 1)) / denominator

    normalized_query = normalize_text(query)
    normalized_chunk = normalize_text(chunk.text)
    if normalized_query[:8] and normalized_query[:8] in normalized_chunk:
        score += 0.5
    if any(normalize_text(term) in normalized_chunk for term in query_terms if len(term) >= 2):
        score += 0.2
    return round(score, 6), matched_terms


def math_log(value: float) -> float:
    # Small wrapper keeps imports explicit in tests and avoids leaking math usage elsewhere.
    import math

    return math.log(value)


def build_document_frequency(chunks: list[Chunk]) -> Counter[str]:
    df: Counter[str] = Counter()
    for chunk in chunks:
        df.update(set(tokenize(chunk.text)))
    return df


def retrieve(query: str, chunks: list[Chunk], top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
    scored: list[RetrievedChunk] = []
    document_frequency = build_document_frequency(chunks)
    total_chunks = max(len(chunks), 1)
    for chunk in chunks:
        score, matched_terms = score_chunk(query, chunk, document_frequency, total_chunks)
        if score > 0:
            scored.append(
                RetrievedChunk(
                    index=chunk.index,
                    score=score,
                    matched_terms=matched_terms,
                    text=chunk.text[:500],
                )
            )
    return sorted(scored, key=lambda item: score_sort_key(item), reverse=True)[:top_k]


def score_sort_key(item: RetrievedChunk) -> tuple[float, int]:
    return (item.score, len(item.matched_terms))


def evaluate_retrieval_case(case: EvalCase, chunks: list[Chunk], top_k: int = DEFAULT_TOP_K) -> RetrievalCaseResult:
    retrieved = retrieve(case.query, chunks, top_k=top_k)
    joined = "\n".join(item.text for item in retrieved)
    normalized_joined = normalize_text(joined)
    matched_keywords = [keyword for keyword in case.expected_keywords if normalize_text(keyword) in normalized_joined]
    missing_keywords = [keyword for keyword in case.expected_keywords if keyword not in matched_keywords]
    keyword_recall = len(matched_keywords) / len(case.expected_keywords) if case.expected_keywords else 0.0
    return RetrievalCaseResult(
        scene=case.scene,
        query=case.query,
        expected_keywords=case.expected_keywords,
        top_k=top_k,
        retrieved=retrieved,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        keyword_recall=round(keyword_recall, 4),
        hit=bool(matched_keywords),
    )


def evaluate_cases(cases: Iterable[EvalCase], chunk_size: int, overlap: int, top_k: int) -> list[RetrievalCaseResult]:
    chunk_cache: dict[str, list[Chunk]] = {}
    results: list[RetrievalCaseResult] = []
    for case in cases:
        if case.scene not in chunk_cache:
            chunk_cache[case.scene] = chunk_text(case.scene, load_scene_corpus(case.scene), chunk_size=chunk_size, overlap=overlap)
        results.append(evaluate_retrieval_case(case, chunk_cache[case.scene], top_k=top_k))
    return results


def summarize(results: list[RetrievalCaseResult]) -> dict[str, Any]:
    total = len(results)
    avg_recall = sum(result.keyword_recall for result in results) / total if total else 0.0
    hit_rate = sum(1 for result in results if result.hit) / total if total else 0.0
    full_recall = sum(1 for result in results if result.keyword_recall >= 1.0)
    by_scene: dict[str, dict[str, Any]] = {}
    for result in results:
        stats = by_scene.setdefault(result.scene, {"cases": 0, "avg_keyword_recall": 0.0, "hit_cases": 0, "full_recall_cases": 0})
        stats["cases"] += 1
        stats["avg_keyword_recall"] += result.keyword_recall
        if result.hit:
            stats["hit_cases"] += 1
        if result.keyword_recall >= 1.0:
            stats["full_recall_cases"] += 1
    for stats in by_scene.values():
        stats["avg_keyword_recall"] = round(stats["avg_keyword_recall"] / stats["cases"], 4)
        stats["hit_rate"] = round(stats["hit_cases"] / stats["cases"], 4)
    return {
        "total_cases": total,
        "avg_keyword_recall": round(avg_recall, 4),
        "hit_rate": round(hit_rate, 4),
        "full_recall_cases": full_recall,
        "by_scene": by_scene,
    }


def write_reports(results: list[RetrievalCaseResult], output_dir: Path = REPORT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"retrieval_baseline_{timestamp}.json"
    md_path = output_dir / f"retrieval_baseline_{timestamp}.md"

    payload = {"summary": summarize(results), "results": [asdict(result) for result in results]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 本地词法检索基线评测报告",
        "",
        f"生成时间：{timestamp}",
        "",
        "## 汇总",
        "",
        f"- 用例数：{payload['summary']['total_cases']}",
        f"- Top-K 命中率：{payload['summary']['hit_rate']:.2%}",
        f"- 平均关键词召回率：{payload['summary']['avg_keyword_recall']:.2%}",
        f"- 全关键词召回用例数：{payload['summary']['full_recall_cases']}",
        "",
        "| 场景 | 用例数 | Top-K 命中率 | 平均关键词召回率 | 全关键词召回用例 |",
        "|---|---:|---:|---:|---:|",
    ]
    for scene, stats in sorted(payload["summary"]["by_scene"].items()):
        lines.append(
            f"| {scene} | {stats['cases']} | {stats['hit_rate']:.2%} | "
            f"{stats['avg_keyword_recall']:.2%} | {stats['full_recall_cases']} |"
        )
    lines.extend(["", "## 未完全召回用例", ""])
    partials = [result for result in results if result.keyword_recall < 1.0]
    if not partials:
        lines.append("全部用例均在 Top-K 检索片段中召回全部期望关键词。")
    else:
        for result in partials:
            top = result.retrieved[0] if result.retrieved else None
            lines.extend(
                [
                    f"### {result.scene}｜{result.query}",
                    f"- 关键词召回率：{result.keyword_recall:.2%}",
                    f"- 已召回：{', '.join(result.matched_keywords) or '无'}",
                    f"- 未召回：{', '.join(result.missing_keywords) or '无'}",
                    f"- Top1 分数：{top.score if top else '无'}",
                    f"- Top1 片段：{top.text[:240].replace(chr(10), ' ') if top else '无'}",
                    "",
                ]
            )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def check_thresholds(summary: dict[str, Any], min_hit_rate: float = 0.0, min_avg_keyword_recall: float = 0.0) -> list[str]:
    failures: list[str] = []
    if summary["hit_rate"] < min_hit_rate:
        failures.append(f"hit_rate {summary['hit_rate']:.2%} < required {min_hit_rate:.2%}")
    if summary["avg_keyword_recall"] < min_avg_keyword_recall:
        failures.append(
            f"avg_keyword_recall {summary['avg_keyword_recall']:.2%} < required {min_avg_keyword_recall:.2%}"
        )
    return failures



def main() -> int:
    parser = argparse.ArgumentParser(description="Run local lexical retrieval baseline for seed and optional reviewed datasets.")
    parser.add_argument("--scene", help="Only evaluate one scene")
    parser.add_argument("--include-reviewed", action="store_true", help="Also load eval/datasets/*_reviewed.jsonl regression cases")
    parser.add_argument(
        "--extra-dataset",
        action="append",
        type=Path,
        default=[],
        help="Additional JSONL dataset path to include; can be repeated",
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-hit-rate", type=float, default=0.0, help="Fail when Top-K hit rate is below this threshold")
    parser.add_argument("--min-avg-keyword-recall", type=float, default=0.0, help="Fail when average keyword recall is below this threshold")
    args = parser.parse_args()

    cases = load_cases(scene=args.scene, include_reviewed=args.include_reviewed, extra_paths=args.extra_dataset)
    if not cases:
        print("No evaluation cases found.")
        return 1
    results = evaluate_cases(cases, chunk_size=args.chunk_size, overlap=args.overlap, top_k=args.top_k)
    json_path, md_path = write_reports(results)
    summary = summarize(results)
    print(
        f"[retrieval-baseline] cases={summary['total_cases']} "
        f"hit_rate={summary['hit_rate']:.2%} avg_keyword_recall={summary['avg_keyword_recall']:.2%}"
    )
    print(f"[report] {json_path}")
    print(f"[report] {md_path}")
    failures = check_thresholds(
        summary,
        min_hit_rate=args.min_hit_rate,
        min_avg_keyword_recall=args.min_avg_keyword_recall,
    )
    if failures:
        for failure in failures:
            print(f"[quality-gate][failed] {failure}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

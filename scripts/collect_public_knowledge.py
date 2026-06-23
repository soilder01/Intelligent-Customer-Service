"""Collect public knowledge data for demo Agent scenes.

The script intentionally stores only public text content and source metadata.
Secrets such as ARK_API_KEY / DASHSCOPE_API_KEY must be provided through
runtime environment variables and are never written by this script.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "Mozilla/5.0 (compatible; AgenticWorkflowDataCollector/0.1)"


@dataclass(frozen=True)
class Source:
    scene: str
    title: str
    url: str
    kind: str = "public_web"


SOURCES: tuple[Source, ...] = (
    Source("zhisaotong", "科沃斯常见问题解决", "https://www.ecovacs.cn/pure-question-21994.html"),
    Source("zhisaotong", "HIZERO F580S 常见问题", "https://www.hizero.cn/help/faq/f500/"),
    Source("zhisaotong", "HIZERO F100 常见问题", "https://www.hizero.cn/help/faq/f100/"),
    Source("ecommerce", "京东售后政策自营", "https://help.jd.com/user/issue/list-112.html"),
    Source("ecommerce", "京东售后常见问题", "https://help.jd.com/user/issue/list-115.html"),
    Source("ecommerce", "三星商城退换货适用条件", "https://www.samsung.com.cn/shop-faq/after-sale/what-conditions-apply-to-returns-and-exchanges/"),
    Source("ecommerce", "网络购买商品七日无理由退货暂行办法", "https://www.gov.cn/zhengce/zhengceku/2020-11/03/content_5557118.htm"),
    Source("hr", "中国就业网人社日课", "https://chinajob.mohrss.gov.cn/h5/c/2021-06-04/308283.shtml"),
    Source("hr", "中华人民共和国劳动合同法", "http://www.npc.gov.cn/zgrdw/npc/xinwen/lfgz/zxfl/2007-06/29/content_368169.htm"),
    Source("hr", "赣州市劳动者入职指引", "http://www.rsj.ganzhou.gov.cn/c101392/202603/fc123d347398402d808e04fdf44a6ec4.shtml"),
    Source("property", "鄂尔多斯物业服务常见问题答疑", "https://zjj.ordos.gov.cn/hdjl/zcwd/202402/t20240218_3573119.html"),
    Source("property", "上海物业费构成详解", "https://www.shanghai.gov.cn/nw17239/20251022/01b68dca140a4ccfa298e742460f19e2.html"),
    Source("property", "上海市房屋管理局物业费构成详解", "https://fgj.sh.gov.cn/gzdt/20251022/896acc6875354f1990d9f2e8297cbb2e.html"),
)


class TextExtractor(HTMLParser):
    """Small dependency-free HTML text extractor."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas"}
    BLOCK_TAGS = {
        "p",
        "br",
        "div",
        "section",
        "article",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        return normalize_text("".join(self._chunks))


def normalize_text(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[\t\x0b\x0c ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def extract_text_from_html(raw_html: str) -> str:
    parser = TextExtractor()
    parser.feed(raw_html)
    return parser.text()


def fetch_url(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            decoded = body.decode(charset, errors="replace")
        except LookupError:
            decoded = body.decode("utf-8", errors="replace")
        if "html" in content_type or "<html" in decoded.lower():
            return extract_text_from_html(decoded)
        return normalize_text(decoded)


def write_scene_file(scene: str, records: Iterable[tuple[Source, str]]) -> Path:
    output_dir = PROJECT_ROOT / "data" / scene
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "public_knowledge_seed.txt"

    sections: list[str] = []
    for source, text in records:
        sections.append(
            "\n".join(
                [
                    f"# 来源：{source.title}",
                    f"URL：{source.url}",
                    f"类型：{source.kind}",
                    "",
                    text,
                ]
            )
        )
    output_path.write_text("\n\n---\n\n".join(sections), encoding="utf-8")
    return output_path


def collect(sources: Iterable[Source], min_chars: int = 300) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[tuple[Source, str]]] = {}
    manifest: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for source in sources:
        try:
            text = fetch_url(source.url)
            if len(text) < min_chars:
                raise ValueError(f"content too short: {len(text)} chars")
            grouped.setdefault(source.scene, []).append((source, text))
            manifest.append(
                {
                    "scene": source.scene,
                    "title": source.title,
                    "url": source.url,
                    "kind": source.kind,
                    "chars": str(len(text)),
                    "status": "success",
                }
            )
            print(f"[success] {source.scene} {source.title} {len(text)} chars")
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            failures.append(
                {
                    "scene": source.scene,
                    "title": source.title,
                    "url": source.url,
                    "kind": source.kind,
                    "chars": "0",
                    "status": f"failed: {type(exc).__name__}: {exc}",
                }
            )
            print(f"[failed] {source.scene} {source.title}: {exc}", file=sys.stderr)
        time.sleep(0.5)

    for scene, records in grouped.items():
        path = write_scene_file(scene, records)
        print(f"[write] {scene}: {path}")

    return manifest, failures


def write_manifest(rows: list[dict[str, str]]) -> Path:
    output_dir = PROJECT_ROOT / "data" / "collected"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "source_manifest.csv"
    fieldnames = ["scene", "title", "url", "kind", "chars", "status"]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public knowledge data for Agent scenes.")
    parser.add_argument("--scene", choices=sorted({source.scene for source in SOURCES}), help="Only collect one scene")
    parser.add_argument("--min-chars", type=int, default=300, help="Minimum extracted text chars per source")
    args = parser.parse_args()

    selected = [source for source in SOURCES if not args.scene or source.scene == args.scene]
    manifest, failures = collect(selected, min_chars=args.min_chars)
    manifest_path = write_manifest(manifest + failures)
    print(f"[manifest] {manifest_path}")
    if failures:
        print(f"[done-with-failures] {len(failures)} source(s) failed", file=sys.stderr)
    return 0 if manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())

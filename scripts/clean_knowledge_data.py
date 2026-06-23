"""Clean collected public knowledge files for RAG ingestion.

The collector stores public web text in scene data folders. Raw web extraction often
contains navigation, login hints and footer boilerplate. This script removes common
noise while keeping source title / URL metadata and useful article content.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENES = ("zhisaotong", "ecommerce", "hr", "property")
DEFAULT_FILE_NAME = "public_knowledge_seed.txt"

BOILERPLATE_EXACT = {
    "返回",
    "首页",
    "常见问题",
    "自助服务",
    "联系客服",
    "新手指南",
    "购物指南",
    "用户协议",
    "交易条款",
    "我的订单",
    "我的京东",
    "京东会员",
    "企业采购",
    "手机京东",
    "关注京东",
    "客户服务",
    "网站导航",
    "免费注册",
    "帮助中心-京东",
    "常见问题分类",
    "购物流程",
    "促销咨询",
    "商品咨询",
    "生活旅行",
    "订单百事通",
    "自营和非自营",
    "配送方式",
    "支付问题",
    "今天是：",
    "无障碍",
    "长者模式",
    "微信公众号",
    "统一身份登录",
    "网站首页",
    "政务公开",
    "党建工作",
    "政务服务",
    "互动交流",
    "当前位置：",
    "字号：",
    "打印",
    "下载",
    "微信分享",
    "微博分享",
    "大",
    "中",
    "小",
    "提交订单",
    "修改订单",
    "取消订单",
    "订单锁定/解锁",
    "订单拆分",
    "订单异常",
    "订单确认",
    "晒单评价",
    "违规订单处理",
    "第三方交易纠纷",
    "发货与签收",
    "京东配送服务说明",
    "商家配送服务说明",
    "第三方配送",
    "配送运费收取说明",
    "配送服务查询",
    "配送时效",
    "配送异常",
    "支付流程",
    "货到付款",
    "在线支付",
    "公司转账",
    "分期付款",
    "京东白条",
    "支票支付",
    "扫码支付",
    "异常情况",
    "登录",
    "注册",
    "回到顶部",
}

BOILERPLATE_PATTERNS = (
    re.compile(r"^你好[，,]?请登录"),
    re.compile(r"^首页\s*[>＞]"),
    re.compile(r"^来源：.{0,30}$"),
    re.compile(r"^作者："),
    re.compile(r"^发布时间："),
    re.compile(r"^主办单位"),
    re.compile(r"^网站标识码"),
    re.compile(r"^京ICP备"),
    re.compile(r"^京公网安备"),
    re.compile(r"^◇"),
    re.compile(r"^Copyright\b", re.IGNORECASE),
    re.compile(r"^版权所有"),
    re.compile(r"^ICP备案"),
    re.compile(r"^京公网安备"),
    re.compile(r"^分享到"),
    re.compile(r"^打印本页"),
    re.compile(r"^关闭窗口"),
)

METADATA_PREFIXES = ("# 来源：", "URL：", "类型：")


@dataclass(frozen=True)
class CleanStats:
    path: Path
    before_lines: int
    after_lines: int
    removed_lines: int


def normalize_line(line: str) -> str:
    line = re.sub(r"[\t\x0b\x0c ]+", " ", line or "")
    return line.strip()


def is_metadata(line: str) -> bool:
    return line.startswith(METADATA_PREFIXES) or line == "---"


def is_boilerplate(line: str) -> bool:
    if not line:
        return True
    if is_metadata(line):
        return False
    if line in BOILERPLATE_EXACT:
        return True
    if len(line) <= 2 and not re.search(r"[\u4e00-\u9fa5A-Za-z0-9]", line):
        return True
    return any(pattern.search(line) for pattern in BOILERPLATE_PATTERNS)


def dedupe_consecutive(lines: Iterable[str]) -> list[str]:
    result: list[str] = []
    previous = None
    for line in lines:
        if line == previous and not is_metadata(line):
            continue
        result.append(line)
        previous = line
    return result


def clean_text(text: str) -> str:
    normalized = [normalize_line(line) for line in text.splitlines()]
    kept = [line for line in normalized if not is_boilerplate(line)]
    kept = dedupe_consecutive(kept)

    # Preserve section readability: add a blank line after metadata blocks and separators.
    output: list[str] = []
    for idx, line in enumerate(kept):
        output.append(line)
        next_line = kept[idx + 1] if idx + 1 < len(kept) else ""
        if line.startswith("类型：") and next_line:
            output.append("")
        elif line == "---" and next_line:
            output.append("")
    return "\n".join(output).strip() + "\n"


def clean_file(path: Path, dry_run: bool = False) -> CleanStats:
    original = path.read_text(encoding="utf-8")
    cleaned = clean_text(original)
    before_lines = len(original.splitlines())
    after_lines = len(cleaned.splitlines())
    if not dry_run:
        path.write_text(cleaned, encoding="utf-8")
    return CleanStats(
        path=path,
        before_lines=before_lines,
        after_lines=after_lines,
        removed_lines=max(before_lines - after_lines, 0),
    )


def iter_scene_files(scenes: Iterable[str], file_name: str = DEFAULT_FILE_NAME) -> Iterable[Path]:
    for scene in scenes:
        path = PROJECT_ROOT / "data" / scene / file_name
        if path.exists():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean collected public knowledge seed files.")
    parser.add_argument("--scene", choices=DEFAULT_SCENES, help="Only clean one scene")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing files")
    args = parser.parse_args()

    scenes = (args.scene,) if args.scene else DEFAULT_SCENES
    files = list(iter_scene_files(scenes))
    if not files:
        print("No knowledge seed files found.")
        return 1

    for path in files:
        stats = clean_file(path, dry_run=args.dry_run)
        print(
            f"[clean] {stats.path.relative_to(PROJECT_ROOT)} "
            f"before={stats.before_lines} after={stats.after_lines} removed={stats.removed_lines}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

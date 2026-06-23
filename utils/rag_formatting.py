"""Utilities for formatting RAG evidence without depending on LangChain runtime."""
from __future__ import annotations

NO_EVIDENCE_RESPONSE = "抱歉，当前知识库中没有检索到足够相关的资料，暂时无法准确回答这个问题。"


def _format_source(metadata: dict) -> str:
    """从文档 metadata 中提取尽量可读的来源信息。"""
    if not metadata:
        return "未知来源"

    source = metadata.get("source") or metadata.get("file_path") or metadata.get("path") or "未知来源"
    page = metadata.get("page")
    if page is not None:
        return f"{source}，第{page + 1 if isinstance(page, int) else page}页"
    return str(source)


def format_rag_context(context_docs: list) -> str:
    """将检索结果格式化为 Prompt 可稳定引用的证据块。"""
    context_parts = []
    for index, doc in enumerate(context_docs, start=1):
        content = (getattr(doc, "page_content", "") or "").strip()
        if not content:
            continue
        metadata = getattr(doc, "metadata", {}) or {}
        source = _format_source(metadata)
        context_parts.append(
            f"【参考资料{index}】\n"
            f"来源：{source}\n"
            f"内容：{content}"
        )
    return "\n\n".join(context_parts)

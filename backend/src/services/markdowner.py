"""把结构化 blocks 渲染为 Markdown 字符串。"""
from __future__ import annotations

from typing import Iterable


def blocks_to_markdown(blocks: Iterable[dict], title: str | None = None) -> str:
    parts: list[str] = []
    if title:
        parts.append(f"# {title}\n")

    for b in blocks:
        speaker = b.get("speaker") or ""
        ts = b.get("timestamp") or ""
        header = speaker
        if ts:
            header = f"{speaker} [{ts}]" if speaker else f"[{ts}]"
        if header:
            parts.append(f"### {header}")
        content = (b.get("content") or "").strip()
        # 以引用样式呈现：每一行前加 "> "，空行也以 ">" 占位，便于连续引用块
        if content:
            for ln in content.splitlines():
                if ln.strip():
                    parts.append(f"> {ln}")
                else:
                    parts.append(">")
        else:
            parts.append(">")
        parts.append("")

    return "\n".join(parts).strip() + "\n"

"""
采访稿解析：将原始文本解析为 blocks 结构（更强鲁棒性）。

核心规则参考 tests/preChunkByHeader.py：
- 头部（带时间）：`<说话人> <时间(00:00[:00])> [：:] 可选`，独立成行；
- 头部（姓名单行）：上一行为空、该行为疑似姓名、下一行有正文；
- 行内头部：`<说话人>[ 可选[hh:mm[:ss]] ]：<同一行内容>`；
然后将头部到下一个头部之间的内容并入一个 Block。
"""
from __future__ import annotations

import re
import uuid
from typing import List, Tuple

from src.schemas import Block, Document


NAME_CHARS = r"[\u4e00-\u9fffA-Za-z0-9_.·\-（）()“”'\"\s]{1,30}"
TIME_RE = r"\d{1,2}:\d{2}(?::\d{2})?"

# 带时间的头部（整行），允许行尾紧跟内容：张三 00:01:02：今天……
TIME_HEADER_RE = re.compile(
    rf"^\s*(?P<name>{NAME_CHARS})\s+(?P<time>{TIME_RE})(?:\s*[：:]\s*(?P<rest>.+))?\s*$"
)

# 行内：姓名（可带 [time]）+ 冒号 + 同行内容
INLINE_HEADER_RE = re.compile(rf"^\s*(?P<name>{NAME_CHARS})(?:\s*\[(?P<time>{TIME_RE})\])?\s*[：:]\s*(?P<rest>.+)$")


def _is_name_only_header(lines: List[str], idx: int) -> str:
    s = lines[idx].strip()
    if not s or len(s) > 20 or len(s) < 1:
        return ""
    # 不能含标点或数字
    if re.search(r"[。！？!?,，；;：:…]", s) or re.search(r"\d", s):
        return ""
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z·\-\._（）()]{1,20}", s):
        return ""
    # 上一行需为空
    if idx > 0 and lines[idx - 1].strip():
        return ""
    # 下一行需存在且不是时间头，且足够长
    if idx + 1 >= len(lines):
        return ""
    nxt = lines[idx + 1].strip()
    if not nxt or TIME_HEADER_RE.fullmatch(nxt) or len(nxt) < 3:
        return ""
    return s


def parse_text_to_blocks(text: str, allow_name_only_header: bool = True) -> Document:
    # 统一行结束符
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # 清理连续下划线（常见装饰线）
    lines = [re.sub(r"_+", "", ln) for ln in text.split("\n")]
    n = len(lines)

    headers = []  # 每项: {i, speaker, time, kind, inline_rest(optional)}

    # 第一遍：匹配时间头/行内头
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        m = TIME_HEADER_RE.fullmatch(s)
        if m:
            rest = (m.group("rest") or "").strip()
            headers.append({
                "i": i,
                "speaker": (m.group("name") or "").strip(),
                "time": (m.group("time") or "").strip(),
                "kind": "time_inline" if rest else "time",
                "inline_rest": rest,
            })
            continue
        mi = INLINE_HEADER_RE.fullmatch(s)
        if mi:
            headers.append({
                "i": i,
                "speaker": (mi.group("name") or "").strip(),
                "time": (mi.group("time") or "").strip(),
                "kind": "inline",
                "inline_rest": (mi.group("rest") or "").strip(),
            })

    # 第二遍：姓名单独一行的头（启发式），避免与已取到的 i 冲突
    if allow_name_only_header:
        taken = {h["i"] for h in headers}
        for i in range(n):
            if i in taken or not lines[i].strip():
                continue
            name = _is_name_only_header(lines, i)
            if name:
                headers.append({
                    "i": i,
                    "speaker": name,
                    "time": "",
                    "kind": "name",
                })

    # 无头部：回退为单块
    if not headers:
        content = "\n".join(lines).strip()
        blk = Block(id=str(uuid.uuid4()), speaker="", timestamp=None, content=content, processed=False)
        return Document(blocks=[blk] if content else [])

    # 构造 blocks
    headers.sort(key=lambda x: x["i"])
    blocks: List[Block] = []
    for idx, h in enumerate(headers):
        start_i = h["i"]
        next_i = headers[idx + 1]["i"] if idx + 1 < len(headers) else n

        cur_lines: List[str] = []
        if h.get("kind") in ("inline", "time_inline"):
            # 行内头部：本行右侧 rest 作为第一行
            rest = (h.get("inline_rest") or "").strip()
            if rest:
                cur_lines.append(rest)
            # 之后并入同一 block 的非头部行
            for j in range(start_i + 1, next_i):
                s = lines[j]
                if not s.strip():
                    cur_lines.append("")
                    continue
                # 若是新头部的行，会在外层通过 next_i 截断，不必再次检测
                cur_lines.append(s)
        else:
            # 标准头：内容从下一行开始
            for j in range(start_i + 1, next_i):
                cur_lines.append(lines[j])

        content = "\n".join(cur_lines).strip()
        if not content:
            # 空内容跳过（可能是噪声头部）
            continue
        blocks.append(
            Block(
                id=str(uuid.uuid4()),
                speaker=h.get("speaker", ""),
                timestamp=(h.get("time") or None) if h.get("time") else None,
                content=content,
                processed=False,
            )
        )

    return Document(blocks=blocks)

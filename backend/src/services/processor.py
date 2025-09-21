"""语义处理模块：去口癖、标点规范、基础句式修整。

说明：算法采用确定性规则，保证可控与可扩展；
如需引入大模型增强改写，可在此模块追加 provider 适配层。
"""
from __future__ import annotations

import re
from typing import Iterable


FILLER_PATTERNS = [
    r"\b[额啊嗯呃]\b",
    r"\b就是\b",
    r"\b然后\b",
    r"\b那个\b",
    r"\b你知道的\b",
]


def normalize_punct(s: str) -> str:
    # 统一中英文标点的常见混用
    s = s.replace(",", "，").replace(";", "；").replace(":", "：")
    s = s.replace("?", "？").replace("!", "！")
    # 规范省略号
    s = re.sub(r"\.{2,}", "…", s)
    s = re.sub(r"…{2,}", "…", s)
    # 处理多余空格
    s = re.sub(r"\s+", " ", s)
    # 括号统一
    s = s.replace("(", "（").replace(")", "）")
    return s.strip()


def remove_fillers(s: str) -> str:
    out = s
    for pat in FILLER_PATTERNS:
        out = re.sub(pat, "", out)
    # 去除多余空白
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def optimize_sentence(s: str) -> str:
    # 合并重复标点，如！！！、？？？、。。。。
    s = re.sub(r"([！!？?。；;，,])\1{1,}", r"\1", s)
    # 句末若缺少终止符，按语气补全（简单启发）
    if s and s[-1] not in "。？！…!?":
        s = s + "。"
    return s


def process_text(text: str) -> str:
    text = normalize_punct(text)
    text = remove_fillers(text)
    # 分句（启发式），再优化
    parts = re.split(r"(?<=[。！？?!])\s+", text)
    parts = [optimize_sentence(p.strip()) for p in parts if p.strip()]
    return "\n".join(parts)


def process_block_content(content: str) -> str:
    return process_text(content)


def process_blocks(blocks: Iterable[dict]) -> list[dict]:
    out = []
    for b in blocks:
        processed_content = process_block_content(b.get("content", ""))
        out.append({
            **b,
            "content": processed_content,
            "processed": True,
        })
    return out


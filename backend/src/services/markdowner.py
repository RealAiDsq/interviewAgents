"""把结构化 blocks 渲染为 Markdown 字符串。"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import re


def is_likely_timestamp(text: str) -> bool:
    """检查文本是否可能是时间戳格式"""
    if not text:
        return False
        
    # 匹配纯时间格式
    if re.match(r"^\s*\d{1,2}[:.：]\d{2}(?:[:.：]\d{2})?\s*$", text):
        return True
    
    # 匹配年月日时分秒格式 - 增强匹配以包括更多变体
    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日\d{1,2}[:.：]\d{2}", text):
        return True
        
    # 匹配年月日 - 增强匹配
    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", text):
        return True
    
    # 特殊匹配：方括号中的年月日格式
    if re.match(r"^\s*\[\d{4}年\d{1,2}月\d{1,2}日\d{1,2}(?:[:：][0-9]{2})?\]?\s*$", text):
        return True
    
    # 特殊匹配：年份+数字的简短格式
    if re.match(r"^\s*\d{4}年\d{1,2}\s*$", text):
        return True
    
    # 匹配更多可能的时间戳格式
    # 方括号中的日期时间
    if re.match(r"^\s*\[\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}[:：]?\d{2})?\]\s*$", text):
        return True
        
    # 检查是否包含年月日时分的组合
    has_year = "年" in text or re.search(r"\d{4}", text)
    has_month = "月" in text
    has_day = "日" in text or "号" in text
    has_time = re.search(r"\d{1,2}[:.：]\d{2}", text)
    
    # 如果同时包含日期和时间元素，很可能是日期时间
    if (has_year and has_month) or (has_month and has_day) or (has_day and has_time):
        return True
    
    return False


def is_internal_message(text: str) -> bool:
    """检查是否为内部处理消息"""
    if not text:
        return False
    
    # 检查常见的内部处理消息模式，扩展模式覆盖更多情况
    patterns = [
        r"当前段落(内容)?(为空|无内容)，无需(优化|修改)",
        r"\[空段落，?无需优化\]",
        r"\[空\]",
        r"\[无内容\]",
        r"\[无内容可优化\]",
        r"^\s*\[\d{2}:\d{2}:\d{2}\]\s*$",
        r"^\s*\[\d{2}:\d{2}\]\s*$",
        r"^(?:当前段落|前文|后文).*?[:：]",
        r"^好的[，,]我将.*?处理",
    ]
    
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    
    # 检查一些特殊短语
    phrases = [
        "当前段落", "无需优化", "无需修改", "内容为空",
        "前文：", "后文：", "段落内容",
    ]
    
    # 如果文本很短且包含这些短语之一，很可能是内部处理消息
    if len(text) < 50:
        for phrase in phrases:
            if phrase in text:
                return True
    
    return False


def blocks_to_markdown(blocks: List[Dict[str, Any]], title: Optional[str] = None) -> str:
    """将块结构转换为Markdown格式。"""
    lines = []
    if title:
        lines.append(f"# {title}\n")

    # 过滤掉包含内部处理消息的块
    filtered_blocks = []
    for block in blocks:
        content = block.get("content", "").strip()
        speaker = block.get("speaker", "").strip()
        
        # 增强过滤：跳过内部处理消息、空内容或说话人是日期格式的块
        if content and not is_internal_message(content) and not is_likely_timestamp(speaker):
            filtered_blocks.append(block)

    for block in filtered_blocks:
        speaker = block.get("speaker", "").strip()
        timestamp = block.get("timestamp", "")
        content = block.get("content", "").strip()
        
        # 再次检查内容，确保没有内部处理消息
        if not content or is_internal_message(content):
            continue

        # 跳过明显是时间戳的说话人
        if speaker and is_likely_timestamp(speaker):
            if timestamp:
                header = f"[{timestamp}]"
            else:
                header = f"[{speaker}]"  # 将误判的说话人作为时间戳
        elif speaker:
            if timestamp:
                header = f"{speaker} [{timestamp}]"
            else:
                header = speaker
        else:
            if timestamp:
                header = f"[{timestamp}]"
            else:
                header = ""
                
        # 跳过纯日期时间格式的标题
        if header and is_likely_timestamp(header.strip('[]')):
            header = ""

        if header:
            # 确保标题使用标准Markdown标记，避免与列表混淆
            lines.append(f"### {header}")
            lines.append("")

        if content:
            content_lines = content.split("\n")
            for line in content_lines:
                lines.append(f"> {line}" if line.strip() else ">")
            lines.append("")

    return "\n".join(lines).strip() + "\n"

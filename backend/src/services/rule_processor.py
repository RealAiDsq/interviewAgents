"""规则型语义处理模块：去口癖、标点规范、基础句式修整。

说明：算法采用确定性规则，保证可控与可扩展；
此模块专注于基础文本规范化，不涉及LLM增强处理。
"""
from __future__ import annotations

import re
import sys
from typing import Iterable, Optional, Dict, Set

try:
    from pypinyin import lazy_pinyin  # type: ignore
    HAS_PYPINYIN = True
    print("成功导入pypinyin库，同音字替换功能已启用", file=sys.stderr)
except ImportError:
    lazy_pinyin = None
    HAS_PYPINYIN = False
    print("警告: 未找到pypinyin库，同音字替换功能不可用。请使用pip install pypinyin安装。", file=sys.stderr)

# 修改中文名模式，允许2-6个字符的中文名
CHINESE_NAME_PATTERN = re.compile(r"[\u4e00-\u9fa5]{2,6}")

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


def build_speaker_map(speakers: Iterable[str]) -> dict[str, str]:
    """构建说话人拼音映射表"""
    if lazy_pinyin is None:
        return {}
        
    mapping: dict[str, str] = {}
    speaker_list = list(speakers)
    
    for raw in speaker_list:
        name = (raw or "").strip()
        if not name:
            continue
        
        # 名称必须是纯中文
        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
            
        try:
            # 使用不带声调的拼音作为键
            key = "".join(lazy_pinyin(name))
            if key:
                mapping[key] = name
        except Exception as e:
            print(f"为'{name}'生成拼音键时出错: {e}")
    
    # 只输出映射数量，不输出详细内容
    if mapping:
        print(f"构建了{len(mapping)}个说话人拼音映射")
    
    return mapping


def replace_homophone_names(text: str, speaker_map: dict[str, str]) -> str:
    """基于拼音映射表替换同音字变体"""
    # TODO:
    # - 将逻辑拆分为按长度分组、查找替换项、从后向前应用替换三步
    # - 保持原有日志输出和错误处理
    # - 确保从后向前替换以避免位置偏移

    if not speaker_map or lazy_pinyin is None:
        return text

    original_text = text
    result = text
    replacements: list[tuple[int, int, str, str]] = []

    try:
        def group_names_by_length(mapping: dict[str, str]) -> dict[int, dict[str, str]]:
            grouped: dict[int, dict[str, str]] = {}
            for pinyin_key, standard_name in mapping.items():
                length = len(standard_name)
                if length not in grouped:
                    grouped[length] = {}
                grouped[length][pinyin_key] = standard_name
            return grouped

        def find_replacements_for_length(length: int, pinyin_map: dict[str, str], source: str) -> list[tuple[int, int, str, str]]:
            found: list[tuple[int, int, str, str]] = []
            # 修改逻辑：不再使用正则表达式一次性查找所有匹配项
            # 而是遍历文本中每个位置，从每个位置开始检查固定长度的子串
            for i in range(len(source) - length + 1):
                candidate = source[i:i+length]
                
                # 跳过非中文字符
                if not all('\u4e00' <= c <= '\u9fff' for c in candidate):
                    continue
                    
                # 跳过已经是标准名称的词
                if candidate in pinyin_map.values():
                    continue
                    
                try:
                    candidate_pinyin = "".join(lazy_pinyin(candidate))
                    if candidate_pinyin in pinyin_map:
                        standard_name = pinyin_map[candidate_pinyin]
                        found.append((i, length, candidate, standard_name))
                except Exception:
                    # 单个候选项出错则跳过
                    continue
            return found

        name_by_length = group_names_by_length(speaker_map)

        for length, pinyin_map in name_by_length.items():
            replacements.extend(find_replacements_for_length(length, pinyin_map, result))

        # 从后向前替换，避免位置偏移
        replacements.sort(reverse=True)
        for pos, length, variant, standard in replacements:
            result = result[:pos] + standard + result[pos + length:]
            print(f"拼音替换: '{variant}' -> '{standard}'")

        # 只在有变化时输出日志
        if result != original_text:
            changes = sum(1 for a, b in zip(original_text, result) if a != b)
            print(f"完成同音字替换: 修改了{changes}处")

    except Exception as e:
        print(f"同音字替换过程中出错: {e}")
        return original_text  # 出错时保留原文

    return result


def process_text(text: str, speaker_map: Optional[dict[str, str]] = None) -> str:
    text = normalize_punct(text)
    text = remove_fillers(text)
    # 使用拼音映射进行同音字替换
    if speaker_map:
        text = replace_homophone_names(text, speaker_map)
    parts = re.split(r"(?<=[。！？?!])\s+", text)
    parts = [optimize_sentence(p.strip()) for p in parts if p.strip()]
    return "\n".join(parts)


def process_block_content(content: str, *, speaker_map: Optional[dict[str, str]] = None) -> str:
    return process_text(content, speaker_map=speaker_map)


def process_blocks(blocks: Iterable[dict], speakers: Iterable[str] | None = None) -> list[dict]:
    block_list = list(blocks)
    
    # 仅在调试模式下检查文本块内容
    if sys.flags.debug:
        # 提取并打印块内容以便调试
        for i, b in enumerate(block_list[:1]):  # 只打印第一个块作为示例
            content = b.get("content", "")
            if content:
                print(f"示例块内容: {content[:50]}...")
    
    speaker_pool = []
    if speakers:
        # 检查speakers参数
        speaker_list = list(speakers)
        print(f"收到{len(speaker_list)}个说话人")
        speaker_pool.extend(speaker_list)
    else:
        print("未收到说话人列表")
    
    # 从blocks中提取说话人
    block_speakers = [(b.get("speaker") or "").strip() for b in block_list]
    unique_block_speakers = set(s for s in block_speakers if s)
    print(f"从文本块中提取了{len(unique_block_speakers)}个说话人")
    
    speaker_pool = []
    speaker_pool.extend(speaker_list)  # 优先使用传入的标准说话人
    speaker_pool.extend(block_speakers)  # 添加从块提取的说话人
    
    unique_speakers = set(name for name in speaker_pool if name)
    
    speaker_map = build_speaker_map(unique_speakers)
    
    # 确认pypinyin是否可用
    if lazy_pinyin is None and speakers and len(speakers) > 0:
        print("提示: 安装pypinyin包以启用同音字替换功能: pip install pypinyin")
    
    processed_count = 0
    changed_count = 0
    out = []
    for b in block_list:
        original_content = b.get("content", "")
        processed_content = process_block_content(original_content, speaker_map=speaker_map)
        
        processed_count += 1
        if processed_content != original_content:
            changed_count += 1
            
        out.append({
            **b,
            "content": processed_content,
            "processed": True,
        })
    
    print(f"共处理了{processed_count}个块，其中{changed_count}个块有内容变化")
    return out
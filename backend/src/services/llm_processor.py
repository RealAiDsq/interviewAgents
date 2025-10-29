"""LLM语义增强处理模块：利用大语言模型进行文本优化。

本模块专注于调用LLM API进行文本内容的语义优化与改写，
与rule_processor提供的基础规则处理形成互补。
"""
from __future__ import annotations

import asyncio
import json
import time
import random
import contextlib  # 添加缺失的导入
import re  # 新增导入，用于处理文本
from typing import Any, Dict, List, Iterable, Optional, AsyncGenerator, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler  

from src.core.chat_llm.llms import ChatLLMFactory
from src.schemas import DEFAULT_PARALLEL, MAX_PARALLEL  # 从schemas.py导入常量

# 修改默认系统提示词，使其更明确
DEFAULT_SYSTEM_PROMPT = """你是文本修改助手。请对用户提供的采访对话内容进行：
1) 去除口癖（额、啊、呃、嗯、就是、然后、那个、你知道的等）
2) 标点符号规范化
3) 同音字的语义甄别

在不改变原意的前提下进行最小必要修改，如果没有上面几点问题，请完全保持原样。"""


def format_block_context(block: Optional[Dict[str, Any]]) -> str:
    if not block:
        return ""
    speaker = str(block.get("speaker") or "").strip()
    timestamp = str(block.get("timestamp") or "").strip()
    header_parts = [part for part in [speaker, f"[{timestamp}]" if timestamp else ""] if part]
    header = " ".join(header_parts)
    content = block.get("content") or ""
    if header:
        return f"{header}\n{content}"
    return str(content)


def build_messages_for_block(
    block: Dict[str, Any],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    *,
    context_before: Optional[str] = None,
    context_after: Optional[str] = None,
) -> List[SystemMessage | HumanMessage]:
    content = block.get("content") or ""
    speaker = block.get("speaker") or ""
    timestamp = block.get("timestamp") or ""
    
    # 检查内容是否为空
    if not content.strip():
        # 对空内容采用特殊提示，避免生成元描述
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content="以下是一段空内容，请直接返回空白即可，不要添加任何描述性文字。\n\n内容：\n")
        ]
    
    # 移除前后文上下文传递
    # context_segments: List[str] = []
    # if context_before:
    #     context_segments.append(f"前文：\n{context_before}")
    # if context_after:
    #     context_segments.append(f"后文：\n{context_after}")
    
    # 明确分离元数据与内容，并提供更明确的指示
    metadata = ""
    if speaker or timestamp:
        metadata = f"说话人：{speaker}\n时间戳：{timestamp}\n\n"
    
    main_segment = f"{metadata}当前段落内容：\n{content}\n\n请仅输出优化后的文本内容，不要包含说话人和时间戳，不要添加格式标记或解释，不要输出'当前段落内容'等提示语。如果内容无需修改，请直接返回原文。"
    
    # 不再拼接前后文上下文
    # body = "\n\n".join([*context_segments, main_segment]) if context_segments else main_segment
    body = main_segment

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=body),
    ]


class QueueTokenHandler(BaseCallbackHandler):
    def __init__(self, q: asyncio.Queue[str]):
        self.q = q

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        try:
            self.q.put_nowait(token)
        except Exception:
            pass


async def stream_process_block(
    block: Dict[str, Any],
    provider: str,
    model: str,
    temperature: float = 0.3,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    # 保留参数但默认为 None，确保向后兼容
    context_before: Optional[str] = None,
    context_after: Optional[str] = None,
):
    """异步生成器：对单个块进行 LLM 处理并逐 token 产出。"""
    q: asyncio.Queue[str] = asyncio.Queue()
    handler = QueueTokenHandler(q)

    # 添加重试和退避逻辑
    max_retries = 3
    base_delay = 2.0
    
    # 创建LLM客户端
    llm = ChatLLMFactory.create(
        provider=provider,
        model=model,
        temperature=temperature,
        streaming=True,
        callbacks=[handler],
    )

    messages = build_messages_for_block(
        block,
        system_prompt,
        # 不传递前后文上下文
        # context_before=context_before,
        # context_after=context_after,
    )

    # 异步并发：后台运行推理，前台消费队列
    async def run_infer():
        for attempt in range(max_retries):
            try:
                # 非第一次尝试时增加延迟
                if attempt > 0:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"流式处理重试 {attempt+1}/{max_retries}，等待 {delay:.2f} 秒...")
                    await asyncio.sleep(delay)
                
                # 尝试调用API
                await llm.ainvoke(messages)
                # 成功完成则退出循环
                break
            except Exception as e:
                # 判断是否是速率限制错误
                if "429" in str(e) or "rate limit" in str(e).lower() or "tpm" in str(e).lower():
                    # 如果还有重试次数则继续
                    if attempt < max_retries - 1:
                        print(f"流式处理遇到限流，将重试 ({attempt+1}/{max_retries})")
                        continue
                # 达到最大重试次数或非速率限制错误，报告失败
                print(f"流式处理失败: {e}")
                await q.put("__ERROR__")
                await q.put(str(e))
        
        # 完成标记
        await q.put("__END__")

    # 启动异步任务
    task = asyncio.create_task(run_infer())
    
    try:
        # 从队列接收结果
        while True:
            token = await q.get()
            if token == "__END__":
                break
            elif token == "__ERROR__":
                # 获取错误消息
                error_msg = await q.get()
                print(f"流式处理错误: {error_msg}")
                break
            yield token
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task


async def _enqueue_block_events(
    idx: int,
    blocks: List[Dict[str, Any]],
    block: Dict[str, Any],
    queue: asyncio.Queue[Optional[bytes]],
    build_chunk: Callable[[str, Dict[str, Any]], bytes],
    provider: str,
    model: str,
    temperature: float,
    system_prompt: str,
) -> None:
    bid = block.get("id") or ""
    speaker = block.get("speaker") or ""
    ts = block.get("timestamp") or None
    original = block.get("content") or ""

    await queue.put(build_chunk("block_start", {"id": bid, "speaker": speaker, "timestamp": ts}))

    # 移除前后文上下文提取
    # prev_text = format_block_context(blocks[idx - 1]) if idx > 0 else ""
    # next_text = format_block_context(blocks[idx + 1]) if idx + 1 < len(blocks) else ""

    try:
        acc: List[str] = []
        async for tok in stream_process_block(
            block,
            provider=provider,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt,
            # 不再传递前后文上下文
            # context_before=prev_text,
            # context_after=next_text,
        ):
            acc.append(tok)
            await queue.put(build_chunk("delta", {"id": bid, "text": tok}))

        text = "".join(acc)
        await queue.put(build_chunk("block_end", {"id": bid, "text": text}))
    except Exception:
        await queue.put(build_chunk("block_error", {"id": bid, "message": "LLM 处理失败，已回退原文"}))
        await queue.put(build_chunk("block_end", {"id": bid, "text": original}))


def resolve_parallel(parallel: Optional[int] = None) -> int:
    """解析并行处理的数量，确保在合理范围内"""
    if parallel is None:
        return DEFAULT_PARALLEL
    max_parallel = max(1, MAX_PARALLEL)  # 使用导入的MAX_PARALLEL
    return max(1, min(parallel, max_parallel))


# 全局速率限制控制
class RateLimiter:
    def __init__(self, tokens_per_minute: int = 90000):
        self.tokens_per_minute = tokens_per_minute
        self.tokens_used = 0
        self.reset_time = time.time() + 60
        self.lock = asyncio.Lock()
    
    async def check_limit(self, tokens_to_use: int) -> bool:
        """检查是否可以使用指定数量的令牌"""
        async with self.lock:
            current_time = time.time()
            # 如果已过重置时间，重置计数
            if current_time > self.reset_time:
                self.tokens_used = 0
                self.reset_time = current_time + 60
            
            # 检查是否超过限制
            if self.tokens_used + tokens_to_use > self.tokens_per_minute:
                return False
            
            # 更新使用量
            self.tokens_used += tokens_to_use
            return True
    
    async def wait_if_needed(self, tokens_to_use: int) -> None:
        """如果需要，等待直到可以使用指定数量的令牌"""
        while not await self.check_limit(tokens_to_use):
            await asyncio.sleep(1)


# 创建一个全局的速率限制器实例
RATE_LIMITER = RateLimiter()


async def sse_stream_blocks(
    blocks: List[Dict[str, Any]],
    provider: str,
    model: str,
    temperature: float = 0.3,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    parallel: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    # 更智能地设置并行度，根据块的数量动态调整
    block_count = len(blocks)
    
    # 如果块数量很少，降低并行度避免浪费
    if parallel is None and block_count < 10:
        suggested_parallel = max(1, min(block_count, 3))
        parallel = suggested_parallel
    else:
        parallel = resolve_parallel(parallel)
    
    # 如果使用OpenAI，进一步限制并行度避免触发TPM限制
    if provider.lower() in ('openai', 'azure'):
        parallel = min(parallel, 5)  # OpenAI更保守的并行限制
        
    print(f"使用并行度: {parallel}，处理 {block_count} 个块")
    
    semaphore = asyncio.Semaphore(parallel)
    queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
    DONE = object()

    def build_chunk(event: str, data: Dict[str, Any]) -> bytes:
        payload = json.dumps(data, ensure_ascii=False)
        return (f"event: {event}\n" + f"data: {payload}\n\n").encode("utf-8")

    async def run_block(idx: int, block: Dict[str, Any]) -> None:
        async with semaphore:
            await _enqueue_block_events(
                idx,
                blocks,
                block,
                queue,
                build_chunk,
                provider,
                model,
                temperature,
                system_prompt,
            )
        await queue.put(DONE)

    tasks = [asyncio.create_task(run_block(idx, block)) for idx, block in enumerate(blocks)]

    finished = 0
    try:
        while finished < len(tasks):
            item = await queue.get()
            if item is DONE:
                finished += 1
                continue
            if item is not None:
                yield item
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
            with contextlib.suppress(Exception):
                await task


async def process_blocks_with_llm(
    blocks: Iterable[Dict[str, Any]], 
    provider: str, 
    model: str, 
    temperature: float = 0.3, 
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    parallel: int = 1,
    streaming: bool = False
) -> List[Dict[str, Any]]:
    """使用LLM处理文本块"""
    try:
        llm = ChatLLMFactory.create(
            provider=provider,
            model=model,
            temperature=temperature,
            streaming=streaming,
        )
    except ValueError as exc:
        raise ValueError(f"创建LLM实例失败: {exc}")

    semaphore = asyncio.Semaphore(parallel)
    prompt = system_prompt.strip() or DEFAULT_SYSTEM_PROMPT

    async def process_block(b: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            content = b.get("content") or ""
            speaker = b.get("speaker") or ""
            timestamp = b.get("timestamp") or ""
            
            # 空内容特殊处理
            if not content.strip():
                return {
                    **b,
                    "content": "",
                    "processed": True,
                }
            
            # 构造更明确的提示
            human_message = f"原文内容：\n{content}\n"
            if speaker or timestamp:
                human_message = f"说话人：{speaker}\n时间戳：{timestamp}\n\n{human_message}"
                human_message += "\n请注意：只返回优化后的内容本身，不要包含说话人和时间戳信息，不要添加任何格式标记或解释文字。"
            
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=human_message),
            ]
            
            # 添加重试逻辑和请求间隔
            max_retries = 3
            base_delay = 2  # 基础延迟2秒
            
            for attempt in range(max_retries):
                try:
                    # 添加请求间隔，避免频繁请求
                    if attempt > 0:
                        # 指数退避策略，每次重试等待时间增加
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"重试请求，等待 {delay:.2f} 秒...")
                        await asyncio.sleep(delay)
                        
                    resp = await llm.ainvoke(messages)
                    text = resp.content if hasattr(resp, 'content') else str(resp)
                    break  # 成功则跳出循环
                except Exception as e:
                    last_error = e
                    if "429" in str(e) or "rate limit" in str(e).lower() or "tpm limit" in str(e).lower():
                        if attempt < max_retries - 1:
                            print(f"遇到限流 (TPM)，将重试 ({attempt+1}/{max_retries})...")
                            continue
                    # 其他错误或达到最大重试次数
                    text = content  # 失败回退原文
                    print(f"处理块失败 (尝试 {attempt+1}/{max_retries}): {e}")
                    break
            
            # 处理LLM响应，清除可能的说话人、时间戳和内部指令
            processed_text = text
            
            # 移除可能出现在开头的说话人和时间戳行
            processed_text = re.sub(r"^[^：\n\r]+\s*\[\d{2}:\d{2}(?::\d{2})?\]\s*\n", "", processed_text)
            processed_text = re.sub(r"^[^：\n\r]+[:：]\s*\n", "", processed_text)
            
            # 过滤掉内部处理指令
            processed_text = re.sub(r"^(?:当前段落|前文|后文).*?[:：].*?\n", "", processed_text)
            processed_text = re.sub(r"^\[.*?\](?:\n|$)", "", processed_text)
            processed_text = re.sub(r"^.*?易立竞.*?(?:\n|$)", "", processed_text)
            processed_text = re.sub(r"^.*?陈鲁豫.*?(?:\n|$)", "", processed_text)
            processed_text = re.sub(r"^.*?无需(?:优化|修改).*?(?:\n|$)", "", processed_text)
            processed_text = re.sub(r"^好的[，,]我将.*?(?:\n|$)", "", processed_text)
            
            # 清理最终文本
            processed_text = processed_text.strip()
            
            return {
                **b,
                "content": processed_text,
                "processed": True,
            }

    block_list = list(blocks)
    out_blocks: List[Dict[str, Any]] = await asyncio.gather(*(process_block(b) for b in block_list))
    return out_blocks

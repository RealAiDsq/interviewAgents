from __future__ import annotations

import asyncio
import json
import contextlib
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage

from src.core.chat_llm.llms import ChatLLMFactory


SYSTEM_PROMPT = (
    "你是文本修改助手。请对用户提供的采访对话内容进行：1) 去除口癖（额、啊、呃、嗯、就是、然后、那个、你知道的等），"
    "2) 标点符号规范。在不改变原意的前提下进行最小必要修改，如果没有上面两点问题，请完全保持原样。输出只包含处理后的文本，不要额外解释。"
)


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
):
    """异步生成器：对单个块进行 LLM 处理并逐 token 产出。"""
    q: asyncio.Queue[str] = asyncio.Queue()
    handler = QueueTokenHandler(q)

    llm = ChatLLMFactory.create(
        provider=provider,
        model=model,
        temperature=temperature,
        streaming=True,
        callbacks=[handler],
    )

    content = block.get("content") or ""
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"原文：\n{content}"),
    ]

    # 异步并发：后台运行推理，前台消费队列
    async def run_infer():
        try:
            await llm.ainvoke(messages)
        finally:
            await q.put("__END__")

    task = asyncio.create_task(run_infer())
    try:
        while True:
            token = await q.get()
            if token == "__END__":
                break
            yield token
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task


async def sse_stream_blocks(
    blocks: List[Dict[str, Any]],
    provider: str,
    model: str,
    temperature: float = 0.3,
):
    """SSE 事件流：按块依次推理，发送 block_start/delta/block_end。"""
    import contextlib

    async def send(event: str, data: Dict[str, Any]):
        payload = json.dumps(data, ensure_ascii=False)
        yield f"event: {event}\n".encode("utf-8")
        yield f"data: {payload}\n\n".encode("utf-8")

    for b in blocks:
        bid = b.get("id") or ""
        speaker = b.get("speaker") or ""
        ts = b.get("timestamp") or None
        # start
        async for chunk in send("block_start", {"id": bid, "speaker": speaker, "timestamp": ts}):
            yield chunk

        acc: List[str] = []
        async for tok in stream_process_block(b, provider=provider, model=model, temperature=temperature):
            acc.append(tok)
            async for chunk in send("delta", {"id": bid, "text": tok}):
                yield chunk

        text = "".join(acc)
        async for chunk in send("block_end", {"id": bid, "text": text}):
            yield chunk

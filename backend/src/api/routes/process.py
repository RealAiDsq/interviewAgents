from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.services.processor import process_blocks
from src.core.chat_llm.llms import ChatLLMFactory
from langchain_core.messages import SystemMessage, HumanMessage


class ProcessRequest(BaseModel):
    blocks: list[Dict[str, Any]]
    mode: str = "llm"  # llm | rule
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.3


router = APIRouter(prefix="/process", tags=["process"])


@router.post("")
async def process(req: ProcessRequest):
    if req.mode == "rule":
        out = process_blocks(req.blocks)
        return {"blocks": out}

    # LLM 模式
    provider = req.provider or "zhipu"
    model = req.model or {
        "zhipu": "GLM-4-Flash",
        "qwen": "qwen2.5-7b-instruct",
        "kimi": "moonshot-v1-32k",
    }.get(provider)

    if not model:
        return {"error": f"未知 provider: {provider}，请提供 model 或切换为 rule 模式"}

    llm = ChatLLMFactory.create(provider=provider, model=model, temperature=req.temperature, streaming=False)
    SYSTEM_PROMPT = (
        "你是文本润色助手。请对用户提供的采访对话内容进行：1) 去除口癖（额、啊、呃、嗯、就是、然后、那个、你知道的等），"
        "2) 标点符号规范，3) 语句顺畅化。在不改变原意的前提下进行最小必要修改。输出只包含处理后的文本，不要额外解释。"
    )

    out_blocks: List[Dict[str, Any]] = []
    for b in req.blocks:
        content = b.get("content") or ""
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"原文：\n{content}"),
        ]
        try:
            resp = await llm.ainvoke(messages)
            text = resp.content if hasattr(resp, 'content') else str(resp)
        except Exception as e:  # noqa: BLE001
            text = content  # 失败回退原文
        out_blocks.append({
            **b,
            "content": text,
            "processed": True,
        })
    return {"blocks": out_blocks}

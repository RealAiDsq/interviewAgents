from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.services.llm_processor import sse_stream_blocks


class ProcessStreamRequest(BaseModel):
    blocks: List[Dict[str, Any]]
    provider: str = "zhipu"  # 可选：qwen/kimi/zhipu
    model: Optional[str] = None
    temperature: float = 0.3


router = APIRouter(prefix="/process", tags=["process"])


@router.post("/stream")
async def process_stream(req: ProcessStreamRequest):
    if not req.blocks:
        raise HTTPException(status_code=400, detail="blocks 不能为空")
    provider = req.provider
    model = req.model or {
        "zhipu": "GLM-4-Flash",
        "qwen": "qwen2.5-7b-instruct",
        "kimi": "moonshot-v1-32k",
    }.get(provider, None)
    if not model:
        raise HTTPException(status_code=400, detail=f"未知 provider: {provider}，请提供 model")

    async def event_gen():
        async for chunk in sse_stream_blocks(req.blocks, provider=provider, model=model, temperature=req.temperature):
            yield chunk

    return StreamingResponse(event_gen(), media_type="text/event-stream")


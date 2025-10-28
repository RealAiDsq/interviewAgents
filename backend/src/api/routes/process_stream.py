from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.schemas import ProcessOptions
from src.services.llm_processor import DEFAULT_SYSTEM_PROMPT, sse_stream_blocks
from src.core.chat_llm.llms import ChatLLMFactory


class ProcessStreamRequest(ProcessOptions):
    blocks: List[Dict[str, Any]]
    provider: str = "zhipu"  # 默认 provider


router = APIRouter(prefix="/process", tags=["process"])


@router.post("/stream")
async def process_stream(req: ProcessStreamRequest):
    if not req.blocks:
        raise HTTPException(status_code=400, detail="blocks 不能为空")
    provider = req.provider or ChatLLMFactory.get_default_provider()
    try:
        ChatLLMFactory.ensure_provider_ready(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        model, _ = await ChatLLMFactory.resolve_model(provider, req.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    system_prompt = (req.system_prompt or DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT

    async def event_gen():
        async for chunk in sse_stream_blocks(
            req.blocks,
            provider=provider,
            model=model,
            temperature=req.temperature,
            system_prompt=system_prompt,
            parallel=req.parallel,
        ):
            yield chunk

    return StreamingResponse(event_gen(), media_type="text/event-stream")


from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.core.chat_llm.llms import ChatLLMFactory
from src.schemas import ProcessOptions
from src.services.llm_processor import DEFAULT_SYSTEM_PROMPT, process_blocks_with_llm, sse_stream_blocks
from src.services.rule_processor import process_blocks


class ProcessRequest(ProcessOptions):
    blocks: list[Dict[str, Any]]
    mode: str = "llm"  # llm | rule
    speakers: list[str] = []  # 添加说话人列表，用于同音字处理


router = APIRouter(prefix="/process", tags=["process"])


@router.get("/catalog")
async def get_llm_catalog():
    providers = []
    for item in ChatLLMFactory.get_catalog():
        provider = item["provider"]
        try:
            # 添加调试输出
            print(f"正在获取提供商 {provider} 的模型列表")
            models = await ChatLLMFactory.fetch_provider_models(provider)
            print(f"成功获取到 {len(models)} 个模型")
        except ValueError as e:
            print(f"获取 {provider} 模型列表失败: {e}")
            models = item.get("models") or []
        item["models"] = models
        if not item.get("default_model") and models:
            item["default_model"] = models[0].get("id")
        providers.append(item)

    default_provider = ChatLLMFactory.get_default_provider()
    default_model = next((p.get("default_model") for p in providers if p["provider"] == default_provider), None)

    # 添加调试输出
    print(f"返回 {len(providers)} 个提供商，默认提供商: {default_provider}")
    
    return {
        "providers": providers,
        "defaults": {
            "provider": default_provider,
            "model": default_model,
            "temperature": 0.3,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "parallel": 8,  # 增大默认并行度
            "parallel_max": 32,  # 添加最大并行度
        },
    }


@router.get("/catalog/{provider}")
async def get_provider_catalog(provider: str, refresh: bool = False):
    try:
        # 添加调试输出
        print(f"请求获取 {provider} 提供商的模型列表，refresh={refresh}")
        models = await ChatLLMFactory.fetch_provider_models(provider, force_refresh=refresh)
        print(f"成功获取到 {len(models)} 个模型")
    except ValueError as exc:  # noqa: PERF203
        print(f"获取 {provider} 模型列表失败: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    default_model = ChatLLMFactory.get_default_model(provider)
    if not default_model and models:
        default_model = models[0].get("id")
    
    print(f"返回 {provider} 提供商的 {len(models)} 个模型，默认模型: {default_model}")
    
    return {
        "provider": provider,
        "models": models,
        "default_model": default_model,
    }


@router.post("")
async def process(req: ProcessRequest):
    # 规则模式 - 调用规则处理器
    if req.mode == "rule":
        # 打印收到的speakers信息
        print(f"接收到处理请求，speakers列表: {req.speakers}")
        out = process_blocks(req.blocks, speakers=req.speakers)
        return {"blocks": out}

    # LLM 模式 - 调用LLM处理器
    provider = req.provider or ChatLLMFactory.get_default_provider()
    system_prompt = (req.system_prompt or DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT
    parallel = max(1, min(req.parallel or 1, 8))

    try:
        resolved_model, _ = await ChatLLMFactory.resolve_model(provider, req.model)
        out_blocks = await process_blocks_with_llm(
            blocks=req.blocks,
            provider=provider,
            model=resolved_model,
            temperature=req.temperature,
            system_prompt=system_prompt,
            parallel=parallel,
            streaming=False
        )
        return {"blocks": out_blocks}
    except ValueError as exc:
        return {"error": str(exc)}


# 新增：将stream处理整合到此文件中
@router.post("/stream")
async def process_stream(req: ProcessRequest):
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

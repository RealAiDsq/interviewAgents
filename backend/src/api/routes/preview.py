from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.services.markdowner import blocks_to_markdown


class PreviewRequest(BaseModel):
    blocks: list[Dict[str, Any]]
    title: str | None = None


router = APIRouter(prefix="/preview", tags=["preview"])


@router.post("")
def preview(req: PreviewRequest, mode: str = Query(default="raw", pattern="^(raw|processed)$")):
    # mode 仅用于前端语义提示，目前后端不区分处理逻辑
    md = blocks_to_markdown(req.blocks, title=req.title)
    return {"markdown": md, "mode": mode}


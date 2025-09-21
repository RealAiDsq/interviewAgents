from typing import List, Optional
from pydantic import BaseModel, Field


class Block(BaseModel):
    id: str = Field(description="唯一标识")
    speaker: str = Field(default="", description="说话人姓名")
    timestamp: Optional[str] = Field(default=None, description="时间戳（可选）")
    content: str = Field(description="说话内容")
    processed: bool = Field(default=False, description="是否已处理")


class Document(BaseModel):
    blocks: List[Block] = Field(default_factory=list)


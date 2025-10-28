from typing import List, Optional
from pydantic import BaseModel, Field

# LLM处理相关默认值
DEFAULT_TEMPERATURE = 0.3
MAX_PARALLEL = 128
# 默认并行处理块数量设置为最大值的一半，兼顾性能与资源消耗
DEFAULT_PARALLEL = MAX_PARALLEL // 2

class Block(BaseModel):
    id: str = Field(description="唯一标识")
    speaker: str = Field(default="", description="说话人姓名")
    timestamp: Optional[str] = Field(default=None, description="时间戳（可选）")
    content: str = Field(description="说话内容")
    processed: bool = Field(default=False, description="是否已处理")


class Document(BaseModel):
    blocks: List[Block] = Field(default_factory=list)


class ProcessOptions(BaseModel):
    provider: Optional[str] = Field(default=None, description="LLM 提供商标识，如 zhipu/qwen/kimi")
    model: Optional[str] = Field(default=None, description="具体模型 ID")
    temperature: float = Field(default=0.3, ge=0, le=1, description="采样温度")
    system_prompt: Optional[str] = Field(default=None, description="自定义系统提示词")
    parallel: int = Field(default=DEFAULT_PARALLEL, ge=1, le=MAX_PARALLEL, description="并行处理的块数量上限")



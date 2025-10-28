import os
import sys

# 确保从 backend/ 目录启动 uvicorn 时可找到 src
sys.path.append(os.getcwd())

# 加载配置（环境变量等）
import src.config.Settings  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router

app = FastAPI(title="智能客服 - SSE API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 仅挂载路由，具体实现放在 src/api 下
app.include_router(api_router)


if __name__ == "__main__":
    # 本地快速运行：poetry run python src/server.py
    import uvicorn

    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)



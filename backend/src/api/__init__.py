from fastapi import APIRouter

# 统一挂载 API 子路由
api_router = APIRouter(prefix="/api")

# 子路由分发
from .routes import health, upload, process, preview, export  # noqa: E402,F401
from .routes import process_stream  # noqa: E402,F401

api_router.include_router(health.router)
api_router.include_router(upload.router)
api_router.include_router(process.router)
api_router.include_router(process_stream.router)
api_router.include_router(preview.router)
api_router.include_router(export.router)

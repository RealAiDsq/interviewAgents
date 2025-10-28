from fastapi import APIRouter

from src.api.routes.export import router as export_router
from src.api.routes.preview import router as preview_router
from src.api.routes.process import router as process_router
from src.api.routes.upload import router as upload_router

api_router = APIRouter(prefix="/api")

api_router.include_router(upload_router)
api_router.include_router(preview_router)
api_router.include_router(process_router)
api_router.include_router(export_router)

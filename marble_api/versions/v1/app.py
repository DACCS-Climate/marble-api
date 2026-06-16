from fastapi import APIRouter

from marble_api.versions.v1.data_request.routes import admin_router as data_request_admin_router
from marble_api.versions.v1.data_request.routes import user_router as data_request_user_router

router = APIRouter(prefix="/v1")

router.include_router(data_request_user_router)
router.include_router(data_request_admin_router)

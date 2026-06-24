from fastapi import APIRouter, Depends

from marble_api.utils.auth import authenticate_magpie_admin, authenticate_magpie_user
from marble_api.versions.v1.data_request.routes import admin_router as data_request_admin_router
from marble_api.versions.v1.data_request.routes import user_router as data_request_user_router

router = APIRouter(prefix="/v1")

user_router = APIRouter(prefix="/users/{user}", tags=["User"], dependencies=[Depends(authenticate_magpie_user)])
admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(authenticate_magpie_admin)])

user_router.include_router(data_request_user_router)
admin_router.include_router(data_request_admin_router)

router.include_router(user_router)
router.include_router(admin_router)

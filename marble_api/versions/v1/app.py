from fastapi import FastAPI

from marble_api.versions.v1.data_request.routes import admin_router as data_request_admin_router
from marble_api.versions.v1.data_request.routes import user_router as data_request_user_router

app = FastAPI(version="1")

app.include_router(data_request_user_router)
app.include_router(data_request_admin_router)

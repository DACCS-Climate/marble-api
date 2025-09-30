from fastapi import FastAPI

from marble_api.versions.v1.data_request.routes import router as data_request_router

app = FastAPI(version="1")

app.include_router(data_request_router)

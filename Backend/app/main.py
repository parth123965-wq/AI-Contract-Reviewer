from fastapi import FastAPI
from app.core.config import settings
from app.api.auth import auth_router
from app.api.users import users_router
from app.api.contracts import contract_router
from app.api.admin import admin_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost",
        "http://localhost:80",
        "http://127.0.0.1:80",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=[
        "*"
    ],
    allow_headers=[
        "*"
    ],
)

app.include_router(router=auth_router)
app.include_router(router=users_router)
app.include_router(router=contract_router)
app.include_router(router=admin_router)

@app.get("/")
def home() -> dict:
    return {
        "message":settings.APP_NAME,
        "version":settings.APP_VERSION,
        "debug":settings.DEBUG
    }
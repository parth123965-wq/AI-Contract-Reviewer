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
        "http://127.0.0.1:5500"
    ],
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
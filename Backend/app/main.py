from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.redis_setup import initialize_redis, close_redis
from app.core.email_setup import initialize_email, close_email
from app.api.auth import auth_router
from app.api.users import users_router
from app.api.contracts import contract_router
from app.api.admin import admin_router
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize services
    try:
        await initialize_redis()
    except Exception as e:
        print(f"Redis initialization warning: {e}")
    await initialize_email()

    yield

    # Shutdown: close services
    await close_redis()
    await close_email()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Explicit CORS configuration based on DEBUG environment setting
if settings.DEBUG:
    # Development Settings: explicit local origins, explicit methods and headers
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1"
    ]
    cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_headers = [
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ]
else:
    # Production Settings: strict configured allowed origins, explicit methods and headers
    cors_origins = settings.ALLOWED_ORIGINS
    cors_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_headers = [
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
    max_age=600,
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
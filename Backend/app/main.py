import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from app.core.config import settings
from app.core.redis_setup import initialize_redis, close_redis
from app.core.email_setup import initialize_email, close_email
from app.core.logger import app_logger, get_app_logger
from app.api.auth import auth_router
from app.api.users import users_router
from app.api.contracts import contract_router
from app.api.admin import admin_router
from fastapi.middleware.cors import CORSMiddleware

main_logger = get_app_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize services
    main_logger.info("Starting Backend App service...")
    try:
        await initialize_redis()
        main_logger.info("Redis initialized successfully.")
    except Exception as e:
        main_logger.warning("Redis initialization warning", extra={"error": str(e)})
    
    try:
        await initialize_email()
        main_logger.info("Email service initialized successfully.")
    except Exception as e:
        main_logger.warning("Email initialization warning", extra={"error": str(e)})

    yield

    # Shutdown: close services
    main_logger.info("Shutting down Backend App service...")
    await close_redis()
    await close_email()
    main_logger.info("Services closed successfully.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    main_logger.info(
        "HTTP Request Processed",
        extra={
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "duration_ms": round(process_time, 2),
            "client_ip": request.client.host if request.client else None,
        }
    )
    return response


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
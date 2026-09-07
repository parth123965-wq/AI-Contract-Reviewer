import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from app.core.config import settings
from app.core.redis_setup import initialize_redis, close_redis
from app.core.email_setup import initialize_email, close_email
from app.core.logger import app_logger, get_app_logger
from app.core.rate_limit import RateLimiter
from app.api.auth import auth_router
from app.api.users import users_router
from app.api.contracts import contract_router
from app.api.admin import admin_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

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


openapi_tags = [
    {
        "name": "System",
        "description": "Health check and application operational status endpoints."
    },
    {
        "name": "Authentication",
        "description": "User registration, OTP verification, login, logout, and password management."
    },
    {
        "name": "Users",
        "description": "User profile retrieval, display name updates, email change workflows, and self-service management."
    },
    {
        "name": "Contracts",
        "description": "Contract PDF document upload, AI risk score calculation, automated summaries, and interactive RAG clause Q&A."
    },
    {
        "name": "Admin",
        "description": "Administrative metrics dashboard, user account management, and contract oversight."
    }
]

app_description = """
# 🤖 AI Contract Reviewer REST API

The **AI Contract Reviewer API** provides automated legal document analysis, contract clause risk scoring, RAG-based natural language document Q&A, and administrative management.

## 🔑 Security & Authentication
- **Protocol**: End-to-End TLS / HTTPS Encryption.
- **Authentication**: JWT (JSON Web Tokens) passed via `Authorization: Bearer <token>` header.
- **Rate Limiting**: Protected endpoints use Redis sliding-window rate limiting to prevent abuse.

## 🚀 Key Features
- **User Authentication**: Secure registration with 6-digit email OTP verification.
- **Contract Processing**: Support for PDF file uploads and automated text extraction.
- **AI Engine Analysis**: High-risk clause extraction, risk score computation (0-100), and modification recommendations powered by Google Gemini LLM.
- **Contract Q&A**: Real-time SSE streaming and standard answers for document clause inquiries.
- **Admin Dashboard**: System-wide statistics and audit operations.
"""

docs_url = None if settings.PRODUCTION else "/docs"
redoc_url = None if settings.PRODUCTION else "/redoc"
openapi_url = None if settings.PRODUCTION else "/openapi.json"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=app_description,
    openapi_tags=openapi_tags,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
    contact={
        "name": "AI Contract Reviewer Development Team",
        "url": "https://github.com/parth123965-wq/AI-Contract-Reviewer",
    },
    license_info={
        "name": "MIT License",
    },
    lifespan=lifespan
)

# Optional force HTTPS redirect middleware
if settings.FORCE_HTTPS:
    app.add_middleware(HTTPSRedirectMiddleware)


@app.middleware("http")
async def enforce_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000

    # OWASP Cryptographic Security Headers
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

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
        "https://localhost",
        "https://127.0.0.1",
        "https://localhost:443",
        "https://127.0.0.1:443",
        "https://localhost:8000",
        "https://127.0.0.1:8000",
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

@app.get(
    "/",
    tags=["System"],
    summary="System Health & Operational Status",
    description="Check backend server health, application display name, version, and debug status.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="home"))]
)
def home() -> dict:
    return {
        "message": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG
    }
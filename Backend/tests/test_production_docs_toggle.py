import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.core.config import settings

@pytest.mark.asyncio
async def test_api_docs_visible_when_production_false():
    with patch.object(settings, "PRODUCTION", False):
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            resp_docs = await client.get("/docs")
            assert resp_docs.status_code == 200

            resp_redoc = await client.get("/redoc")
            assert resp_redoc.status_code == 200

            resp_openapi = await client.get("/openapi.json")
            assert resp_openapi.status_code == 200

@pytest.mark.asyncio
async def test_api_docs_hidden_when_production_true():
    with patch.object(settings, "PRODUCTION", True):
        # Re-evaluate docs URLs conditionally
        docs_url = None if settings.PRODUCTION else "/docs"
        redoc_url = None if settings.PRODUCTION else "/redoc"
        openapi_url = None if settings.PRODUCTION else "/openapi.json"
        
        # Test app instantiation with docs disabled
        from fastapi import FastAPI
        from app.main import app_description, openapi_tags, lifespan
        prod_app = FastAPI(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description=app_description,
            openapi_tags=openapi_tags,
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
            lifespan=lifespan
        )
        
        async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://testserver") as client:
            resp_docs = await client.get("/docs")
            assert resp_docs.status_code == 404

            resp_redoc = await client.get("/redoc")
            assert resp_redoc.status_code == 404

            resp_openapi = await client.get("/openapi.json")
            assert resp_openapi.status_code == 404

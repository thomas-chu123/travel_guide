from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db import models  # noqa: F401 - register SQLAlchemy model metadata
from app.db.session import create_local_schema


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_local_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tokyo Event Map API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

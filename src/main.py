from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette import status

from src.core.config.settings import get_settings
from src.core.errors.exceptions import AppException
from src.core.errors.handlers import (
    app_exception_handler,
    generic_exception_handler,
    value_error_handler,
)
from src.core.logging.logger import configure_logging
from src.core.scheduler.manager import start_scheduler, stop_scheduler
from src.infrastructure.database.session import dispose_engine, engine
from src.modules.shopee.api import router as shopee_router

logger = logging.getLogger("app")


def _success_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
    }


def _error_payload(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "data": {},
        "error": message,
    }


async def _check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("database_check_failed")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup")
    scheduler = start_scheduler()
    try:
        yield
    finally:
        logger.info("shutdown")
        stop_scheduler(scheduler)
        await _shutdown_resources()


async def _shutdown_resources() -> None:
    try:
        await dispose_engine()
    except Exception:
        logger.error("database_dispose_failed")


def create_app() -> FastAPI:
    configure_logging()
    app_settings = get_settings()

    app = FastAPI(
        title=app_settings.app.name,
        version=app_settings.app.api_version,
        debug=app_settings.app.debug,
        lifespan=lifespan,
    )

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    app.include_router(shopee_router)

    @app.get("/health")
    async def health() -> JSONResponse:
        db_ok = await _check_database()
        if db_ok:
            return JSONResponse(status_code=status.HTTP_200_OK, content=_success_payload({"status": "ok"}))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_payload("Database unavailable"),
        )

    @app.get("/readiness")
    async def readiness() -> JSONResponse:
        db_ok = await _check_database()
        if db_ok:
            return JSONResponse(status_code=status.HTTP_200_OK, content=_success_payload({"status": "ready"}))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_payload("Not ready"),
        )

    @app.get("/liveness")
    async def liveness() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=_success_payload({"status": "alive"}))

    return app


app = create_app()

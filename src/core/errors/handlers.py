from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from src.core.config.settings import settings
from src.core.errors.exceptions import AppException

logger = logging.getLogger("app.errors")


def _error_payload(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "data": {},
        "error": message,
    }


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    logger.warning(
        "application_error",
        extra={
            "data": {
                "path": request.url.path,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
            }
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.message),
    )


async def value_error_handler(
    request: Request,
    exc: ValueError,
) -> JSONResponse:
    message = str(exc).strip() or "Invalid request"
    logger.info(
        "value_error",
        extra={"data": {"path": request.url.path}},
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_payload(message),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if settings.app.debug:
        logger.exception(
            "unhandled_exception",
            extra={"data": {"path": request.url.path}},
        )
    else:
        logger.error(
            "unhandled_exception",
            extra={"data": {"path": request.url.path}},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload("Internal server error"),
    )

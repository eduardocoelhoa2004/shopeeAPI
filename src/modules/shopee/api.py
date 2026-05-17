from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import settings
from src.core.errors.exceptions import AppException
from src.infrastructure.database.session import get_db_session
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.modules.shopee.client import ShopeeAffiliateClient
from src.modules.shopee.service import ShopeeOfferService

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="ignore")

    success: bool
    data: T | dict[str, Any]
    error: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    error: str


class ShortLinkRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    original_url: HttpUrl


class ShortLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    short_link: HttpUrl


router = APIRouter(prefix="/api/v1/shopee", tags=["Shopee"])


async def get_shopee_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ShopeeOfferService, None]:
    async with AsyncHttpClient(base_url=settings.shopee.base_url) as http_client:
        client = ShopeeAffiliateClient(http_client=http_client)
        yield ShopeeOfferService(session=session, client=client)


@router.post("/short-link", response_model=StandardResponse[ShortLinkResponse])
async def create_short_link(payload: ShortLinkRequest) -> StandardResponse[ShortLinkResponse]:
    async with AsyncHttpClient(base_url=settings.shopee.base_url) as http_client:
        client = ShopeeAffiliateClient(http_client=http_client)
        result = await client.generate_short_link(original_url=str(payload.original_url))

    if not result.get("success"):
        raise AppException(
            result.get("error") or "shopee_request_failed",
            status_code=502,
            error_code="shopee_short_link_failed",
        )

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    short_link_value = (
        data.get("short_link")
        or data.get("shortLink")
        or data.get("short_link_url")
        or data.get("shortLinkUrl")
    )
    if not short_link_value:
        raise AppException(
            "shopee_short_link_missing",
            status_code=502,
            error_code="shopee_short_link_missing",
        )

    try:
        payload_response = ShortLinkResponse(short_link=short_link_value)
    except ValidationError as exc:
        raise AppException(
            "shopee_short_link_invalid",
            status_code=502,
            error_code="shopee_short_link_invalid",
        ) from exc

    return StandardResponse(success=True, data=payload_response, error=None)


@router.post("/test-fetch", response_model=StandardResponse[dict[str, int]])
async def test_fetch(
    limit: int = 20,
    service: ShopeeOfferService = Depends(get_shopee_service),
) -> StandardResponse[dict[str, int]]:
    try:
        summary = await service.fetch_and_process_offers(limit=limit)
    except Exception as exc:
        raise AppException(
            "shopee_test_fetch_failed",
            status_code=500,
            error_code=exc.__class__.__name__,
        ) from exc

    return StandardResponse(success=True, data=summary, error=None)


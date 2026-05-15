from __future__ import annotations

from typing import AsyncGenerator, Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from src.core.config.settings import settings
from src.core.errors.exceptions import AppException
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.modules.shopee.client import ShopeeAffiliateClient
from src.modules.shopee.schemas import (
    OfferListRequest,
    OfferListResponse,
    ShortLinkRequest,
    ShortLinkResponse,
)

router = APIRouter(prefix="/api/v1/shopee", tags=["Shopee"])


async def get_shopee_client() -> AsyncGenerator[ShopeeAffiliateClient, None]:
    async with AsyncHttpClient(base_url=settings.shopee.base_url) as http_client:
        yield ShopeeAffiliateClient(http_client=http_client)


@router.post("/short-link", response_model=ShortLinkResponse)
async def create_short_link(
    payload: ShortLinkRequest,
    client: ShopeeAffiliateClient = Depends(get_shopee_client),
) -> ShortLinkResponse:
    result = await client.generate_short_link(
        original_url=str(payload.original_url),
        source=payload.source,
    )
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
        return ShortLinkResponse(short_link=short_link_value)
    except ValidationError as exc:
        raise AppException(
            "shopee_short_link_invalid",
            status_code=502,
            error_code="shopee_short_link_invalid",
        ) from exc


@router.get("/offers", response_model=OfferListResponse)
async def list_offers(
    query: OfferListRequest = Depends(),
    client: ShopeeAffiliateClient = Depends(get_shopee_client),
) -> OfferListResponse:
    result = await client.get_offer_list(limit=query.limit, offset=query.offset)
    if not result.get("success"):
        raise AppException(
            result.get("error") or "shopee_request_failed",
            status_code=502,
            error_code="shopee_offer_list_failed",
        )

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    offers = data.get("offers") or data.get("list") or data.get("items") or []
    if not isinstance(offers, list):
        offers = []

    total_value: Any = data.get("total") or data.get("count")
    total = total_value if isinstance(total_value, int) else None

    return OfferListResponse(
        offers=offers,
        total=total,
        limit=query.limit,
        offset=query.offset,
    )

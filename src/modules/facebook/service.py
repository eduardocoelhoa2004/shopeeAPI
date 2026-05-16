from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.external_apis.gemini import GeminiClient
from src.modules.facebook.client import FacebookClient
from src.modules.shopee.models import ShopeeOffer

logger = logging.getLogger("app.facebook.service")

HASHTAGS = "#AchadosDaShopee #Ofertas"


class FacebookPublisherService:
    def __init__(
        self,
        session: AsyncSession,
        facebook_client: FacebookClient,
        gemini_client: GeminiClient,
    ) -> None:
        self._session = session
        self._facebook_client = facebook_client
        self._gemini_client = gemini_client

    async def publish_next_offer(self) -> bool:
        offer = await self._get_next_unpublished_offer()
        if offer is None:
            logger.info(
                "facebook_publish_skipped",
                extra={"data": {"reason": "no_unpublished_offers"}},
            )
            return False

        current_offer_id = str(offer.offer_id)
        message = await self._format_offer_message(offer)
        try:
            published = await self._facebook_client.post_offer(
                message=message,
                link=offer.short_url,
            )
        except Exception:
            await self._session.rollback()
            logger.exception(
                "facebook_publish_error",
                extra={"data": {"offer_id": current_offer_id}},
            )
            return False

        if not published:
            await self._session.rollback()
            logger.warning(
                "facebook_publish_failed",
                extra={"data": {"offer_id": current_offer_id}},
            )
            return False

        offer.is_published_facebook = True
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception(
                "facebook_publish_commit_failed",
                extra={"data": {"offer_id": current_offer_id}},
            )
            return False

        logger.info(
            "facebook_offer_published",
            extra={"data": {"offer_id": current_offer_id}},
        )
        return True

    async def _get_next_unpublished_offer(self) -> ShopeeOffer | None:
        stmt = (
            select(ShopeeOffer)
            .where(ShopeeOffer.is_published_facebook.is_(False))
            .order_by(ShopeeOffer.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _format_offer_message(self, offer: ShopeeOffer) -> str:
        name = " ".join(offer.name.split())
        price = self._format_price(offer.price)
        fallback = f"{name}\n\nPor apenas: {price}\n\n{HASHTAGS}"
        ai_copy = await self._gemini_client.generate_caption(
            name,
            price,
            offer.short_url,
        )
        if ai_copy:
            cleaned = ai_copy.strip()
            if cleaned:
                return cleaned
        return fallback

    def _format_price(self, price: float) -> str:
        formatted = (
            f"{price:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        )
        return f"R$ {formatted}"


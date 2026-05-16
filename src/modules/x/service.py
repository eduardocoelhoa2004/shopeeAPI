from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.shopee.models import ShopeeOffer
from src.modules.x.client import XClient

logger = logging.getLogger("app.x")

MAX_TWEET_LENGTH = 280
ELLIPSIS = "..."


class XPublisherService:
    def __init__(self, session: AsyncSession, x_client: XClient) -> None:
        self._session = session
        self._x_client = x_client

    async def publish_next_offer(self) -> bool:
        offer = await self._get_next_unpublished_offer()
        if offer is None:
            logger.info(
                "x_publish_skipped", extra={"data": {"reason": "no_unpublished_offers"}}
            )
            return False

        current_offer_id = str(offer.offer_id)
        message = self._format_offer_message(offer)
        sent = await self._x_client.post_tweet(message)
        if not sent:
            await self._session.rollback()
            logger.warning(
                "x_publish_failed", extra={"data": {"offer_id": current_offer_id}}
            )
            return False

        offer.is_published_x = True
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception(
                "x_publish_commit_failed",
                extra={"data": {"offer_id": current_offer_id}},
            )
            return False

        logger.info("x_offer_published", extra={"data": {"offer_id": current_offer_id}})
        return True

    async def _get_next_unpublished_offer(self) -> ShopeeOffer | None:
        stmt = (
            select(ShopeeOffer)
            .where(ShopeeOffer.is_published_x.is_(False))
            .order_by(ShopeeOffer.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _format_offer_message(self, offer: ShopeeOffer) -> str:
        hashtags = "#AchadosDaShopee #Promocao #Desconto"
        price = self._format_price(offer.price)
        short_url = offer.short_url.strip()
        name = " ".join(offer.name.split())
        suffix = f"\n\nPor apenas: {price}\nCompre aqui: {short_url}\n\n{hashtags}"

        max_name_length = MAX_TWEET_LENGTH - len(suffix)
        if max_name_length <= 0:
            fallback = f"{short_url}\n\n{hashtags}"
            return fallback[:MAX_TWEET_LENGTH]

        return f"{self._truncate(name, max_name_length)}{suffix}"

    def _format_price(self, price: float) -> str:
        formatted = (
            f"{price:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        )
        return f"R$ {formatted}"

    def _truncate(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        if max_length <= len(ELLIPSIS):
            return text[:max_length]
        return f"{text[: max_length - len(ELLIPSIS)].rstrip()}{ELLIPSIS}"

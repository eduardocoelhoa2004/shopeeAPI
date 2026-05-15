from __future__ import annotations

import html
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.shopee.models import ShopeeOffer
from src.modules.telegram.client import TelegramClient

logger = logging.getLogger("app.telegram.service")


class TelegramPublisherService:
    def __init__(self, session: AsyncSession, telegram_client: TelegramClient) -> None:
        self._session = session
        self._telegram_client = telegram_client

    async def publish_next_offer(self) -> bool:
        offer = await self._get_next_unpublished_offer()
        if offer is None:
            logger.info("telegram_publish_skipped", extra={"data": {"reason": "no_unpublished_offers"}})
            return False

        message = self._format_offer_message(offer)
        sent = await self._telegram_client.send_message(message)
        if not sent:
            await self._session.rollback()
            logger.warning("telegram_publish_failed", extra={"data": {"offer_id": offer.offer_id}})
            return False

        offer.is_published = True
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception("telegram_publish_commit_failed", extra={"data": {"offer_id": offer.offer_id}})
            return False

        logger.info("telegram_offer_published", extra={"data": {"offer_id": offer.offer_id}})
        return True

    async def _get_next_unpublished_offer(self) -> ShopeeOffer | None:
        stmt = (
            select(ShopeeOffer)
            .where(ShopeeOffer.is_published.is_(False))
            .order_by(ShopeeOffer.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _format_offer_message(self, offer: ShopeeOffer) -> str:
        name = html.escape(offer.name, quote=False)
        short_url = html.escape(offer.short_url, quote=False)
        return f"🔥 <b>{name}</b>\n💰 Por apenas: R$ {offer.price:.2f}\n🛒 Compre aqui: {short_url}"

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.external_apis.gemini import GeminiClient
from src.infrastructure.image.generator import ImageGeneratorService
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
        image_generator: ImageGeneratorService,
    ) -> None:
        self._session = session
        self._facebook_client = facebook_client
        self._gemini_client = gemini_client
        self._image_generator = image_generator

    async def publish_next_offer(self) -> bool:
        offers = await self._get_next_unpublished_offers(limit=1)
        if not offers:
            logger.info(
                "facebook_publish_skipped",
                extra={"data": {"reason": "no_unpublished_offers"}},
            )
            return False

        offer = offers[0]

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

    async def publish_text_batch(self, batch_size: int = 4) -> bool:
        try:
            offers = await self._get_next_unpublished_offers(limit=batch_size)
        
            if not offers or len(offers) == 0:
                logger.info("Nenhuma oferta pendente para publicar.")
                return False

            offers_data = []
            for offer in offers:
                offers_data.append({
                    "name": offer.name,
                    "price": self._format_price(offer.price),
                    "url": offer.short_url 
                })

            caption = await self._gemini_client.generate_batch_caption(offers_data)

            if not caption:
                caption = "🔥 TOP OFERTAS DO DIA 🔥\n\n"
                for item in offers_data:
                    caption += f"👉 {item['name']}\n💸 Por: {item['price']}\n🔗 {item['url']}\n\n"
                caption += HASHTAGS

            response = await self._facebook_client.post_offer(message=caption)

            if response:
                for offer in offers:
                    offer.is_published_facebook = True
                await self._session.commit()
                logger.info(f"Lote de {len(offers)} ofertas publicado com sucesso no Facebook!")
                return True
                
            return False

        except Exception:
            logger.exception("facebook_text_batch_publish_error")
            await self._session.rollback()
            return False

    async def preview_offer_batch_image(self, batch_size: int = 4) -> str | None:
        offers = await self._get_next_unpublished_offers(limit=batch_size)
        if not offers or len(offers) == 0:
            logger.info("facebook_preview_skipped", extra={"data": {"reason": "no_offers"}})
            return None

        image_data: list[dict[str, str | None]] = []
        for offer in offers:
            original_price = self._estimate_original_price(offer.price)
            image_data.append({
                "image_url": offer.image_url,
                "price": self._format_price(offer.price),
                "old_price": self._format_price(original_price),
                "discount": self._calculate_discount(offer.price),
            })

        output_path = "preview_top_deals.jpg"
        await self._image_generator.generate_image(
            offers_data=image_data,
            output_path=output_path,
            template_type="top_deals",
        )
        return output_path

    async def _get_next_unpublished_offers(self, limit: int = 4) -> list[ShopeeOffer]:
        stmt = (
            select(ShopeeOffer)
            .where(ShopeeOffer.is_published_facebook.is_(False))
            .order_by(ShopeeOffer.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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

    def _estimate_original_price(self, current_price: float, markup: float = 0.30) -> float:
        """Simula o preço original assumindo que era markup% mais caro."""
        return current_price * (1 + markup)

    def _calculate_discount(self, current_price: float, markup: float = 0.30) -> int:
        """Simula o desconto assumindo que o preço original era markup% mais caro."""
        original_price = self._estimate_original_price(current_price, markup)
        discount = int(((original_price - current_price) / original_price) * 100)
        return discount


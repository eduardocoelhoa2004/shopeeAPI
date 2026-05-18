from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import settings
from src.infrastructure.external_apis.gemini import GeminiClient
from src.infrastructure.image.generator import ImageGeneratorService
from src.modules.facebook.client import FacebookClient
from src.modules.shopee.models import ShopeeOffer

logger = logging.getLogger("app.facebook.service")

HASHTAGS = "#AchadosDaShopee #Ofertas"
CAPTION_MAX_NAME_LEN = 60
FLASH_DISCOUNT_THRESHOLD = 50


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

    async def publish_smart_batch(self) -> bool:
        offers = await self._get_next_unpublished_offers(limit=4)
        if not offers:
            logger.info("facebook_smart_publish_skipped", extra={"data": {"reason": "no_unpublished_offers"}})
            return False

        first = offers[0]
        template_type, selected_offers = self._route_template(first, offers)

        logger.info(
            "smart_routing_decision",
            extra={"data": {"template": template_type, "count": len(selected_offers)}},
        )

        caption = self._build_rich_caption(selected_offers)

        image_data: list[dict[str, str | None]] = []
        for offer in selected_offers:
            old_price = offer.old_price if offer.old_price > 0 else self._estimate_original_price(offer.price)
            discount = offer.discount if offer.discount > 0 else self._calculate_discount(offer.price)
            image_data.append({
                "image_url": offer.image_url,
                "price": self._format_price(offer.price),
                "old_price": self._format_price(old_price),
                "discount": discount,
            })

        output_path = f"smart_{template_type}.jpg"
        try:
            await self._image_generator.generate_image(
                offers_data=image_data,
                output_path=output_path,
                template_type=template_type,
            )
        except Exception:
            logger.exception("smart_image_generation_failed")
            return False

        try:
            result = await self._facebook_client.post_photo(message=caption, image_path=output_path)
        except Exception:
            await self._session.rollback()
            logger.exception("smart_publish_error")
            return False

        if not result:
            await self._session.rollback()
            logger.warning("smart_publish_failed")
            return False

        for offer in selected_offers:
            offer.is_published_facebook = True

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception("smart_publish_commit_failed")
            return False

        ids = [str(o.offer_id) for o in selected_offers]
        logger.info("smart_publish_success", extra={"data": {"offer_ids": ids, "template": template_type}})
        return True

    def _route_template(
        self, first: ShopeeOffer, offers: list[ShopeeOffer]
    ) -> tuple[str, list[ShopeeOffer]]:
        is_flash = self._is_flash_offer(first)
        if is_flash:
            return "relampago", [first]

        if len(offers) >= 4:
            return "top_deals", offers[:4]

        return "achadinho", [offers[0]]

    def _is_flash_offer(self, offer: ShopeeOffer) -> bool:
        if offer.period_end_time is not None:
            if offer.period_end_time > datetime.now(timezone.utc):
                return True

        if offer.discount is not None and offer.discount >= FLASH_DISCOUNT_THRESHOLD:
            return True

        return False

    def _build_rich_caption(self, offers: list[ShopeeOffer]) -> str:
        lines: list[str] = []
        for i, offer in enumerate(offers, start=1):
            truncated_name = offer.name[:CAPTION_MAX_NAME_LEN]
            if len(offer.name) > CAPTION_MAX_NAME_LEN:
                truncated_name += "..."

            old_price = offer.old_price if offer.old_price > 0 else self._estimate_original_price(offer.price)
            old_price_str = self._format_price(old_price)
            new_price_str = self._format_price(offer.price)

            if len(offers) > 1:
                lines.append(f"{i}. 🛍️ {truncated_name}")
            else:
                lines.append(f"🛍️ {truncated_name}")

            lines.append(f"❌ De: {old_price_str}")
            lines.append(f"✅ Por: {new_price_str}")
            lines.append(f"🔗 Compre aqui: {offer.short_url}")
            lines.append("")

        telegram_link = settings.telegram.group_link
        lines.append("🚨 Não perca mais nenhuma promoção ou cupom!")
        lines.append(f"👉 Entre agora no nosso grupo VIP do Telegram: {telegram_link}")
        lines.append("")
        lines.append(HASHTAGS)

        return "\n".join(lines)

    async def preview_offer_batch_image(self, batch_size: int = 4, template_type: str = "top_deals") -> str | None:
        offers = await self._get_next_unpublished_offers(limit=batch_size)
        if not offers or len(offers) == 0:
            logger.info("facebook_preview_skipped", extra={"data": {"reason": "no_offers"}})
            return None

        image_data: list[dict[str, str | None]] = []
        for offer in offers:
            old_price = offer.old_price if offer.old_price > 0 else self._estimate_original_price(offer.price)
            discount = offer.discount if offer.discount > 0 else self._calculate_discount(offer.price)
            image_data.append({
                "image_url": offer.image_url,
                "price": self._format_price(offer.price),
                "old_price": self._format_price(old_price),
                "discount": discount,
            })

        output_path = f"preview_{template_type}.jpg"
        await self._image_generator.generate_image(
            offers_data=image_data,
            output_path=output_path,
            template_type=template_type,
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


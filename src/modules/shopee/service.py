from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.shopee.client import ShopeeAffiliateClient
from src.modules.shopee.models import ShopeeOffer

logger = logging.getLogger("app.shopee.service")


class ShopeeOfferService:
    def __init__(self, session: AsyncSession, client: ShopeeAffiliateClient) -> None:
        self._session = session
        self._client = client

    async def fetch_and_process_offers(self, limit: int = 20) -> dict[str, int]:
        summary = {"processed": 0, "inserted": 0, "skipped": 0, "failed": 0}

        response = await self._client.get_offer_list(limit=limit, offset=0)
        if not response.get("success"):
            logger.warning("shopee_offer_list_failed")
            return summary

        offers = self._extract_offers(response)
        for raw_offer in offers:
            summary["processed"] += 1
            status = await self._process_offer(raw_offer)
            summary[status] += 1

        logger.info("shopee_offer_batch_complete", extra={"data": summary})
        return summary

    async def _process_offer(self, raw_offer: dict[str, Any] | Any) -> str:
        offer = raw_offer if isinstance(raw_offer, dict) else {}
        offer_id = self._coerce_str(
            offer.get("itemId")
            or offer.get("offerId")
            or offer.get("offer_id")
            or offer.get("item_id")
            or offer.get("itemId")
            or offer.get("id")
        )
        if not offer_id:
            logger.info(
                "shopee_offer_skipped", extra={"data": {"reason": "missing_offer_id"}}
            )
            return "skipped"

        if await self._offer_exists(offer_id):
            logger.info(
                "shopee_offer_skipped",
                extra={"data": {"reason": "duplicate", "offer_id": offer_id}},
            )
            return "skipped"

        mapped = self._map_offer_fields(offer)
        if mapped is None:
            logger.info(
                "shopee_offer_skipped",
                extra={"data": {"reason": "invalid_payload", "offer_id": offer_id}},
            )
            return "skipped"

        short_result = await self._client.generate_short_link(
            original_url=mapped["original_url"]
        )
        if not short_result.get("success"):
            logger.warning(
                "shopee_offer_short_link_failed",
                extra={"data": {"offer_id": offer_id}},
            )
            return "failed"

        short_url = self._extract_short_link(short_result)
        if not short_url:
            logger.warning(
                "shopee_offer_short_link_missing",
                extra={"data": {"offer_id": offer_id}},
            )
            return "failed"

        new_offer = ShopeeOffer(
            offer_id=offer_id,
            name=mapped["name"],
            price=mapped["price"],
            old_price=mapped["old_price"],
            discount=mapped["discount"],
            period_end_time=mapped["period_end_time"],
            commission_rate=mapped["commission_rate"],
            original_url=mapped["original_url"],
            short_url=short_url,
            image_url=mapped.get("image_url"),
            is_published=False,
            is_published_facebook=False,
        )

        try:
            self._session.add(new_offer)
            await self._session.commit()
            logger.info("shopee_offer_inserted", extra={"data": {"offer_id": offer_id}})
            return "inserted"
        except IntegrityError:
            await self._session.rollback()
            logger.info(
                "shopee_offer_skipped",
                extra={"data": {"reason": "duplicate", "offer_id": offer_id}},
            )
            return "skipped"
        except Exception:
            await self._session.rollback()
            logger.exception(
                "shopee_offer_persist_failed",
                extra={"data": {"offer_id": offer_id}},
            )
            return "failed"

    async def _offer_exists(self, offer_id: str) -> bool:
        stmt = select(ShopeeOffer.id).where(ShopeeOffer.offer_id == offer_id).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _extract_offers(self, response: dict[str, Any]) -> Iterable[dict[str, Any]]:
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        nodes = []
        if isinstance(data.get("productOfferV2"), dict):
            nodes = data.get("productOfferV2", {}).get("nodes")
        elif isinstance(data.get("getOfferList"), dict):
            nodes = data.get("getOfferList", {}).get("nodes")
        offers = (
            nodes
            or data.get("nodes")
            or data.get("offers")
            or data.get("list")
            or data.get("items")
            or []
        )
        if isinstance(offers, list):
            return [item for item in offers if isinstance(item, dict)]
        return []

    def _normalize_price(self, value: Any) -> float:
        """Normaliza o preco de forma inteligente, evitando dividir valores ja formatados."""
        try:
            if not value:
                return 0.0
            val = float(value)
            if val > 10000:
                return val / 100000.0
            return val
        except (ValueError, TypeError):
            return 0.0

    def _normalize_discount(self, value: Any) -> int:
        try:
            if not value:
                return 0
            if isinstance(value, str) and "%" in value:
                return int(float(value.replace("%", "").strip()))
            discount = float(value)
            if 0 < discount <= 1:
                return int(discount * 100)
            return min(int(discount), 99)
        except (ValueError, TypeError):
            return 0

    def _map_offer_fields(self, offer: dict[str, Any]) -> dict[str, Any] | None:
        # Incluído productName
        name = self._coerce_str(
            offer.get("productName") or offer.get("itemName") or offer.get("offerName") or offer.get("name")
        )
        original_url = self._coerce_str(
            offer.get("productLink") or offer.get("itemUri") or offer.get("itemUrl")
        )

        price_min = self._normalize_price(
            offer.get("priceMin") or offer.get("minPrice") or offer.get("price") or 0
        )
        price_max = self._normalize_price(
            offer.get("priceMax") or offer.get("maxPrice") or offer.get("originalPrice") or 0
        )

        # Incluído priceDiscountRate
        discount_rate = self._normalize_discount(
            offer.get("priceDiscountRate") or offer.get("discountRate") or offer.get("discount") or 0
        )
        period_end_time = offer.get("periodEndTime") or offer.get("endTime") or offer.get("end_time") or 0

        commission_rate = self._to_float(
            offer.get("commissionRate") or offer.get("commission_rate") or offer.get("commission")
        )
        image_url = self._coerce_str(
            offer.get("imageUrl") or offer.get("image") or offer.get("image_url")
        )

        # Atualizado o log para buscar o itemId corretamente em vez de dar N/A
        if not name or not original_url:
            logger.warning(f"Produto pulado (Sem nome ou URL). ID: {offer.get('itemId') or offer.get('offerId')}")
            return None

        if price_min == 0.0 or commission_rate is None:
            logger.warning(f"Produto pulado (Preço Zero ou Sem Comissão). Preço: {price_min} | Comissão: {commission_rate} | ID: {offer.get('itemId') or offer.get('offerId')}")
            return None

        if price_max <= price_min and discount_rate > 0:
            price_max = price_min / (1 - (discount_rate / 100.0))

        if price_max <= price_min:
            price_max = 0.0
            discount_rate = 0

        return {
            "name": name,
            "original_url": original_url,
            "price": price_min,
            "old_price": price_max,
            "discount": discount_rate,
            "period_end_time": period_end_time,
            "commission_rate": commission_rate,
            "image_url": image_url,
        }

    def _extract_short_link(self, response: dict[str, Any]) -> str | None:
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        short_link = (
            data.get("short_link")
            or data.get("shortLink")
            or data.get("short_link_url")
            or data.get("shortLinkUrl")
        )
        return self._coerce_str(short_link)

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            ts = int(value)
            if ts <= 0:
                return None
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (TypeError, ValueError):
            return None

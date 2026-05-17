from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.modules.shopee.client import ShopeeAffiliateClient
from src.modules.shopee.models import ShopeeOffer
from src.modules.shopee.service import ShopeeOfferService


class FakeScalarsResult:
    def __init__(self, offers: list[ShopeeOffer]) -> None:
        self._offers = offers

    def first(self) -> ShopeeOffer | None:
        return self._offers[0] if self._offers else None

    def all(self) -> list[ShopeeOffer]:
        return self._offers


class FakeResult:
    def __init__(self, offers: list[ShopeeOffer]) -> None:
        self._offers = offers

    def scalars(self) -> FakeScalarsResult:
        return FakeScalarsResult(self._offers)

    def scalar_one_or_none(self) -> ShopeeOffer | None:
        return self._offers[0] if self._offers else None


class FakeSession:
    def __init__(self, existing_offers: list[ShopeeOffer] | None = None) -> None:
        self._existing = existing_offers or []
        self.added: list[ShopeeOffer] = []
        self.committed = False

    async def execute(self, _: Any) -> FakeResult:
        return FakeResult(self._existing)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


class FakeShopeeClient:
    def __init__(
        self,
        offer_list_response: dict[str, Any] | None = None,
        short_link_response: dict[str, Any] | None = None,
    ) -> None:
        self._offer_list_response = offer_list_response or {
            "success": True,
            "data": {"productOfferV2": {"nodes": []}},
            "error": None,
        }
        self._short_link_response = short_link_response or {
            "success": True,
            "data": {"short_link": "https://s.shopee/short"},
            "error": None,
        }
        self.short_link_calls: list[str] = []

    async def get_offer_list(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return self._offer_list_response

    async def generate_short_link(self, original_url: str) -> dict[str, Any]:
        self.short_link_calls.append(original_url)
        return self._short_link_response


def _raw_offer(offer_id: str = "item-123") -> dict[str, Any]:
    return {
        "itemId": offer_id,
        "productName": "Fone Bluetooth",
        "priceMin": 49.90,
        "commissionRate": 8.5,
        "productLink": "https://shopee.com/product/123",
        "imageUrl": "https://img.shopee.com/123.jpg",
    }


def test_fetch_and_process_offers_inserts_new_offers() -> None:
    session = FakeSession()
    client = FakeShopeeClient(
        offer_list_response={
            "success": True,
            "data": {"productOfferV2": {"nodes": [_raw_offer()]}},
            "error": None,
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 1
    assert summary["inserted"] == 1
    assert summary["skipped"] == 0
    assert summary["failed"] == 0
    assert len(session.added) == 1
    assert session.committed is True
    assert session.added[0].offer_id == "item-123"
    assert session.added[0].name == "Fone Bluetooth"
    assert session.added[0].price == 49.90
    assert session.added[0].short_url == "https://s.shopee/short"


def test_fetch_and_process_offers_skips_existing_offer() -> None:
    existing = ShopeeOffer(
        offer_id="item-123",
        name="Fone Bluetooth",
        price=49.90,
        commission_rate=8.5,
        original_url="https://shopee.com/product/123",
        short_url="https://s.shopee/short",
        is_published=False,
        is_published_facebook=False,
        created_at=datetime.now(timezone.utc),
    )
    session = FakeSession(existing_offers=[existing])
    client = FakeShopeeClient(
        offer_list_response={
            "success": True,
            "data": {"productOfferV2": {"nodes": [_raw_offer()]}},
            "error": None,
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 1
    assert summary["inserted"] == 0
    assert summary["skipped"] == 1
    assert len(session.added) == 0


def test_fetch_and_process_offers_returns_empty_summary_on_api_failure() -> None:
    session = FakeSession()
    client = FakeShopeeClient(
        offer_list_response={
            "success": False,
            "data": {},
            "error": "api_error",
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 0
    assert summary["inserted"] == 0
    assert len(session.added) == 0


def test_fetch_and_process_offers_handles_empty_nodes() -> None:
    session = FakeSession()
    client = FakeShopeeClient(
        offer_list_response={
            "success": True,
            "data": {"productOfferV2": {"nodes": []}},
            "error": None,
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 0
    assert summary["inserted"] == 0


def test_fetch_and_process_offers_skips_offer_without_id() -> None:
    raw = {"productName": "Sem ID", "priceMin": 10.0}
    session = FakeSession()
    client = FakeShopeeClient(
        offer_list_response={
            "success": True,
            "data": {"productOfferV2": {"nodes": [raw]}},
            "error": None,
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 1
    assert summary["skipped"] == 1
    assert summary["inserted"] == 0


def test_fetch_and_process_offers_handles_multiple_offers() -> None:
    offers = [_raw_offer("item-1"), _raw_offer("item-2"), _raw_offer("item-3")]
    session = FakeSession()
    client = FakeShopeeClient(
        offer_list_response={
            "success": True,
            "data": {"productOfferV2": {"nodes": offers}},
            "error": None,
        },
    )
    service = ShopeeOfferService(session=session, client=client)

    summary = asyncio.run(service.fetch_and_process_offers(limit=10))

    assert summary["processed"] == 3
    assert summary["inserted"] == 3
    assert len(session.added) == 3

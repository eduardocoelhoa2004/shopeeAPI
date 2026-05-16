from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.external_apis.gemini import GeminiClient
from src.modules.facebook.client import FacebookClient
from src.modules.facebook.service import FacebookPublisherService
from src.modules.shopee.models import ShopeeOffer


class FakeScalarResult:
    def __init__(self, offer: ShopeeOffer | None) -> None:
        self._offer = offer

    def scalar_one_or_none(self) -> ShopeeOffer | None:
        return self._offer


class FakeSession:
    def __init__(self, offer: ShopeeOffer | None) -> None:
        self._offer = offer
        self.committed = False
        self.rolled_back = False

    async def execute(self, _: Any) -> FakeScalarResult:
        return FakeScalarResult(self._offer)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeFacebookClient:
    def __init__(self, posted: bool = True) -> None:
        self._posted = posted
        self.message: str | None = None
        self.link: str | None = None

    async def post_offer(self, message: str, link: str) -> bool:
        self.message = message
        self.link = link
        return self._posted


class FakeGeminiClient:
    def __init__(self, caption: str | None = None) -> None:
        self._caption = caption

    async def generate_caption(self, name: str, price: str, url: str) -> str | None:
        return self._caption


def _offer() -> ShopeeOffer:
    return ShopeeOffer(
        offer_id="offer-1",
        name="Produto   Especial",
        price=19.9,
        commission_rate=12.5,
        original_url="https://example.com/original",
        short_url="https://example.com/short",
        is_published=False,
        is_published_facebook=False,
        created_at=datetime.now(timezone.utc),
    )


def test_publish_next_offer_posts_to_facebook_and_marks_as_published() -> None:
    offer = _offer()
    session = FakeSession(offer)
    facebook_client = FakeFacebookClient()
    gemini_client = FakeGeminiClient()
    service = FacebookPublisherService(
        session=cast(AsyncSession, session),
        facebook_client=cast(FacebookClient, facebook_client),
        gemini_client=cast(GeminiClient, gemini_client),
    )

    published = asyncio.run(service.publish_next_offer())

    assert published is True
    assert offer.is_published_facebook is True
    assert session.committed is True
    assert session.rolled_back is False
    assert facebook_client.message == (
        "Produto Especial\n\n" "Por apenas: R$ 19,90\n\n" "#AchadosDaShopee #Ofertas"
    )
    assert facebook_client.link == "https://example.com/short"


def test_publish_next_offer_rolls_back_when_post_fails() -> None:
    offer = _offer()
    session = FakeSession(offer)
    facebook_client = FakeFacebookClient(posted=False)
    gemini_client = FakeGeminiClient()
    service = FacebookPublisherService(
        session=cast(AsyncSession, session),
        facebook_client=cast(FacebookClient, facebook_client),
        gemini_client=cast(GeminiClient, gemini_client),
    )

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert offer.is_published_facebook is False
    assert session.committed is False
    assert session.rolled_back is True


def test_publish_next_offer_returns_false_when_queue_is_empty() -> None:
    session = FakeSession(None)
    facebook_client = FakeFacebookClient()
    gemini_client = FakeGeminiClient()
    service = FacebookPublisherService(
        session=cast(AsyncSession, session),
        facebook_client=cast(FacebookClient, facebook_client),
        gemini_client=cast(GeminiClient, gemini_client),
    )

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert session.committed is False
    assert facebook_client.message is None

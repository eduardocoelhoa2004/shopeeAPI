from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.modules.shopee.models import ShopeeOffer
from src.modules.x.service import XPublisherService


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


class FakeXClient:
    def __init__(self, posted: bool = True) -> None:
        self._posted = posted
        self.message: str | None = None

    async def post_tweet(self, text: str) -> bool:
        self.message = text
        return self._posted


def _offer() -> ShopeeOffer:
    return ShopeeOffer(
        offer_id="offer-1",
        name="Produto Especial",
        price=19.9,
        commission_rate=12.5,
        original_url="https://example.com/original",
        short_url="https://example.com/short",
        is_published=False,
        is_published_x=False,
        created_at=datetime.now(timezone.utc),
    )


def test_publish_next_offer_posts_tweet_and_marks_as_published_x() -> None:
    offer = _offer()
    session = FakeSession(offer)
    x_client = FakeXClient()
    service = XPublisherService(session=session, x_client=x_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is True
    assert offer.is_published_x is True
    assert session.committed is True
    assert session.rolled_back is False
    assert x_client.message == (
        "Produto Especial\n\n"
        "Por apenas: R$ 19,90\n"
        "Compre aqui: https://example.com/short\n\n"
        "#AchadosDaShopee #Promocao #Desconto"
    )


def test_publish_next_offer_rolls_back_when_post_fails() -> None:
    offer = _offer()
    session = FakeSession(offer)
    x_client = FakeXClient(posted=False)
    service = XPublisherService(session=session, x_client=x_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert offer.is_published_x is False
    assert session.committed is False
    assert session.rolled_back is True


def test_publish_next_offer_returns_false_when_queue_is_empty() -> None:
    session = FakeSession(None)
    x_client = FakeXClient()
    service = XPublisherService(session=session, x_client=x_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert session.committed is False
    assert x_client.message is None

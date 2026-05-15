from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.modules.shopee.models import ShopeeOffer
from src.modules.telegram.service import TelegramPublisherService


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


class FakeTelegramClient:
    def __init__(self, sent: bool = True) -> None:
        self._sent = sent
        self.message: str | None = None

    async def send_message(self, text: str) -> bool:
        self.message = text
        return self._sent


def _offer() -> ShopeeOffer:
    return ShopeeOffer(
        offer_id="offer-1",
        name="Produto <Especial>",
        price=19.9,
        commission_rate=12.5,
        original_url="https://example.com/original",
        short_url="https://example.com/short?a=1&b=2",
        is_published=False,
        created_at=datetime.now(timezone.utc),
    )


def test_publish_next_offer_sends_message_and_marks_as_published() -> None:
    offer = _offer()
    session = FakeSession(offer)
    telegram_client = FakeTelegramClient()
    service = TelegramPublisherService(session=session, telegram_client=telegram_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is True
    assert offer.is_published is True
    assert session.committed is True
    assert session.rolled_back is False
    assert telegram_client.message == (
        "🔥 <b>Produto &lt;Especial&gt;</b>\n"
        "💰 Por apenas: R$ 19.90\n"
        "🛒 Compre aqui: https://example.com/short?a=1&amp;b=2"
    )


def test_publish_next_offer_does_not_commit_when_send_fails() -> None:
    offer = _offer()
    session = FakeSession(offer)
    telegram_client = FakeTelegramClient(sent=False)
    service = TelegramPublisherService(session=session, telegram_client=telegram_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert offer.is_published is False
    assert session.committed is False
    assert session.rolled_back is True


def test_publish_next_offer_returns_false_when_queue_is_empty() -> None:
    session = FakeSession(None)
    telegram_client = FakeTelegramClient()
    service = TelegramPublisherService(session=session, telegram_client=telegram_client)

    published = asyncio.run(service.publish_next_offer())

    assert published is False
    assert session.committed is False
    assert telegram_client.message is None

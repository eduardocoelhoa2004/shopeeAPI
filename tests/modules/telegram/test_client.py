from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.core.config.settings import TelegramSettings
from src.modules.telegram.client import TelegramClient


class FakeResponse:
    status_code = 200
    is_success = True

    def json(self) -> dict[str, Any]:
        return {"ok": True}


class FakeHttpClient:
    def __init__(self) -> None:
        self.path: str | None = None
        self.payload: dict[str, Any] | None = None

    async def post(self, url: str, *, json: dict[str, Any] | None = None, **_: Any) -> FakeResponse:
        self.path = url
        self.payload = json
        return FakeResponse()


def test_send_message_posts_expected_payload() -> None:
    http_client = FakeHttpClient()
    settings = TelegramSettings(bot_token="token-123", chat_id="chat-456")
    client = TelegramClient(http_client=http_client, telegram_settings=settings)

    sent = asyncio.run(client.send_message("  oferta especial  "))

    assert sent is True
    assert http_client.path == "/bottoken-123/sendMessage"
    assert http_client.payload == {
        "chat_id": "chat-456",
        "text": "oferta especial",
        "parse_mode": "HTML",
    }


def test_send_message_rejects_empty_text() -> None:
    http_client = FakeHttpClient()
    settings = TelegramSettings(bot_token="token-123", chat_id="chat-456")
    client = TelegramClient(http_client=http_client, telegram_settings=settings)

    with pytest.raises(ValueError, match="text must not be empty"):
        asyncio.run(client.send_message(" "))

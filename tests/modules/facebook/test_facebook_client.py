from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.core.config.settings import FacebookSettings
from src.modules.facebook.client import FacebookClient


class FakeResponse:
    def __init__(self, *, is_success: bool = True, status_code: int = 200) -> None:
        self.is_success = is_success
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return {"id": "post-1"} if self.is_success else {"error": {"message": "nope"}}


class FakeHttpClient:
    def __init__(self, response: FakeResponse | None = None) -> None:
        self._response = response or FakeResponse()
        self.path: str | None = None
        self.payload: dict[str, Any] | None = None
        self.headers: dict[str, str] | None = None

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **_: Any,
    ) -> FakeResponse:
        self.path = url
        self.payload = json
        self.headers = headers
        return self._response


def _settings() -> FacebookSettings:
    return FacebookSettings(page_id="page-123", access_token="token-456")


def test_post_offer_posts_expected_payload_and_headers() -> None:
    http_client = FakeHttpClient()
    client = FacebookClient(http_client=http_client, facebook_settings=_settings())

    posted = asyncio.run(
        client.post_offer("  oferta especial  ", " https://s.shopee.com.br/x ")
    )

    assert posted is True
    assert http_client.path == "/page-123/feed"
    assert http_client.payload == {
        "message": "oferta especial",
        "link": "https://s.shopee.com.br/x",
    }
    assert http_client.headers == {"Authorization": "Bearer token-456"}


def test_post_offer_returns_false_when_graph_api_rejects_post() -> None:
    http_client = FakeHttpClient(FakeResponse(is_success=False, status_code=400))
    client = FacebookClient(http_client=http_client, facebook_settings=_settings())

    posted = asyncio.run(
        client.post_offer("oferta especial", "https://s.shopee.com.br/x")
    )

    assert posted is False


def test_post_offer_rejects_empty_message() -> None:
    http_client = FakeHttpClient()
    client = FacebookClient(http_client=http_client, facebook_settings=_settings())

    with pytest.raises(ValueError, match="message must not be empty"):
        asyncio.run(client.post_offer(" ", "https://s.shopee.com.br/x"))

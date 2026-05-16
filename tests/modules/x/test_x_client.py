from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.modules.x.client import XClient


class FakeTweetClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.text: str | None = None

    async def create_tweet(self, *, text: str) -> dict[str, Any]:
        self.text = text
        if self.should_fail:
            raise RuntimeError("x unavailable")
        return {"data": {"id": "tweet-1"}}


def test_post_tweet_creates_tweet_with_cleaned_text() -> None:
    tweet_client = FakeTweetClient()
    client = XClient(tweet_client=tweet_client)

    posted = asyncio.run(client.post_tweet("  oferta especial  "))

    assert posted is True
    assert tweet_client.text == "oferta especial"


def test_post_tweet_returns_false_when_tweepy_fails() -> None:
    tweet_client = FakeTweetClient(should_fail=True)
    client = XClient(tweet_client=tweet_client)

    posted = asyncio.run(client.post_tweet("oferta especial"))

    assert posted is False


def test_post_tweet_rejects_empty_text() -> None:
    tweet_client = FakeTweetClient()
    client = XClient(tweet_client=tweet_client)

    with pytest.raises(ValueError, match="text must not be empty"):
        asyncio.run(client.post_tweet(" "))

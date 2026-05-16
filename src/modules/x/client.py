from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from src.core.config.settings import XSettings, settings

logger = logging.getLogger("app.x")


class TweetClient(Protocol):
    async def create_tweet(self, *, text: str) -> Any: ...


class XClient:
    def __init__(
        self,
        tweet_client: TweetClient | None = None,
        x_settings: XSettings | None = None,
    ) -> None:
        self._client = tweet_client or self._build_client(x_settings or settings.x)

    async def post_tweet(self, text: str) -> bool:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must not be empty")

        try:
            response = await self._client.create_tweet(text=cleaned_text)
        except Exception:
            logger.exception("x_post_tweet_failed")
            return False

        logger.info(
            "x_post_tweet_success",
            extra={"data": {"tweet_id": self._extract_tweet_id(response)}},
        )
        return True

    def _build_client(self, x_settings: XSettings) -> TweetClient:
        try:
            from tweepy.asynchronous import AsyncClient  # type: ignore[import-not-found, import-untyped]
        except ImportError as exc:
            raise RuntimeError("tweepy v4+ is required to publish offers on X") from exc

        return cast(
            TweetClient,
            AsyncClient(
                consumer_key=x_settings.api_key.get_secret_value(),
                consumer_secret=x_settings.api_secret.get_secret_value(),
                access_token=x_settings.access_token.get_secret_value(),
                access_token_secret=x_settings.access_secret.get_secret_value(),
                wait_on_rate_limit=True,
            ),
        )

    def _extract_tweet_id(self, response: Any) -> str | None:
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            tweet_id = data.get("id")
            if tweet_id is not None:
                return str(tweet_id)
        return None

from __future__ import annotations

import logging
from typing import Any

from src.core.config.settings import FacebookSettings, settings
from src.infrastructure.external_apis.http_client import AsyncHttpClient

FACEBOOK_GRAPH_API_BASE_URL = "https://graph.facebook.com/v19.0"

logger = logging.getLogger("app.facebook")


class FacebookClient:
    def __init__(
        self,
        http_client: AsyncHttpClient,
        facebook_settings: FacebookSettings | None = None,
    ) -> None:
        self._settings = facebook_settings or settings.facebook
        self._client = http_client

    async def post_offer(self, message: str, link: str) -> bool:
        cleaned_message = message.strip()
        cleaned_link = link.strip()
        if not cleaned_message:
            raise ValueError("message must not be empty")
        if not cleaned_link:
            raise ValueError("link must not be empty")

        payload = {"message": cleaned_message, "link": cleaned_link}
        headers = {
            "Authorization": (
                f"Bearer {self._settings.access_token.get_secret_value()}"
            )
        }

        try:
            response = await self._client.post(
                f"/{self._settings.page_id}/feed",
                json=payload,
                headers=headers,
            )
        except Exception:
            logger.exception("facebook_post_offer_failed")
            return False

        if response.is_success:
            logger.info(
                "facebook_post_offer_success",
                extra={"data": {"status_code": response.status_code}},
            )
            return True

        logger.error(
            "facebook_post_offer_rejected",
            extra={
                "data": {
                    "status_code": response.status_code,
                    "response": self._safe_json(response),
                }
            },
        )
        return False

    def _safe_json(self, response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

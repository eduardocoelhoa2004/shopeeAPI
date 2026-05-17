from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

import aiofiles
import httpx

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

    async def post_offer(self, message: str, link: str | None = None) -> bool:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("message must not be empty")

        payload = {"message": cleaned_message}
        if link is not None:
            cleaned_link = link.strip()
            if cleaned_link:
                payload["link"] = cleaned_link

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

    async def post_photo(self, message: str, image_path: str) -> dict[str, Any]:
        cleaned_message = message.strip()
        cleaned_path = image_path.strip()
        if not cleaned_message:
            raise ValueError("message must not be empty")
        if not cleaned_path:
            raise ValueError("image_path must not be empty")

        file_path = Path(cleaned_path)
        if not file_path.exists():
            logger.warning(
                "facebook_post_photo_missing_file",
                extra={"data": {"image_path": cleaned_path}},
            )
            return {}

        try:
            async with aiofiles.open(file_path, "rb") as file_handle:
                image_bytes = await file_handle.read()
        except Exception:
            logger.exception(
                "facebook_post_photo_read_failed",
                extra={"data": {"image_path": cleaned_path}},
            )
            return {}

        if not image_bytes:
            logger.warning(
                "facebook_post_photo_empty_file",
                extra={"data": {"image_path": cleaned_path}},
            )
            return {}

        content_type = mimetypes.guess_type(file_path.name)[0] or "image/jpeg"
        files = {
            "source": (file_path.name, image_bytes, content_type),
        }
        data = {
            "message": cleaned_message,
            "access_token": self._settings.access_token.get_secret_value(),
        }
        endpoint = f"/{self._settings.page_id}/photos"

        try:
            async with httpx.AsyncClient(base_url=FACEBOOK_GRAPH_API_BASE_URL) as client:
                response = await client.post(endpoint, data=data, files=files)
        except Exception:
            logger.exception("facebook_post_photo_failed")
            return {}

        payload = self._safe_json(response)
        if response.is_success:
            logger.info(
                "facebook_post_photo_success",
                extra={"data": {"status_code": response.status_code}},
            )
            return payload

        logger.error(
            "facebook_post_photo_rejected",
            extra={
                "data": {
                    "status_code": response.status_code,
                    "response": payload,
                }
            },
        )
        return {}

    def _safe_json(self, response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

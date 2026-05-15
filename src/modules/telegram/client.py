from __future__ import annotations

import logging
from typing import Any

from src.core.config.settings import TelegramSettings, settings
from src.infrastructure.external_apis.http_client import AsyncHttpClient

logger = logging.getLogger("app.telegram")


class TelegramClient:
    def __init__(
        self,
        http_client: AsyncHttpClient | None = None,
        telegram_settings: TelegramSettings | None = None,
    ) -> None:
        self._settings = telegram_settings or settings.telegram
        self._client = http_client or AsyncHttpClient(base_url=self._settings.base_url)

    async def send_message(self, text: str) -> bool:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("text must not be empty")

        payload: dict[str, Any] = {
            "chat_id": self._settings.chat_id,
            "text": cleaned_text,
            "parse_mode": "HTML",
        }
        path = f"/bot{self._settings.bot_token.get_secret_value()}/sendMessage"

        try:
            response = await self._client.post(path, json=payload)
        except Exception:
            logger.exception("telegram_send_message_failed")
            return False

        body = self._safe_json(response)
        ok = body.get("ok") is True
        if response.is_success and ok:
            logger.info(
                "telegram_send_message_success",
                extra={"data": {"status_code": response.status_code}},
            )
            return True

        logger.warning(
            "telegram_send_message_rejected",
            extra={"data": {"status_code": response.status_code, "telegram_ok": ok}},
        )
        print(f"\n--- ERRO DO TELEGRAM ---\n{body}\n------------------------\n")
        return False

    def _safe_json(self, response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

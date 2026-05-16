from __future__ import annotations

import logging
from typing import Any

from src.core.config.settings import GeminiSettings, settings
from src.infrastructure.external_apis.http_client import AsyncHttpClient

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"

logger = logging.getLogger("app.gemini")


class GeminiClient:
    def __init__(
        self,
        http_client: AsyncHttpClient,
        gemini_settings: GeminiSettings | None = None,
    ) -> None:
        self._client = http_client
        self._settings = gemini_settings or settings.gemini

    async def generate_caption(self, name: str, price: str, url: str) -> str | None:
        prompt = (
            "Voce e um copywriter do projeto Achados da Shopee. "
            "Escreva uma legenda curta, persuasiva e magnetica para Facebook. "
            "Use emojis e gatilhos mentais de escassez e oportunidade. "
            "Inclua obrigatoriamente a URL fornecida no texto. "
            "Use exatamente o nome e o preco informados. "
            "Inclua as hashtags #AchadosDaShopee #Ofertas ao final. "
            "Retorne apenas a legenda final, sem aspas e sem comentarios.\n\n"
            f"Nome: {name}\n"
            f"Preco: {price}\n"
            f"Link: {url}\n"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }
        endpoint = (
            f"/v1beta/models/{GEMINI_MODEL_ID}:generateContent"
            f"?key={self._settings.api_key.get_secret_value()}"
        )

        try:
            response = await self._client.post(endpoint, json=payload)
        except Exception:
            logger.warning("gemini_generate_caption_failed", exc_info=True)
            return None

        if not response.is_success:
            logger.warning(
                "gemini_generate_caption_rejected",
                extra={"data": {"status_code": response.status_code}},
            )
            return None

        data = self._safe_json(response)
        return self._extract_text(data)

    def _safe_json(self, response: Any) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list) or not candidates:
            return None

        first_candidate = candidates[0] if isinstance(candidates[0], dict) else None
        content = first_candidate.get("content") if isinstance(first_candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            return None

        first_part = parts[0] if isinstance(parts[0], dict) else None
        text = first_part.get("text") if isinstance(first_part, dict) else None
        if isinstance(text, str) and text.strip():
            return text
        return None

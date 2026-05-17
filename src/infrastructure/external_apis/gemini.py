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

    async def generate_batch_caption(
        self,
        offers_data: list[dict[str, str]],
    ) -> str | None:
        if not offers_data:
            return None

        fire = "\U0001F525"
        money = "\U0001F4B8"
        link = "\U0001F517"
        package = "\U0001F4E6"
        bell = "\U0001F514"
        keycap_one = "1\ufe0f\u20e3"

        offers_lines: list[str] = []
        for idx, offer in enumerate(offers_data, start=1):
            name = offer.get("name", "").strip()
            price = offer.get("price", "").strip()
            url = offer.get("url", "").strip()
            if not name or not price or not url:
                continue
            offers_lines.append(
                f"{idx}. Nome: {name} | Preco: {price} | Link: {url}"
            )

        if not offers_lines:
            return None

        offers_block = "\n".join(offers_lines)
        prompt = (
            "Voce e a estrategista da Central das Ofertas. "
            "Compile a lista de produtos recebida em um unico texto. "
            "Siga estritamente o template abaixo. "
            "Retorne apenas o texto final preenchido, sem aspas, "
            "markdowns de codigo ou comentarios extras.\n\n"
            "TEMPLATE:\n"
            f"{fire} TOP OFERTAS DO DIA {fire}\n"
            "Descontos reais selecionados para voc\u00ea. "
            "Aproveite antes que vire o pre\u00e7o!\n\n"
            f"{keycap_one} [Nome Curto do Produto 1]\n"
            f"{money} Por: [Pre\u00e7o 1]\n"
            f"{link} [Link 1]\n"
            "(Repetir para os restantes)\n\n"
            f"{package} Frete e descontos ativos nos links!\n"
            f"{bell} Central das Ofertas\n\n"
            "DADOS DOS PRODUTOS:\n"
            f"{offers_block}\n"
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
            logger.warning("gemini_generate_batch_caption_failed", exc_info=True)
            return None

        if not response.is_success:
            logger.warning(
                "gemini_generate_batch_caption_rejected",
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

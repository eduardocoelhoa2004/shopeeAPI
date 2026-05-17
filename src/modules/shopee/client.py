from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Mapping

import httpx

from src.core.config.settings import ShopeeSettings, settings
from src.infrastructure.external_apis.http_client import AsyncHttpClient

logger = logging.getLogger("app.shopee")


class ShopeeAffiliateClient:
    def __init__(
        self,
        http_client: AsyncHttpClient | None = None,
        shopee_settings: ShopeeSettings | None = None,
    ) -> None:
        self._settings = shopee_settings or settings.shopee
        self._client = http_client or AsyncHttpClient(base_url=self._settings.base_url)

    async def generate_short_link(
        self,
        original_url: str,
    ) -> dict[str, Any]:
        cleaned_url = original_url.strip()
        if not cleaned_url:
            raise ValueError("original_url must not be empty")

        path = self._normalize_path("/graphql")
        url_literal = json.dumps(cleaned_url)
        query = (
            "mutation { generateShortLink(input: {originUrl: "
            f"{url_literal}"
            "}) { shortLink } }"
        )
        payload: dict[str, Any] = {"query": query}
        payload_string = json.dumps(payload, separators=(",", ":"))
        timestamp = self._timestamp()
        signature = self._sign(timestamp, payload_string)
        headers = self._build_auth_headers(timestamp, signature)

        response = await self._client.post(path, headers=headers, data=payload_string)

        payload_json = self._safe_json(response)
        errors = payload_json.get("errors") if isinstance(payload_json, dict) else None
        if response.is_success and not errors:
            data = payload_json.get("data") if isinstance(payload_json.get("data"), dict) else {}
            node = data.get("generateShortLink") if isinstance(data.get("generateShortLink"), dict) else {}
            short_link = node.get("shortLink") if isinstance(node, dict) else None
            logger.info(
                "shopee_short_link_success",
                extra={"data": {"status_code": response.status_code, "path": path}},
            )
            return {
                "success": True,
                "data": {"short_link": short_link} if short_link else {},
                "error": None,
            }

        logger.warning(
            "shopee_short_link_failed",
            extra={"data": {"status_code": response.status_code, "path": path}},
        )
        error_message = (
            payload_json.get("error")
            or payload_json.get("message")
            or "shopee_request_failed"
        )
        return {
            "success": False,
            "data": {},
            "error": error_message,
        }

    async def get_offer_list(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if offset < 0:
            raise ValueError("offset must be zero or positive")

        page = (offset // limit) + 1
        if page < 1:
            page = 1

        path = self._normalize_path("/graphql")
        query = (
            "{ productOfferV2(page: "
            f"{page}"
            ", limit: "
            f"{limit}"
            ", sortType: 5) { nodes { itemId, productName, priceMin, commissionRate, productLink, imageUrl } } }"
        )
        payload: dict[str, Any] = {"query": query}
        payload_string = json.dumps(payload, separators=(",", ":"))
        timestamp = self._timestamp()
        signature = self._sign(timestamp, payload_string)
        headers = self._build_auth_headers(timestamp, signature)

        response = await self._client.post(path, headers=headers, data=payload_string)
        payload_json = self._safe_json(response)
        errors = payload_json.get("errors") if isinstance(payload_json, dict) else None

        if errors:
            logger.warning(
                "shopee_offer_list_failed",
                extra={"data": {"status_code": response.status_code, "path": path}},
            )
            return {
                "success": False,
                "data": {},
                "error": "shopee_graphql_error",
            }

        if response.is_success and not errors:
            data = payload_json.get("data") if isinstance(payload_json.get("data"), dict) else {}
            node = data.get("productOfferV2") if isinstance(data.get("productOfferV2"), dict) else {}
            nodes = node.get("nodes") if isinstance(node.get("nodes"), list) else []
            logger.info(
                "shopee_offer_list_success",
                extra={"data": {"status_code": response.status_code, "path": path}},
            )
            return {
                "success": True,
                "data": {"productOfferV2": {"nodes": nodes}},
                "error": None,
            }

        logger.warning(
            "shopee_offer_list_failed",
            extra={"data": {"status_code": response.status_code, "path": path}},
        )
        error_message = payload_json.get("error") or payload_json.get("message") or "shopee_request_failed"
        return {
            "success": False,
            "data": {},
            "error": error_message,
        }

    def _auth_params(self, path: str, payload: Mapping[str, Any] | None) -> dict[str, str]:
        timestamp = self._timestamp()
        payload_string = self._payload_string(payload)
        signature = self._sign(timestamp, payload_string)
        return {
            "app_id": self._settings.app_id,
            "timestamp": str(timestamp),
            "sign": signature,
        }

    def _timestamp(self) -> int:
        return int(time.time())

    def _sign(self, timestamp: int, payload_string: str) -> str:
        app_id = self._settings.app_id
        app_secret = self._settings.app_secret.get_secret_value()
        message = f"{app_id}{timestamp}{payload_string}{app_secret}"
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def _payload_string(self, payload: Mapping[str, Any] | None) -> str:
        if not payload:
            return ""
        return json.dumps(payload, separators=(",", ":"))

    def _build_auth_headers(self, timestamp: int, signature: str) -> dict[str, str]:
        authorization = (
            "SHA256 "
            f"Credential={self._settings.app_id},"
            f"Timestamp={timestamp},"
            f"Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": "application/json",
        }

    def _safe_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    def _normalize_path(self, path: str) -> str:
        if path.startswith("/"):
            return path
        return f"/{path}"

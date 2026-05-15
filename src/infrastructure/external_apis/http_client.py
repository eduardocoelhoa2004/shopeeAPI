from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

import httpx
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger("app.http")


class CircuitBreakerOpenError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0


class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self._config = config or CircuitBreakerConfig()
        self._state: Literal["closed", "open"] = "closed"
        self._failure_count = 0
        self._opened_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def allow_request(self) -> bool:
        async with self._lock:
            if self._state == "open":
                if self._opened_at is None:
                    return False
                elapsed = (datetime.now(timezone.utc) - self._opened_at).total_seconds()
                if elapsed < self._config.recovery_timeout:
                    return False
                self._state = "closed"
                self._failure_count = 0
                self._opened_at = None
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self._config.failure_threshold:
                self._state = "open"
                self._opened_at = datetime.now(timezone.utc)


class AsyncHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: httpx.Timeout | None = None,
        max_retries: int = 3,
        backoff_min: float = 0.5,
        backoff_max: float = 4.0,
        circuit_breaker: CircuitBreaker | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout or httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        self._max_retries = max_retries
        self._backoff_min = backoff_min
        self._backoff_max = backoff_max
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> httpx.Response:
        if not await self._circuit_breaker.allow_request():
            logger.error(
                "http_circuit_open",
                extra={"data": {"method": method, "path": self._safe_path(url)}},
            )
            raise CircuitBreakerOpenError("Circuit breaker open")

        retrying = AsyncRetrying(
            retry=retry_if_exception_type(httpx.RequestError),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(
                multiplier=self._backoff_min,
                min=self._backoff_min,
                max=self._backoff_max,
            ),
            reraise=True,
            before_sleep=self._log_retry,
        )

        try:
            response = await retrying(
                self._client.request,
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=json,
                data=data,
            )
        except httpx.RequestError as exc:
            await self._circuit_breaker.record_failure()
            self._log_request_error(method, url, exc)
            raise

        await self._circuit_breaker.record_success()
        self._log_response(method, response)
        return response

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
        )

    async def post(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> httpx.Response:
        return await self.request(
            "POST",
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncHttpClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    def _log_retry(self, retry_state: RetryCallState) -> None:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if exc is None:
            return
        method = retry_state.kwargs.get("method", "UNKNOWN")
        url = retry_state.kwargs.get("url")
        logger.warning(
            "http_retry",
            extra={
                "data": {
                    "method": method,
                    "path": self._safe_path(url),
                    "attempt": retry_state.attempt_number,
                    "error_type": exc.__class__.__name__,
                }
            },
        )

    def _log_request_error(self, method: str, url: str, exc: httpx.RequestError) -> None:
        request_url = exc.request.url if exc.request else url
        logger.error(
            "http_request_failed",
            extra={
                "data": {
                    "method": method,
                    "path": self._safe_path(request_url),
                    "error_type": exc.__class__.__name__,
                }
            },
        )

    def _log_response(self, method: str, response: httpx.Response) -> None:
        path = self._safe_path(response.request.url)
        if response.is_success:
            logger.info(
                "http_request_success",
                extra={"data": {"method": method, "path": path, "status_code": response.status_code}},
            )
        else:
            logger.warning(
                "http_request_error",
                extra={"data": {"method": method, "path": path, "status_code": response.status_code}},
            )

    def _safe_path(self, url: str | httpx.URL | None) -> str:
        if url is None:
            return "/"
        try:
            if isinstance(url, httpx.URL):
                path = url.path or "/"
            else:
                path = httpx.URL(url).path or "/"
            return re.sub(r"/bot[^/]+/", "/bot<redacted>/", path)
        except httpx.InvalidURL:
            return "/"

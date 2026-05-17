from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infrastructure.external_apis.http_client import (
    AsyncHttpClient,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)


class FakeAsyncClient:
    def __init__(self, responses: list[httpx.Response | Exception] | None = None) -> None:
        self._responses = list(responses or [])
        self._call_count = 0
        self.calls: list[dict[str, Any]] = []

    async def request(self, **kwargs: Any) -> httpx.Response:
        self.calls.append(kwargs)
        if self._call_count >= len(self._responses):
            raise RuntimeError("no more fake responses")
        resp = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp

    async def aclose(self) -> None:
        pass


def _ok_response(status_code: int = 200, json_data: Any = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data or {"ok": True},
        request=httpx.Request("GET", "https://api.example.com/test"),
    )


def _error_response(status_code: int = 500) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json={"error": "internal"},
        request=httpx.Request("GET", "https://api.example.com/test"),
    )


def test_get_returns_successful_response() -> None:
    fake_client = FakeAsyncClient([_ok_response()])
    client = AsyncHttpClient(base_url="https://api.example.com", client=fake_client)

    response = asyncio.run(client.get("/test"))

    assert response.status_code == 200
    assert len(fake_client.calls) == 1


def test_post_returns_successful_response() -> None:
    fake_client = FakeAsyncClient([_ok_response(201, {"created": True})])
    client = AsyncHttpClient(base_url="https://api.example.com", client=fake_client)

    response = asyncio.run(client.post("/create", json={"name": "test"}))

    assert response.status_code == 201
    assert fake_client.calls[0]["json"] == {"name": "test"}


def test_retries_on_request_error_and_succeeds() -> None:
    req = httpx.Request("GET", "https://api.example.com/test")
    error = httpx.ConnectError("connection refused", request=req)
    fake_client = FakeAsyncClient([error, error, _ok_response()])
    client = AsyncHttpClient(
        base_url="https://api.example.com",
        client=fake_client,
        max_retries=3,
        backoff_min=0.01,
        backoff_max=0.02,
    )

    response = asyncio.run(client.get("/test"))

    assert response.status_code == 200
    assert len(fake_client.calls) == 3


def test_raises_after_max_retries_exceeded() -> None:
    req = httpx.Request("GET", "https://api.example.com/test")
    error = httpx.ConnectError("connection refused", request=req)
    fake_client = FakeAsyncClient([error, error, error, error])
    client = AsyncHttpClient(
        base_url="https://api.example.com",
        client=fake_client,
        max_retries=3,
        backoff_min=0.01,
        backoff_max=0.02,
    )

    with pytest.raises(httpx.ConnectError):
        asyncio.run(client.get("/test"))


def test_does_not_retry_on_http_error_status() -> None:
    fake_client = FakeAsyncClient([_error_response(500)])
    client = AsyncHttpClient(
        base_url="https://api.example.com",
        client=fake_client,
        max_retries=3,
    )

    response = asyncio.run(client.get("/test"))

    assert response.status_code == 500
    assert len(fake_client.calls) == 1


def test_context_manager_closes_client() -> None:
    fake_client = FakeAsyncClient()
    client = AsyncHttpClient(base_url="https://api.example.com", client=fake_client)

    async def _run() -> None:
        async with client:
            pass

    asyncio.run(_run())


# --- Circuit Breaker Tests ---


def test_circuit_breaker_starts_closed() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0))

    assert asyncio.run(cb.allow_request()) is True


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0))

    for _ in range(3):
        asyncio.run(cb.record_failure())

    assert asyncio.run(cb.allow_request()) is False


def test_circuit_breaker_closes_on_success() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0))

    for _ in range(2):
        asyncio.run(cb.record_failure())
    asyncio.run(cb.record_success())

    assert asyncio.run(cb.allow_request()) is True


def test_circuit_breaker_rejects_requests_when_open() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0))

    asyncio.run(cb.record_failure())
    asyncio.run(cb.record_failure())

    with pytest.raises(CircuitBreakerOpenError):
        asyncio.run(AsyncHttpClient(base_url="https://api.example.com", circuit_breaker=cb).get("/test"))


def test_circuit_breaker_recovers_after_timeout() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.01))

    asyncio.run(cb.record_failure())
    asyncio.run(cb.record_failure())

    assert asyncio.run(cb.allow_request()) is False

    import time
    time.sleep(0.02)

    assert asyncio.run(cb.allow_request()) is True


def test_http_client_records_success_on_circuit_breaker() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0))
    fake_client = FakeAsyncClient([_ok_response()])
    client = AsyncHttpClient(
        base_url="https://api.example.com",
        client=fake_client,
        circuit_breaker=cb,
    )

    asyncio.run(client.get("/test"))

    assert asyncio.run(cb.allow_request()) is True


def test_http_client_records_failure_on_circuit_breaker() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, recovery_timeout=30.0))
    req = httpx.Request("GET", "https://api.example.com/test")
    error = httpx.ConnectError("connection refused", request=req)
    fake_client = FakeAsyncClient([error, error])
    client = AsyncHttpClient(
        base_url="https://api.example.com",
        client=fake_client,
        circuit_breaker=cb,
        max_retries=2,
        backoff_min=0.01,
        backoff_max=0.02,
    )

    with pytest.raises(httpx.ConnectError):
        asyncio.run(client.get("/test"))

    assert asyncio.run(cb.allow_request()) is False

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from src.core.config.settings import settings

SENSITIVE_KEYS: set[str] = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
}

REDACTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|authorization)\s*=\s*[^,\s]+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
]


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(marker in key_lower for marker in SENSITIVE_KEYS)


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            redacted[key] = "***"
        else:
            redacted[key] = _redact_value(value)
    return redacted


def _redact_text(text: str) -> str:
    redacted = text
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub("***", redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_text(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        data: Any | None = None
        if hasattr(record, "data"):
            data = getattr(record, "data")
        elif isinstance(record.args, Mapping):
            data = record.args

        if data is not None:
            payload["data"] = _redact_value(data)

        if hasattr(record, "correlation_id"):
            payload["correlation_id"] = getattr(record, "correlation_id")

        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            if settings.app.debug:
                payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def _resolve_log_level(level: str) -> int:
    numeric = logging.getLevelName(level.upper())
    return numeric if isinstance(numeric, int) else logging.INFO


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(_resolve_log_level(settings.app.log_level))

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.setLevel(root_logger.level)
        logger.propagate = False

    logging.captureWarnings(True)
    return root_logger

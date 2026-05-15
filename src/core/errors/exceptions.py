from __future__ import annotations


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str | None = None,
    ) -> None:
        if not message:
            message = "Application error"
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

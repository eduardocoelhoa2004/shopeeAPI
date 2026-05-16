from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal, TypeVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

NonEmptyStr = Annotated[str, Field(min_length=1)]
NonEmptySecret = Annotated[SecretStr, Field(min_length=1)]
Port = Annotated[int, Field(gt=0, lt=65536)]
SettingsT = TypeVar("SettingsT", bound=BaseSettings)


def _load_settings(settings_type: type[SettingsT]) -> SettingsT:
    return settings_type()


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: NonEmptyStr = "offer-automation"
    environment: Literal["development", "staging", "production"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    debug: bool = False
    api_version: NonEmptyStr = "v1"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: NonEmptyStr
    port: Port
    name: NonEmptyStr
    user: NonEmptyStr
    password: NonEmptySecret
    ssl_mode: Literal["disable", "require", "verify-full"] = "require"
    pool_size: Annotated[int, Field(ge=1)] = 10
    max_overflow: Annotated[int, Field(ge=0)] = 20
    connect_timeout: Annotated[int, Field(ge=1)] = 10

    @property
    def sqlalchemy_url(self) -> str:
        password = self.password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.user}:{password}@"
            f"{self.host}:{self.port}/{self.name}"
        )


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: NonEmptySecret
    api_token: NonEmptySecret


class ShopeeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHOPEE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_id: NonEmptyStr
    app_secret: NonEmptySecret
    base_url: NonEmptyStr


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: NonEmptySecret
    chat_id: NonEmptyStr
    base_url: NonEmptyStr = "https://api.telegram.org"


class FacebookSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FACEBOOK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    page_id: NonEmptyStr
    access_token: NonEmptySecret


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=lambda: _load_settings(AppSettings))
    database: DatabaseSettings = Field(
        default_factory=lambda: _load_settings(DatabaseSettings)
    )
    security: SecuritySettings = Field(
        default_factory=lambda: _load_settings(SecuritySettings)
    )
    shopee: ShopeeSettings = Field(
        default_factory=lambda: _load_settings(ShopeeSettings)
    )
    telegram: TelegramSettings = Field(
        default_factory=lambda: _load_settings(TelegramSettings)
    )
    facebook: FacebookSettings = Field(default_factory=FacebookSettings)


@lru_cache
def get_settings() -> AppConfig:
    return AppConfig()


settings = get_settings()

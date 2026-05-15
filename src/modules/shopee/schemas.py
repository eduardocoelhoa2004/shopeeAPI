from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ShortLinkRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    original_url: HttpUrl
    source: str | None = None


class ShortLinkResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    short_link: HttpUrl


class OfferListRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class OfferListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    offers: list[dict[str, Any]]
    total: int | None = None
    limit: int
    offset: int

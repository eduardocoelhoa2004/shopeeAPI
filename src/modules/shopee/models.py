from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class ShopeeOffer(Base):
    __tablename__ = "shopee_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    short_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Telegram
    is_published_facebook: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Facebook
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
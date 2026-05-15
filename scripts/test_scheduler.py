from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from src.infrastructure.database.session import AsyncSessionLocal
from src.modules.shopee.models import ShopeeOffer


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(ShopeeOffer))
        total = result.scalar_one()
        print(f"shopee_offers_total={total}")


if __name__ == "__main__":
    asyncio.run(main())

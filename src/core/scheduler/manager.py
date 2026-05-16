from __future__ import annotations

import logging
from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.config.settings import settings
from src.infrastructure.database.session import AsyncSessionLocal
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.modules.facebook.client import FACEBOOK_GRAPH_API_BASE_URL, FacebookClient
from src.modules.facebook.service import FacebookPublisherService
from src.modules.shopee.client import ShopeeAffiliateClient
from src.modules.shopee.service import ShopeeOfferService
from src.modules.telegram.client import TelegramClient
from src.modules.telegram.service import TelegramPublisherService

logger = logging.getLogger("app.scheduler")


async def _run_shopee_job(limit: int) -> None:
    logger.info("shopee_offer_job_started", extra={"data": {"limit": limit}})
    try:
        async with AsyncSessionLocal() as session:
            async with AsyncHttpClient(
                base_url=settings.shopee.base_url
            ) as http_client:
                client = ShopeeAffiliateClient(http_client=http_client)
                service = ShopeeOfferService(session=session, client=client)
                summary = await service.fetch_and_process_offers(limit=limit)
        logger.info("shopee_offer_job_finished", extra={"data": summary})
    except Exception:
        logger.exception("shopee_offer_job_failed")


async def _run_telegram_job() -> None:
    logger.info("telegram_publish_job_started")
    try:
        async with AsyncSessionLocal() as session:
            async with AsyncHttpClient(
                base_url=settings.telegram.base_url
            ) as http_client:
                client = TelegramClient(http_client=http_client)
                service = TelegramPublisherService(
                    session=session, telegram_client=client
                )
                published = await service.publish_next_offer()
        logger.info(
            "telegram_publish_job_finished", extra={"data": {"published": published}}
        )
    except Exception:
        logger.exception("telegram_publish_job_failed")


async def _run_facebook_job() -> None:
    logger.info("facebook_publish_job_started")
    try:
        async with AsyncSessionLocal() as session:
            async with AsyncHttpClient(
                base_url=FACEBOOK_GRAPH_API_BASE_URL
            ) as http_client:
                client = FacebookClient(http_client=http_client)
                service = FacebookPublisherService(
                    session=session,
                    facebook_client=client,
                )
                published = await service.publish_next_offer()
        logger.info(
            "facebook_publish_job_finished",
            extra={"data": {"published": published}},
        )
    except Exception:
        logger.exception("facebook_publish_job_failed")


def start_scheduler(
    interval_minutes: int = 30,
    limit: int = 20,
    telegram_interval_minutes: int = 5,
    facebook_interval_minutes: int = 45,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        _run_shopee_job,
        "interval",
        minutes=interval_minutes,
        kwargs={"limit": limit},
        id="shopee_offer_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_telegram_job,
        "interval",
        minutes=telegram_interval_minutes,
        id="telegram_publish_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    #scheduler.add_job(
    #   _run_facebook_job,
    #    "interval",
    #    minutes=facebook_interval_minutes,
    #    id="facebook_publish_job",
    #    replace_existing=True,
    #    max_instances=1,
    #    coalesce=True,
    #)
    scheduler.start()
    logger.info(
        "scheduler_started",
        extra={
            "data": {
                "interval_minutes": interval_minutes,
                "limit": limit,
                "telegram_interval_minutes": telegram_interval_minutes,
                "facebook_interval_minutes": facebook_interval_minutes,
            }
        },
    )
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is None:
        return
    scheduler.shutdown(wait=False)
    logger.info("scheduler_stopped")

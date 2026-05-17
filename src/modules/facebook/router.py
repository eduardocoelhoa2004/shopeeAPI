from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db_session
from src.infrastructure.external_apis.gemini import GEMINI_API_BASE_URL, GeminiClient
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.modules.facebook.client import FACEBOOK_GRAPH_API_BASE_URL, FacebookClient
from src.modules.facebook.service import FacebookPublisherService

logger = logging.getLogger("app.facebook.router")

router = APIRouter(prefix="/api/facebook", tags=["Facebook"])


async def get_facebook_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[FacebookPublisherService, None]:
    async with AsyncHttpClient(
        base_url=FACEBOOK_GRAPH_API_BASE_URL
    ) as facebook_http_client:
        async with AsyncHttpClient(
            base_url=GEMINI_API_BASE_URL
        ) as gemini_http_client:
            client = FacebookClient(http_client=facebook_http_client)
            gemini_client = GeminiClient(http_client=gemini_http_client)
            yield FacebookPublisherService(
                session=session,
                facebook_client=client,
                gemini_client=gemini_client,
            )


@router.post("/force-publish-batch")
async def force_publish_batch(
    batch_size: int = 4,
    service: FacebookPublisherService = Depends(get_facebook_service),
) -> dict[str, str]:
    try:
        result = await service.publish_text_batch(batch_size=batch_size)
        if result:
            return {
                "status": "success",
                "message": "Lote publicado com sucesso no Facebook",
            }
        return {
            "status": "warning",
            "message": "Nenhum produto publicado. Verifique os logs ou se há ofertas suficientes no banco.",
        }
    except Exception:
        logger.exception("facebook_force_publish_error")
        raise HTTPException(status_code=500, detail="Erro interno ao tentar publicar no Facebook.")

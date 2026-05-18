from __future__ import annotations

import logging
from enum import Enum
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db_session
from src.infrastructure.external_apis.gemini import GEMINI_API_BASE_URL, GeminiClient
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.infrastructure.image.generator import ImageGeneratorService
from src.modules.facebook.client import FACEBOOK_GRAPH_API_BASE_URL, FacebookClient
from src.modules.facebook.service import FacebookPublisherService

logger = logging.getLogger("app.facebook.router")

router = APIRouter(prefix="/api/facebook", tags=["Facebook"])


class TemplateTypeEnum(str, Enum):
    top_deals = "top_deals"
    relampago = "relampago"
    achadinho = "achadinho"


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
            image_generator = ImageGeneratorService()
            yield FacebookPublisherService(
                session=session,
                facebook_client=client,
                gemini_client=gemini_client,
                image_generator=image_generator,
            )


@router.post("/force-publish-batch")
async def force_publish_batch(
    batch_size: int = 4,
    service: FacebookPublisherService = Depends(get_facebook_service),
) -> dict[str, str]:
    try:
        result = await service.publish_offer_batch(batch_size=batch_size)
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


@router.get("/preview-template")
async def preview_template(
    template_type: TemplateTypeEnum = Query(
        TemplateTypeEnum.top_deals,
        description="Selecione o template no menu dropdown",
    ),
    service: FacebookPublisherService = Depends(get_facebook_service),
) -> FileResponse:
    try:
        image_path = await service.preview_offer_batch_image(template_type=template_type.value)
        if not image_path:
            raise HTTPException(status_code=404, detail="Ofertas insuficientes para gerar preview.")
        return FileResponse(image_path, media_type="image/jpeg")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Erro no preview do template %s", template_type.value)
        raise HTTPException(status_code=500, detail="Erro interno ao gerar o preview.")

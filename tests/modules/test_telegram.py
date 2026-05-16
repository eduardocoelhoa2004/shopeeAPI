import asyncio
from src.core.config.settings import settings
from src.infrastructure.database.session import AsyncSessionLocal
from src.infrastructure.external_apis.http_client import AsyncHttpClient
from src.modules.telegram.client import TelegramClient
from src.modules.telegram.service import TelegramPublisherService

async def main():
    print("A preparar envio para o Telegram...")
    async with AsyncSessionLocal() as session:
        async with AsyncHttpClient(base_url=settings.telegram.base_url) as http_client:
            client = TelegramClient(http_client=http_client)
            service = TelegramPublisherService(session=session, telegram_client=client)
            
            sucesso = await service.publish_next_offer()
            
            if sucesso:
                print("✅ SUCESSO! A oferta foi enviada para o seu Telegram!")
            else:
                print("❌ Falha no envio ou não há ofertas novas para publicar.")

if __name__ == "__main__":
    asyncio.run(main())
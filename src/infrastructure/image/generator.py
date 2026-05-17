import os
import logging
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)

class ImageGeneratorService:
    """
    Serviço responsável pela geração de imagens para ofertas (Oferta Relâmpago, Top Descontos, etc.)
    utilizando renderização de templates HTML/CSS com Playwright e Jinja2.
    """

    def __init__(self, templates_dir: str = "src/assets/templates/html"):
        # Garante que o diretório base existe caso não tenha sido criado
        os.makedirs(templates_dir, exist_ok=True)
        
        # Configura o ambiente Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

    async def generate_top_deals_image(self, offers_data: list[dict[str, Any]], output_path: str) -> str:
        """
        Gera uma imagem de "Top Descontos" utilizando um template HTML e capturando a tela com Playwright.
        """
        try:
            # Tenta carregar o template, assumindo que ele existirá (ex: top_deals.html)
            template = self.jinja_env.get_template("top_deals.html")
            
            # Renderiza o HTML passando as ofertas como contexto
            html_content = template.render(offers=offers_data)
        except Exception as e:
            logger.error(f"Falha ao renderizar o template Jinja2: {e}")
            raise

        try:
            async with async_playwright() as p:
                # Lança o browser em modo headless
                browser = await p.chromium.launch(headless=True)
                
                # Cria uma nova página com a viewport para formato feed/post (1080x1350)
                context = await browser.new_context(viewport={"width": 1080, "height": 1350})
                page = await context.new_page()
                
                # Define o conteúdo da página com o HTML renderizado
                # wait_until="networkidle" aguarda o carregamento completo das imagens da rede
                await page.set_content(html_content, wait_until="networkidle")
                
                # Tira o screenshot
                await page.screenshot(path=output_path)
                
                await browser.close()
                
                logger.info(f"Imagem Top Descontos salva em: {output_path}")
                return output_path
                
        except PlaywrightError as pe:
            logger.error(f"Erro do Playwright ao gerar a imagem: {pe}. Verifique se instalou o Chromium usando 'playwright install chromium'.")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao gerar a imagem com Playwright: {e}")
            raise

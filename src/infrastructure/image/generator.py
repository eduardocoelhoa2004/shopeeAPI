import base64
import logging
import os
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)

TEMPLATE_REGISTRY: dict[str, dict[str, str]] = {
    "top_deals": {
        "html": "top_deals.html",
        "mask": os.path.join("src", "assets", "templates", "images", "TD_template_vazado.png"),
    },
    "relampago": {
        "html": "oferta_relampago.html",
        "mask": os.path.join("src", "assets", "templates", "images", "oferta_relampago.png"),
    },
    "achadinho": {
        "html": "achadinho_do_dia.html",
        "mask": os.path.join("src", "assets", "templates", "images", "achadinho_do_dia.png"),
    },
}

_PLACEHOLDER_IMAGE = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">'
        b'<rect width="400" height="400" fill="#EEEEEE"/>'
        b'<text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="#999" font-size="32">Sem Foto</text>'
        b"</svg>"
    ).decode()
)


class ImageGeneratorService:
    """
    Servico responsavel pela geracao de imagens para ofertas (Oferta Relampago, Top Descontos, etc.)
    utilizando renderizacao de templates HTML/CSS com Playwright e Jinja2.
    """

    def __init__(self, templates_dir: str = "src/assets/templates/html"):
        os.makedirs(templates_dir, exist_ok=True)
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def generate_image(
        self,
        offers_data: list[dict[str, Any]],
        output_path: str,
        template_type: str = "top_deals",
    ) -> str:
        """
        Gera uma imagem utilizando o template especificado e capturando a tela com Playwright.
        """
        template_config = TEMPLATE_REGISTRY.get(template_type)
        if not template_config:
            raise ValueError(f"template_type desconhecido: {template_type}. Valores: {list(TEMPLATE_REGISTRY)}")

        try:
            template = self.jinja_env.get_template(template_config["html"])

            await self._download_images_as_base64(offers_data)
            self._apply_image_fallback(offers_data)

            mask_data_uri = self._load_mask_as_base64(template_config["mask"])

            html_content = template.render(offers=offers_data, mask_data_uri=mask_data_uri)
        except Exception:
            logger.exception("jinja2_render_failed")
            raise

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1080, "height": 1350},
                    device_scale_factor=2,
                )
                page = await context.new_page()
                await page.set_content(html_content, wait_until="networkidle")
                await page.screenshot(path=output_path, type="jpeg", quality=100)
                await browser.close()

                logger.info("image_generated", extra={"data": {"path": output_path, "template": template_type}})
                return output_path

        except PlaywrightError:
            logger.exception("playwright_image_generation_failed")
            raise
        except Exception:
            logger.exception("playwright_image_generation_unexpected_error")
            raise

    async def _download_images_as_base64(self, offers_data: list[dict[str, Any]]) -> None:
        """Baixa as imagens via HTTP e converte para Data URI Base64."""
        async with httpx.AsyncClient() as client:
            for offer in offers_data:
                url = offer.get("image_url")
                if url and not url.startswith("data:"):
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                            "Referer": "https://shopee.com.br/",
                        }
                        resp = await client.get(url, headers=headers, follow_redirects=True, timeout=15.0)
                        resp.raise_for_status()

                        img_b64 = base64.b64encode(resp.content).decode("utf-8")
                        content_type = resp.headers.get("content-type", "image/jpeg")
                        offer["image_url"] = f"data:{content_type};base64,{img_b64}"
                    except Exception as e:
                        logger.error(f"Erro ao transferir imagem da Shopee {url}: {e}")
                        offer["image_url"] = None

    def _apply_image_fallback(self, offers_data: list[dict[str, Any]]) -> None:
        """Substitui imagens ausentes ou falhadas por um placeholder."""
        for offer in offers_data:
            if not offer.get("image_url"):
                offer["image_url"] = _PLACEHOLDER_IMAGE

    def _load_mask_as_base64(self, mask_relative_path: str) -> str:
        """Carrega a mascara local e converte para Data URI Base64."""
        template_path = os.path.join(os.getcwd(), mask_relative_path)
        with open(template_path, "rb") as image_file:
            template_b64 = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{template_b64}"

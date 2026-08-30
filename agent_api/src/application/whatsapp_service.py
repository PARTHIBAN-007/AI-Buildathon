from __future__ import annotations

from loguru import logger

from src.infrastructure.messaging.whatsapp_client import WhatsAppClient


class WhatsAppService:
    """Application service for WhatsApp outbound messaging."""

    def __init__(self, client: WhatsAppClient | None = None) -> None:
        self.client = client or WhatsAppClient()

    async def send_text_message(self, to: str, body: str) -> dict:
        logger.info("Sending WhatsApp text message to {}", to)
        return await self.client.send_text_message(to=to, body=body)

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language: str = "en_US",
        components: list[dict] | None = None,
    ) -> dict:
        logger.info("Sending WhatsApp template {} to {}", template_name, to)
        return await self.client.send_template_message(
            to=to,
            template_name=template_name,
            language=language,
            components=components,
        )

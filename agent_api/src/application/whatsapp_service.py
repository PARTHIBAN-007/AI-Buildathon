from __future__ import annotations

from typing import Any, Dict
from loguru import logger
from src.infrastructure.clients.whatsapp_client import WhatsAppClient


class WhatsAppService:
    def __init__(self, client: WhatsAppClient | None = None) -> None:
        self.client = client or WhatsAppClient()

    async def send_text_message(self, to: str, body: str) -> Dict[str, Any]:
        logger.info("WhatsAppService.send_text_message to=%s", to)
        return await self.client.send_text_message(to=to, body=body)

    async def send_template_message(self, to: str, template_name: str, language: str = "en_US", components: list | None = None) -> Dict[str, Any]:
        logger.info("WhatsAppService.send_template_message template=%s to=%s", template_name, to)
        return await self.client.send_template_message(to=to, template_name=template_name, language=language, components=components)

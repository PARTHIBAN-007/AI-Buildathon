from __future__ import annotations

from typing import Any, Dict
from loguru import logger
from src.infrastructure.clients.sarvam_client import SarvamClient


class VoiceService:
    def __init__(self, client: SarvamClient | None = None) -> None:
        self.client = client or SarvamClient()

    async def trigger_call(self, phone: str, language: str | None = None, metadata: Dict | None = None) -> Dict[str, Any]:
        logger.info("VoiceService.trigger_call phone=%s", phone)
        return await self.client.trigger_call(phone=phone, language=language, metadata=metadata)

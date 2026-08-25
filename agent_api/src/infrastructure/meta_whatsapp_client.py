"""Meta WhatsApp Cloud API client"""
from typing import Any, Dict
import logging

import httpx

logger = logging.getLogger(__name__)


class MetaWhatsAppClient:
    GRAPH_BASE = "https://graph.facebook.com/v17.0"

    def __init__(self, *, access_token: str, phone_number_id: str, timeout: float = 15.0):
        if not access_token or not phone_number_id:
            raise ValueError("META_WHATSAPP_TOKEN and META_WHATSAPP_PHONE_ID must be provided")
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.GRAPH_BASE}/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

        logger.debug("Posting WhatsApp message to %s: payload keys=%s", url, list(payload.keys()))
        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
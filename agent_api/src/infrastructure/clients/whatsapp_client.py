from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class WhatsAppClient:
    """Meta WhatsApp Cloud API client (async).

    Methods:
    - send_text_message(to, body)
    - send_template_message(to, template_name, components)
    """

    def __init__(self, access_token: str | None = None, phone_number_id: str | None = None, base_url: str | None = None) -> None:
        self.access_token = access_token or settings.META_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("META_ACCESS_TOKEN and META_PHONE_NUMBER_ID must be configured")
        self.base_url = (base_url or "https://graph.facebook.com/v20.0").rstrip("/")
        self._client = httpx.AsyncClient(timeout=15.0)

    async def send_text_message(self, to: str, body: str) -> Dict[str, Any]:
        if not to or not body:
            raise ValueError("to and body are required")
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
        logger.debug("WhatsApp send_text url=%s payload=%s", url, payload)
        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def send_template_message(self, to: str, template_name: str, language: str = "en_US", components: Optional[List[Dict]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {"name": template_name, "language": {"code": language}, "components": components or []},
        }
        logger.debug("WhatsApp send_template url=%s payload=%s", url, payload)
        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

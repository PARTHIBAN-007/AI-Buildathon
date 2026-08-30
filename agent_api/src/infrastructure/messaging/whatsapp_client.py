from typing import Any

import httpx
from loguru import logger

from src.config import get_settings


class WhatsAppClient:
    """Meta WhatsApp Cloud API client used by the application service layer."""

    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        base_url: str = "https://graph.facebook.com/v20.0",
        timeout: float = 15.0,
    ) -> None:
        settings = get_settings()
        self.access_token = access_token or settings.META_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID
        if not self.access_token or not self.phone_number_id:
            raise ValueError("META_ACCESS_TOKEN and META_PHONE_NUMBER_ID must be configured")

        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def send_text_message(self, to: str, body: str) -> dict[str, Any]:
        if not to or not body:
            raise ValueError("to and body are required")

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        return await self._request("POST", f"/{self.phone_number_id}/messages", payload)

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language: str = "en_US",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not to or not template_name:
            raise ValueError("to and template_name are required")

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components or [],
            },
        }
        return await self._request("POST", f"/{self.phone_number_id}/messages", payload)

    async def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        logger.debug("Sending WhatsApp request to {} with payload={}", url, payload)

        response = await self._client.request(method, url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            logger.exception("WhatsApp request failed: {}", detail)
            raise ValueError(f"WhatsApp API error: {detail}") from exc

        return response.json()

    async def close(self) -> None:
        await self._client.aclose()

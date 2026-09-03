from __future__ import annotations

from typing import Any, Dict
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class SarvamClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.SARVAM_API_KEY
        # SARVAM_BASE_URL already contains the org/workspace path in settings
        self.base_url = (base_url or settings.SARVAM_BASE_URL) or "https://apps.sarvam.ai/api/outbounds/v1"
        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY must be configured to trigger voice calls")
        # use short timeout suitable for outbound triggers
        self._client = httpx.AsyncClient(timeout=30.0)

    async def trigger_call(
        self,
        phone: str,
        *,
        checkout_id: str | None = None,
        call_summary: str | None = None,
        opening_line: str | None = None,
        user_name: str | None = None,
        connection_id: str | None = None,
        agent_phone_number: str | None = None,
        webhook_url: str | None = None,
        lead_id: str | None = None,
    ) -> Dict[str, Any]:
        """Trigger a Sarvam outbound voice call using the Outbounds API.

        The Sarvam API expects a POST to the outbounds endpoint with a body like
        the cURL snippet provided. This method builds that payload from the
        provided parameters and the configured settings.

        Note: settings.SARVAM_BASE_URL already includes org/workspace in our config.
        """
        url = self.base_url
        headers = {"Content-Type": "application/json", "X-API-Key": self.api_key}

        app_id = getattr(settings, "META_APP_ID", "Recovery-Agent") or "Recovery-Agent"
        app_config = {
            "app_id": app_id,
            "app_version": 1,
            "app_type": "agent",
            "connection_config": {"connection_id": connection_id} if connection_id else {},
            "agent_variables": {"call_summary": call_summary or "", "user_name": user_name or ""},
            "app_overrides": {"initial_bot_message": opening_line or "", "initial_state_name": "entry"},
        }

        user_config = {"user_phone_number": phone}
        webhook_config = {"url": webhook_url or "", "metadata": {"lead_id": lead_id or checkout_id}}

        payload = {"app_config": app_config, "user_config": user_config, "webhook_config": webhook_config}

        logger.debug(f"Sarvam trigger_call url={url} payload={payload}")
        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

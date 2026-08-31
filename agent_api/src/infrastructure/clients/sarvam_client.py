from __future__ import annotations

from typing import Any, Dict, Optional
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class SarvamClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.base_url = (base_url or settings.SARVAM_BASE_URL) or "https://api.sarvam.ai"
        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY must be configured to trigger voice calls")
        self._client = httpx.AsyncClient(timeout=20.0)

    async def trigger_call(self, phone: str, language: str | None = None, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/v1/calls/outbound"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"to": phone, "language": language or "hi-IN", "metadata": metadata or {}}
        logger.debug("Sarvam trigger_call url=%s payload=%s", url, payload)
        resp = await self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

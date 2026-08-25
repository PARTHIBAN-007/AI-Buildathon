"""Sarvam Voice HTTP client."""
from typing import Any, Dict
import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class SarvamVoiceClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 15.0, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def _request_with_retries(self, method: str, path: str, json: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/') }"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        backoff = 0.5
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.request(method, url, headers=headers, json=json)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                # 4xx errors should not be retried except 429
                status = exc.response.status_code
                text = exc.response.text
                logger.warning("Sarvam HTTP error %s for %s: %s", status, url, text)
                if 500 <= status < 600 or status == 429:
                    # retryable
                    logger.info("Retrying (attempt %s) after server error", attempt)
                else:
                    raise
            except (httpx.RequestError, asyncio.TimeoutError) as exc:
                logger.warning("Sarvam request failed on attempt %s: %s", attempt, exc)

            if attempt == self._max_retries:
                break

            await asyncio.sleep(backoff)
            backoff *= 2

        # final attempt without raising specific exc
        resp = await self._client.request(method, url, headers=headers, json=json)
        resp.raise_for_status()
        return resp.json()

    async def create_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an outbound call using Sarvam Voice provider.

        payload: expected to contain fields like 'to', 'language', 'flow_id'.
        """
        return await self._request_with_retries("POST", "/v1/calls/outbound", json=payload)

    async def get_call(self, call_id: str) -> Dict[str, Any]:
        return await self._request_with_retries("GET", f"/v1/calls/{call_id}")

    async def close(self):
        await self._client.aclose()
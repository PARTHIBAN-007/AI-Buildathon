from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class SarvamClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.base_url = base_url or settings.SARVAM_BASE_URL

        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY must be configured in environment variables.")

        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        await self.close()

    async def __aenter__(self) -> SarvamClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def trigger_call(
        self,
        phone: str,
        *,
        checkout_id: str | None = None,
        customer_name: str | None = None,
        amount_in_inr: int | float | Decimal | None = None,
        item_name: str | None = None,
        webhook_url: str | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Trigger an outbound voice call through Sarvam's Outbound Agent API."""
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

        if isinstance(amount_in_inr, Decimal):
            amount_in_inr = float(amount_in_inr)
        
        logger.debug(f"{amount_in_inr=}, {amount_in_inr}, {checkout_id}, {customer_name}, {item_name}, {webhook_url}")

        safe_amount = float(amount_in_inr) if amount_in_inr is not None else 0.0
        resolved_customer = (customer_name or "Customer").strip() or "Customer"
        resolved_item = (item_name or "items in your cart").strip() or "items in your cart"
        safe_checkout_id = str(checkout_id).strip() if checkout_id else ""

        agent_variables: Dict[str, Any] = {
            "checkout_id": safe_checkout_id,
            "customer_name": "Parthiban K",
            "amount_in_inr": "6,697",
            "item_name": "Mechanical Keyboard",
        }

        payload = {
            "app_config": {
                "app_id": settings.SARVAM_APP_ID,
                "app_version": settings.SARVAM_APP_VERSION,
                "app_type": "agent",
                "connection_config": {
                    "connection_id": settings.SARVAM_CONNECTION_ID,
                    "agent_phone_number": settings.SARVAM_AGENT_PHONE_NUMBER,
                },
            },
            "user_config": {
                "user_phone_number": phone,
            },
            "agent_variables": agent_variables,
            "webhook_config": {
                "url": webhook_url or settings.SARVAM_WEBHOOK_URL,
                "metadata": {
                    "checkout_id": safe_checkout_id,
                    "phone": phone,
                },
            },
        }

        logger.info(f"Triggering Sarvam outbound call for phone={phone}, checkout_id={safe_checkout_id}, amount={safe_amount}")
        logger.debug(f"POST {self.base_url} | Payload: {payload}")

        try:
            resp = await self._client.post(self.base_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Sarvam call triggered successfully for {phone}: {data}")
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(f"Sarvam API error ({exc.response.status_code}): {exc.response.text}")
            raise RuntimeError(f"Sarvam API call failed: {exc.response.text}") from exc
        except Exception as exc:
            logger.error(f"Unexpected failure triggering Sarvam call: {exc}")
            raise
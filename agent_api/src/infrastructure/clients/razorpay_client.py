from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class RazorpayClient:
    """Async-ish Razorpay client using httpx and HTTP REST API.

    Uses HTTP Basic auth with api_key:key_secret.
    """

    def __init__(self, api_key: str | None = None, key_secret: str | None = None) -> None:
        self.api_key = api_key or settings.RAZORPAY_API_KEY
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        if not self.api_key or not self.key_secret:
            raise RuntimeError("RAZORPAY_API_KEY and RAZORPAY_KEY_SECRET must be configured")
        self.base = "https://api.razorpay.com/v1"
        self._client = httpx.AsyncClient(auth=(self.api_key, self.key_secret), timeout=15.0)

    async def create_order(self, amount_in_inr: int, receipt: str | None = None) -> Dict[str, Any]:
        if amount_in_inr <= 0:
            raise ValueError("amount_in_inr must be greater than zero")
        payload = {"amount": int(amount_in_inr) * 100, "currency": "INR", "payment_capture": 1}
        if receipt:
            payload["receipt"] = receipt
        url = f"{self.base}/orders"
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def create_payment_link(self, amount_in_inr: int, description: str | None = None, customer: Dict | None = None) -> Dict[str, Any]:
        if amount_in_inr <= 0:
            raise ValueError("amount_in_inr must be greater than zero")
        payload: Dict[str, Any] = {"amount": int(amount_in_inr) * 100, "currency": "INR", "accept_partial": False}
        if description:
            payload["description"] = description
        if customer:
            payload["customer"] = customer
        url = f"{self.base}/payment_links"
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
            raise ValueError("order_id, payment_id and signature are required")
        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        generated = hmac.new(self.key_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated, razorpay_signature)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not signature:
            return False
        generated = hmac.new(self.key_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated, signature)

    async def fetch_order(self, order_id: str) -> Dict[str, Any]:
        url = f"{self.base}/orders/{order_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

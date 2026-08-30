from __future__ import annotations

import hashlib
import hmac
from typing import Any

import razorpay
from loguru import logger

from src.config import get_settings


class RazorpayClient:
    """Razorpay provider adapter for order creation and payment verification."""

    def __init__(
        self,
        api_key: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.RAZORPAY_API_KEY
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET

        if not self.api_key or not self.key_secret:
            raise ValueError("RAZORPAY_API_KEY and RAZORPAY_KEY_SECRET must be configured")

        self.client = razorpay.Client(auth=(self.api_key, self.key_secret))

    def create_order(self, amount_in_inr: int, receipt: str | None = None) -> dict[str, Any]:
        if amount_in_inr <= 0:
            raise ValueError("amount_in_inr must be greater than zero")

        payload = {
            "amount": int(amount_in_inr) * 100,
            "currency": "INR",
            "receipt": receipt or f"rcpt_{__import__('uuid').uuid4().hex[:12]}",
            "payment_capture": 1,
        }

        order = self.client.order.create(data=payload)
        logger.info("Created Razorpay order: order_id={}", order.get("id"))
        return {
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "key_id": self.api_key,
        }

    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            raise ValueError("razorpay_order_id, razorpay_payment_id and razorpay_signature are required")

        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        secret = self.key_secret.encode("utf-8")
        generated = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated, razorpay_signature)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            logger.warning("RAZORPAY_WEBHOOK_SECRET is not configured; skipping webhook verification")
            return True

        if not signature:
            raise ValueError("signature is required")

        generated = hmac.new(self.webhook_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated, signature)

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        return self.client.order.fetch(order_id)

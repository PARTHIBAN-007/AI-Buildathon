from __future__ import annotations

from typing import Any, Dict
from loguru import logger
from src.infrastructure.clients.razorpay_client import RazorpayClient


class PaymentService:
    """Application-level payment orchestration using RazorpayClient."""

    def __init__(self, client: RazorpayClient | None = None) -> None:
        self.client = client or RazorpayClient()

    async def create_order(self, amount_in_inr: int, receipt: str | None = None) -> Dict[str, Any]:
        logger.info("PaymentService.create_order amount=%s", amount_in_inr)
        return await self.client.create_order(amount_in_inr=amount_in_inr, receipt=receipt)

    async def create_payment_link(self, amount_in_inr: int, description: str | None = None, customer: Dict | None = None) -> Dict[str, Any]:
        logger.info("PaymentService.create_payment_link amount=%s description=%s", amount_in_inr, description)
        return await self.client.create_payment_link(amount_in_inr=amount_in_inr, description=description, customer=customer)

    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        logger.info("PaymentService.verify_payment_signature order=%s payment=%s", razorpay_order_id, razorpay_payment_id)
        return self.client.verify_payment_signature(razorpay_order_id=razorpay_order_id, razorpay_payment_id=razorpay_payment_id, razorpay_signature=razorpay_signature)

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        logger.info("PaymentService.verify_webhook signature=%s", "****")
        return self.client.verify_webhook_signature(payload=payload, signature=signature)

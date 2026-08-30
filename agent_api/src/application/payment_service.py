from __future__ import annotations

from loguru import logger

from src.infrastructure.payments.razorpay_client import RazorpayClient


class PaymentService:
    """Application service for Razorpay order creation and verification."""

    def __init__(self, client: RazorpayClient | None = None) -> None:
        self.client = client or RazorpayClient()

    def create_order(self, amount_in_inr: int, receipt: str | None = None) -> dict:
        logger.info("Creating Razorpay order for amount_in_inr={}", amount_in_inr)
        return self.client.create_order(amount_in_inr=amount_in_inr, receipt=receipt)

    def verify_payment(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        logger.info(
            "Verifying Razorpay signature for order_id={} payment_id={}",
            razorpay_order_id,
            razorpay_payment_id,
        )
        return self.client.verify_payment_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        logger.info("Verifying Razorpay webhook signature")
        return self.client.verify_webhook_signature(payload=payload, signature=signature)

from __future__ import annotations

from typing import Any, Dict
from loguru import logger
from src.infrastructure.clients.razorpay_client import RazorpayClient


class PaymentService:
    """Application-level payment orchestration using RazorpayClient."""

    def __init__(self, client: RazorpayClient | None = None) -> None:
        self.client = client or RazorpayClient()

    async def create_order(
        self,
        amount_in_inr: int,
        receipt: str | None = None,
        customer: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        logger.info(
            f"PaymentService.create_order amount={amount_in_inr} receipt={receipt} customer={customer}"
        )
        return await self.client.create_order(amount_in_inr=amount_in_inr, receipt=receipt, customer=customer)

    async def create_payment_link(
        self,
        amount_in_inr: int,
        description: str | None = None,
        checkout_id: str | None = None,
        customer: Dict[str, Any] | None = None,
        notes: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Creates a Razorpay payment link with checkout_id attached in metadata notes."""
        logger.info(f"PaymentService.create_payment_link amount={amount_in_inr} checkout_id={checkout_id}")

        payment_notes = dict(notes) if notes else {}
        if checkout_id:
            payment_notes["checkout_id"] = str(checkout_id)

        return await self.client.create_payment_link(
            amount_in_inr=amount_in_inr,
            description=description,
            customer=customer,
            notes=payment_notes,
        )

    def verify_payment_signature(
        self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
    ) -> bool:
        logger.info(f"PaymentService.verify_payment_signature order={razorpay_order_id} payment={razorpay_payment_id}")
        return self.client.verify_payment_signature(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        logger.info(f"PaymentService.verify_webhook signature={signature}")
        return self.client.verify_webhook_signature(payload=payload, signature=signature)
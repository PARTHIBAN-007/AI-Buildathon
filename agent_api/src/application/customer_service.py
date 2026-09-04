from __future__ import annotations

from loguru import logger
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from src.infrastructure.postgres.repository import list_checkouts_by_phone


async def build_customer_profile(phone: str) -> dict:
    logger.info(f"Building customer profile for {phone}")
    try:
        checkouts = await list_checkouts_by_phone(phone)
        total_orders = len(checkouts)
        max_discount = max(
            (float(checkout.discount_offered) if checkout.discount_offered is not None else 0.0 for checkout in checkouts),
            default=0.0,
        )
        summary = (
            f"Repeat buyer | Total Orders: {total_orders}"
            if total_orders
            else "No prior orders found"
        )
        return {
            "summary": summary,
            "total_orders": total_orders,
            "max_discount": max_discount,
        }
    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database error in build_customer_profile for {phone}: {e}")
        # Return fallback defaults so recovery_service does not crash
        return {
            "summary": "Customer history unavailable (Database Offline)",
            "total_orders": 0,
            "max_discount": 0.0,
        }
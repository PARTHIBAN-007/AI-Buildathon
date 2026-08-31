from __future__ import annotations

from loguru import logger

# Placeholder: real implementation should query DB and aggregate behavior


async def build_customer_profile(phone: str) -> dict:
    logger.info("Building customer profile for {}", phone)
    # Example summary; in reality query checkouts/orders table
    return {"summary": "Repeat buyer | Total Orders: 2", "total_orders": 2, "max_discount": 10.0}

import logging
from typing import Any, Dict, List

from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger(__name__)


class WhatsAppWebhookHandler:
    """Handles verification and payload processing for WhatsApp Cloud API webhooks."""

    @staticmethod
    def verify_subscription(*, mode: str | None, challenge: str | None, verify_token: str | None) -> dict:
        if mode != "subscribe":
            raise HTTPException(status_code=400, detail="Invalid mode")

        expected_token = settings.VERIFY_TOKEN
        if not expected_token:
            raise HTTPException(status_code=500, detail="VERIFY_TOKEN is not configured")

        if verify_token != expected_token:
            raise HTTPException(status_code=403, detail="Verification token mismatch")

        if not challenge:
            raise HTTPException(status_code=400, detail="Missing challenge parameter")

        return {"hub.challenge": challenge}

    @staticmethod
    def process_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        entries = payload.get("entry", [])
        if not entries:
            logger.warning("WhatsApp webhook payload has no entry objects: %s", payload)
            return {"status": "ignored", "message": "No entries found"}

        messages: List[Dict[str, Any]] = []
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                contacts = value.get("contacts", [])
                messages_list = value.get("messages", [])

                for message in messages_list:
                    sender = contacts[0] if contacts else {}
                    messages.append(
                        {
                            "from": message.get("from"),
                            "type": message.get("type"),
                            "text": message.get("text", {}).get("body"),
                            "timestamp": message.get("timestamp"),
                            "wa_id": sender.get("wa_id"),
                            "display_name": sender.get("profile", {}).get("name"),
                            "phone_number_id": metadata.get("phone_number_id"),
                        }
                    )

        logger.info("Processed WhatsApp webhook payload with %s message(s)", len(messages))
        return {"status": "received", "messages": messages}

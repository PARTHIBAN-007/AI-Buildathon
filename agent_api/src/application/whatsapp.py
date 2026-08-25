from typing import Optional
import logging

from pydantic import BaseModel, Field, constr

from src.infrastructure.meta_whatsapp_client import MetaWhatsAppClient
from src.config import settings

logger = logging.getLogger(__name__)

class WhatsAppMessageRequest(BaseModel):
    phone_number: constr(min_length=7)
    template_name: Optional[str] = None
    text: Optional[str] = None
    language: Optional[str] = Field("en_US")


class WhatsAppMessageResponse(BaseModel):
    message_id: str
    status: str
    provider_response: dict


class WhatsAppService:
    def __init__(self, client: MetaWhatsAppClient | None = None):
        self._client = client or MetaWhatsAppClient(access_token=settings.META_WHATSAPP_TOKEN, phone_number_id=settings.META_WHATSAPP_PHONE_ID)

    async def send_text(self, req: WhatsAppMessageRequest) -> WhatsAppMessageResponse:
        """Send a WhatsApp message via Meta (WhatsApp Cloud API)."""
        logger.info("Sending WhatsApp message to %s", req.phone_number)

        payload = {
            "to": req.phone_number,
            "type": "text",
            "text": {"body": req.text or ""}
        }

        try:
            resp = await self._client.send_message(payload)
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message: %s", exc)
            raise

        return WhatsAppMessageResponse(message_id=resp.get("messages", [{}])[0].get("id", ""), status="sent", provider_response=resp)

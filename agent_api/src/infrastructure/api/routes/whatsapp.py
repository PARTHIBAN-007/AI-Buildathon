from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.application.whatsapp_service import WhatsAppService

router = APIRouter(prefix="", tags=["WhatsApp"])


class SendWhatsAppMessageRequest(BaseModel):
    to: str
    body: str
    template_name: str | None = None
    language: str = "en_US"
    components: list[dict] | None = None


@router.post("/whatsapp/send")
async def send_whatsapp_message(payload: SendWhatsAppMessageRequest) -> dict:
    service = WhatsAppService()
    try:
        if payload.template_name:
            response = await service.send_template_message(
                to=payload.to,
                template_name=payload.template_name,
                language=payload.language,
                components=payload.components,
            )
            return {"status": "success", "message": "Template WhatsApp message sent", "response": response}

        response = await service.send_text_message(to=payload.to, body=payload.body)
        return {"status": "success", "message": "WhatsApp message sent", "response": response}
    except ValueError as exc:
        logger.warning("Invalid WhatsApp payload: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to send WhatsApp message: {}", exc)
        raise HTTPException(status_code=502, detail="WhatsApp API error") from exc

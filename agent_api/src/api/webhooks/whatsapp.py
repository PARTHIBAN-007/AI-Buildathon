from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from src.agent.graph import resume_agent_thread

router = APIRouter()


@router.post("/webhook")
async def whatsapp_inbound(request: Request):
    payload = await request.json()
    logger.info("Received WhatsApp webhook payload: {}", payload)

    try:
        # Extract phone/thread_id and message text from Meta payload
        # Simple best-effort extraction; adapt to your incoming webhook format
        entries = payload.get("entry", [])
        for e in entries:
            changes = e.get("changes", [])
            for ch in changes:
                value = ch.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    from_phone = msg.get("from")
                    text = msg.get("text", {}).get("body")
                    if from_phone and text:
                        await resume_agent_thread(thread_id=from_phone, message=text, raw=msg)

        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Failed to process WhatsApp webhook: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to process webhook")

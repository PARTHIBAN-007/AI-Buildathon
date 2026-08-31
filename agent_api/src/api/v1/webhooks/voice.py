from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from src.agent.graph import append_voice_summary

router = APIRouter()


@router.post("/voice")
async def sarvam_voice_webhook(request: Request):
    payload = await request.json()
    logger.info("Received Sarvam voice webhook: {}", payload)

    try:
        # Expecting payload with phone and summary
        phone = payload.get("phone") or payload.get("to")
        summary = payload.get("summary") or payload.get("transcript")
        if not phone:
            raise HTTPException(status_code=400, detail="Missing phone in payload")

        await append_voice_summary(thread_id=phone, summary=summary, raw=payload)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to process voice webhook: {}", exc)
        raise HTTPException(status_code=500, detail="Voice webhook processing failed")

from loguru import logger

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from src.application.voice_agent import VoiceAgentService, VoiceCallRequest
from src.application.whatsapp import WhatsAppService, WhatsAppMessageRequest
from src.application.whatsapp_webhook import WhatsAppWebhookHandler
from src.config import get_settings

settings = get_settings()


app = FastAPI(
    title="Agent_API",
    description="API for the Agent AI Buildathon project",
    version="1.0.0",
)


@app.get("/")
def welcome():
    return {"message": "Welcome to Agent API"}


@app.get("/health")
def health():
    return {"status": "ok"}


class VoiceStartRequest(BaseModel):
    phone_number: str
    language: str | None = None
    flow_id: str | None = None


@app.post("/voice/calls")
async def start_voice_call(req: VoiceStartRequest):
    service = VoiceAgentService()
    try:
        resp = await service.start_call(VoiceCallRequest(**req.dict()))
        return JSONResponse(status_code=200, content={"success": True, "call": resp.dict()})
    except Exception as exc:
        logger.exception("Error starting voice call: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


class WhatsAppSendRequest(BaseModel):
    phone_number: str
    text: str


@app.post("/whatsapp/messages")
async def send_whatsapp_message(req: WhatsAppSendRequest):
    service = WhatsAppService()
    try:
        resp = await service.send_text(WhatsAppMessageRequest(phone_number=req.phone_number, text=req.text))
        return JSONResponse(status_code=200, content={"success": True, "message": resp.dict()})
    except ValueError as exc:
        # configuration error or input validation at runtime
        logger.exception("Configuration error when sending WhatsApp message: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Error sending WhatsApp message: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(mode: str, challenge: str | None = None, verify_token: str | None = None):
    try:
        result = WhatsAppWebhookHandler.verify_subscription(mode=mode, challenge=challenge, verify_token=verify_token)
        return JSONResponse(status_code=200, content=result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled WhatsApp webhook verification error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/whatsapp/webhook")
async def receive_whatsapp_webhook(request: Request):
    payload = await request.json()
    try:
        result = WhatsAppWebhookHandler.process_payload(payload)
        return JSONResponse(status_code=200, content={"status": "ok", "result": result})
    except Exception as exc:
        logger.exception("Error processing WhatsApp webhook payload: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
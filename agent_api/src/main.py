import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from src.application.voice_agent import VoiceAgentService, VoiceCallRequest
from src.application.whatsapp import WhatsAppService, WhatsAppMessageRequest
from src.config import settings

logging.basicConfig(level=getattr(logging, settings.__dict__.get('LOG_LEVEL', 'INFO')))
logger = logging.getLogger(__name__)

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
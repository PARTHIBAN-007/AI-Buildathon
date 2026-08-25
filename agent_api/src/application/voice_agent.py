from typing import Optional
import logging
import asyncio

from pydantic import BaseModel, Field, constr

from src.infrastructure.sarvam_voice_client import SarvamVoiceClient
from src.config import settings

logger = logging.getLogger(__name__)

class VoiceCallRequest(BaseModel):
    phone_number: constr(min_length=7) = Field(..., description="E.164 or local formatting phone number")
    language: Optional[str] = Field("en", description="Preferred language for the agent")
    flow_id: Optional[str] = Field(None, description="ID of the voice flow to run on the agent")


class VoiceCallResponse(BaseModel):
    call_id: str
    status: str
    provider_response: dict


class VoiceAgentService:
    def __init__(self, client: SarvamVoiceClient | None = None):
        self._client = client or SarvamVoiceClient(base_url=settings.SARVAM_BASE_URL, api_key=settings.SARVAM_API_KEY)

    async def start_call(self, request: VoiceCallRequest) -> VoiceCallResponse:
        """Start a call with Sarvam Voice Agent.

        This method implements robust error handling and logging appropriate for production use.
        """
        payload = {
            "to": request.phone_number,
            "language": request.language,
            "flow_id": request.flow_id,
        }

        logger.info("Starting Sarvam voice call to %s", request.phone_number)
        try:
            resp = await self._client.create_call(payload)
        except Exception as exc:
            logger.exception("Failed to start Sarvam voice call: %s", exc)
            raise

        return VoiceCallResponse(call_id=str(resp.get("call_id") or resp.get("id") or ""), status=resp.get("status", "unknown"), provider_response=resp)

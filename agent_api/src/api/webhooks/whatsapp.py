from fastapi import APIRouter, BackgroundTasks, Request, Response
from loguru import logger
from src.agent.graph import resume_agent_thread

router = APIRouter()


@router.post("/webhook")
async def whatsapp_inbound(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Inbound WhatsApp Webhook Endpoint.

    Processes messages asynchronously in the background to return HTTP 200 OK
    immediately, preventing Meta delivery retries.
    """
    payload = await request.json()

    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return Response(status_code=200)

        incoming_msg = messages[0]
        raw_phone = incoming_msg.get("from", "")
        user_text = incoming_msg.get("text", {}).get("body", "").strip()

        if raw_phone and user_text:
            formatted_phone = f"+{raw_phone.lstrip('+')}"

            logger.info(f"Inbound WhatsApp message from {formatted_phone}: '{user_text}'")

            # Dispatch execution to FastAPI background queue
            background_tasks.add_task(
                resume_agent_thread,
                phone_or_thread_id=formatted_phone,
                message=user_text,
                raw=payload,
            )

    except Exception as e:
        logger.error(f"Error parsing WhatsApp inbound webhook payload: {e}")

    return Response(status_code=200)
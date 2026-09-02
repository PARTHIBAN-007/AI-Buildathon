from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.cart import router as cart_router
from src.api.payments import router as payments_router
from src.api.webhooks.razorpay import router as razorpay_webhook_router
from src.api.webhooks.whatsapp import router as whatsapp_webhook_router
from src.api.webhooks.voice import router as voice_webhook_router
from src.infrastructure.postgres.core import close_db, init_db


async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="Agent API",
    version="1.0.0",
    description="Abandoned cart recovery agent API with WhatsApp, Razorpay, and Sarvam integrations.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def welcome() -> str:
    return "Welcome to Agent API"

@app.get("/health")
async def healthcheck() -> dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok", "service": "agent-api"}

app.include_router(cart_router,tags=["cart"])
app.include_router(payments_router,  tags=["payments"])
app.include_router(razorpay_webhook_router, tags=["webhooks"])
app.include_router(whatsapp_webhook_router,  tags=["webhooks"])
app.include_router(voice_webhook_router,  tags=["webhooks"])




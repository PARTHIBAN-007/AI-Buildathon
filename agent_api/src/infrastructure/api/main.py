from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.api.routes import payment_router, whatsapp_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent_API",
        description="API for the Agent AI Buildathon project",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def welcome() -> dict[str, str]:
        return {"message": "Welcome to Agent API"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "Healthy"}

    app.include_router(payment_router)
    app.include_router(whatsapp_router)
    return app


app = create_app()

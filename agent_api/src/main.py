from fastapi import FastAPI
from pydantic import BaseModel

from src.infrastructure.exotel.caller import make_outbound_call

app = FastAPI(
    title = "Agent_API",
    description = "API for the Agent AI Buildathon project",
    version = "1.0.0"
)

@app.get("/")
def welcome():
    return "Welcome to RazorPay AI Buildathon"


class CallRequest(BaseModel):
    phone_number: str


@app.post("/calls")
async def start_call(request: CallRequest):
    result = make_outbound_call(
        recipient_number=request.phone_number,
    )
    return {
        "success": True,
        "exotel": result,
    }
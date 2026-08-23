from fastapi import FastAPI

app = FastAPI(
    title = "Agent_API",
    
)


@app.get("/")
async def welcome():
    return "Welcome to RazorPay AI Buildathon"
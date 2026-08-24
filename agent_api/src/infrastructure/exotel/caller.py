import os
import requests
from src.config import get_settings

settings = get_settings()

def make_outbound_call(recipient_number: str):

    url = (
        f"{settings.EXOTEL_BASE_URL}"
        f"/v1/accounts/{settings.EXOTEL_ACCOUNT_SID}"
        f"/calls/connect"
    )

    payload = {
        "from": recipient_number,
        "callerid": settings.EXOTEL_PHONE_NUMBER,

        # Temporarily use a placeholder only if
        # AgentStream is enabled and you have a public WS.
        "streamurl": "wss://YOUR_DOMAIN/ws",
        "streamtype": "bidirectional",
    }

    print("URL:", url)
    print("Account SID:", settings.EXOTEL_ACCOUNT_SID)
    print("API key present:", bool(settings.EXOTEL_API_KEY))
    print("API token present:", bool(settings.EXOTEL_API_TOKEN))

    response = requests.post(
        url,
        auth=(
            settings.EXOTEL_API_KEY,
            settings.EXOTEL_API_TOKEN,
        ),
        data=payload,
        timeout=30,
    )

    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    response.raise_for_status()

    return response.json()
from __future__ import annotations

from typing import List, Dict, Any
import httpx
from loguru import logger

from src.config import get_settings

settings = get_settings()


class OpenRouterClient:
    """Simple async OpenRouter/OpenAI-compatible client.

    Uses settings.OPENAI_API_BASE (defaults to https://openrouter.ai/api/v1) and
    sends Bearer token from OPENAI_API_KEY. Returns the assistant text.
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.api_base = (api_base or settings.OPENAI_API_BASE) or "https://openrouter.ai/api/v1"
        self.model = model or settings.OPENAI_MODEL
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY must be configured to call the LLM")
        self._client = httpx.AsyncClient(timeout=settings.OPENAI_TIMEOUT)

    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        """Send a chat completion request.

        messages: list of {role: 'system'|'user'|'assistant', 'content': str}
        Returns the assistant content (string). Raises httpx.HTTPError on network problems.
        """
        url = f"{self.api_base.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload: Dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": max_tokens}

        logger.debug("OpenRouter request url=%s model=%s", url, self.model)
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        # Best-effort extraction supporting OpenAI-style or OpenRouter responses
        try:
            choice = data.get("choices", [])[0]
            if isinstance(choice.get("message"), dict):
                return choice["message"]["content"]
            if "text" in choice:
                return choice["text"]
        except Exception:
            logger.warning("Unexpected OpenRouter response shape: %s", data)
        # Fallback: return JSON string
        return str(data)

    async def close(self) -> None:
        await self._client.aclose()

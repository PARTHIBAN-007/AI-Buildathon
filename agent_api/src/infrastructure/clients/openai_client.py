from __future__ import annotations

from typing import List, Dict, Any
from openai import AsyncOpenAI
from loguru import logger

from src.config import get_settings

settings = get_settings()


class OpenRouterClient:
    """Simple async OpenRouter client using the official OpenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.api_base = api_base or getattr(settings, "OPENROUTER_API_BASE", None) or "https://openrouter.ai/api/v1"
        self.model = model or settings.OPENROUTER_MODEL

        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY must be configured to call the LLM")

        # Initialize the modern async OpenAI client configured for OpenRouter
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
        )

    async def chat(self, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
        logger.debug(f"OpenRouter request model={self.model}")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as err:
            logger.error(f"OpenRouter request failed: {err}")
            raise

    async def close(self) -> None:
        await self.client.close()
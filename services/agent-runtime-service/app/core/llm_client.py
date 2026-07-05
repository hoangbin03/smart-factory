"""
LLM Client - unified interface for OpenRouter / NVIDIA NIM API.
Handles model calls for all agents.
"""
from typing import Optional
import httpx
import structlog
from app.core.config import settings

logger = structlog.get_logger()


class LLMClient:
    """Unified LLM client supporting OpenRouter and NVIDIA NIM."""

    def __init__(self):
        self._openrouter_client = None

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Call the LLM and return the text response."""
        model = model or settings.DEFAULT_MODEL

        if self._is_configured(settings.OPENROUTER_API_KEY):
            return await self._call_openrouter(system_prompt, user_prompt, model, temperature, max_tokens)
        elif self._is_configured(settings.NVIDIA_API_KEY):
            return await self._call_nvidia(system_prompt, user_prompt, model, temperature, max_tokens)
        else:
            # Fallback: structured mock response for development
            logger.warning("No LLM API key configured, returning mock response")
            return self._mock_response(system_prompt, user_prompt)

    async def _call_openrouter(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-Title"] = settings.OPENROUTER_APP_NAME

        base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": settings.OPENROUTER_MODEL or model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_nvidia(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """NVIDIA NIM API - OpenAI-compatible format."""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model or "meta/llama-3.1-70b-instruct",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """Development mock response."""
        return f"""[MOCK LLM RESPONSE]
Task Analysis: {user_prompt[:100]}...

This is a mock response for development.
Configure OPENROUTER_API_KEY or NVIDIA_API_KEY for real LLM integration.

Result: Task analyzed and plan created successfully.
Steps completed: 3/3
Status: SUCCESS
"""


    def _is_configured(self, value: str) -> bool:
        return bool(value and value.strip() and not value.strip().lower().startswith("your_"))

llm_client = LLMClient()

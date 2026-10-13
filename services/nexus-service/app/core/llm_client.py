"""Nexus - LLM Client."""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()
_current_llm_config: ContextVar[Dict[str, Any]] = ContextVar("nexus_current_llm_config", default={})


@contextmanager
def llm_config_context(config: Optional[Dict[str, Any]]):
    token = _current_llm_config.set(config or {})
    try:
        yield
    finally:
        _current_llm_config.reset(token)


class LLMClient:
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        top_p: Optional[float] = None,
    ) -> str:
        options = self._resolve_options(model, temperature, max_tokens, top_p)
        provider = options.get("provider", "auto")

        if provider == "openrouter" and self._ok(settings.OPENROUTER_API_KEY):
            return await self._openrouter(system_prompt, user_prompt, options)
        if provider == "nvidia" and self._ok(settings.NVIDIA_API_KEY):
            return await self._nvidia(system_prompt, user_prompt, options)
        if self._ok(settings.OPENROUTER_API_KEY):
            return await self._openrouter(system_prompt, user_prompt, options)
        if self._ok(settings.NVIDIA_API_KEY):
            return await self._nvidia(system_prompt, user_prompt, options)
        return self._mock(user_prompt)

    async def _openrouter(self, sys: str, usr: str, options: Dict[str, Any]) -> str:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_APP_NAME,
        }
        payload = {
            "model": options["model"],
            "messages": [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            "temperature": options["temperature"],
            "max_tokens": options["max_tokens"],
        }
        self._add_optional_sampling(payload, options)
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _nvidia(self, sys: str, usr: str, options: Dict[str, Any]) -> str:
        payload = {
            "model": options["model"] or "meta/llama-3.1-70b-instruct",
            "messages": [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            "temperature": options["temperature"],
            "max_tokens": options["max_tokens"],
        }
        self._add_optional_sampling(payload, options)
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.NVIDIA_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def _resolve_options(
        self,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        top_p: Optional[float],
    ) -> Dict[str, Any]:
        config = _current_llm_config.get() or {}
        provider = str(config.get("provider") or "auto").strip().lower() or "auto"
        if provider not in {"auto", "openrouter", "nvidia"}:
            provider = "auto"
        configured_model = str(config.get("model") or "").strip()
        return {
            "provider": provider,
            "model": configured_model or model or settings.OPENROUTER_MODEL or settings.DEFAULT_MODEL,
            "temperature": self._float_option(config.get("temperature"), temperature, 0, 2),
            "max_tokens": self._int_option(config.get("max_tokens"), max_tokens, 128, 32768),
            "top_p": self._float_option(config.get("top_p"), top_p, 0, 1) if config.get("top_p") is not None or top_p is not None else None,
            "presence_penalty": self._float_option(config.get("presence_penalty"), None, -2, 2),
            "frequency_penalty": self._float_option(config.get("frequency_penalty"), None, -2, 2),
        }

    def _add_optional_sampling(self, payload: Dict[str, Any], options: Dict[str, Any]) -> None:
        for key in ["top_p", "presence_penalty", "frequency_penalty"]:
            if options.get(key) is not None:
                payload[key] = options[key]

    def _float_option(self, value: Any, fallback: Optional[float], minimum: float, maximum: float) -> Optional[float]:
        if value is None:
            return fallback
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return fallback
        return min(maximum, max(minimum, parsed))

    def _int_option(self, value: Any, fallback: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = fallback
        return min(maximum, max(minimum, parsed))

    def _mock(self, prompt: str) -> str:
        return f"[Nexus Mock] Question: {prompt[:80]}... Configure OPENROUTER_API_KEY to activate AI."

    def _ok(self, value: str) -> bool:
        return bool(value and value.strip() and not value.lower().startswith("your_"))


llm_client = LLMClient()
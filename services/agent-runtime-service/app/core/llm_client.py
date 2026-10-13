"""
LLM Client - unified interface for OpenRouter / NVIDIA NIM API.
Handles model calls for all agents.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()
_current_llm_config: ContextVar[Dict[str, Any]] = ContextVar("current_llm_config", default={})
_usage_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar("llm_usage", default=None)


@contextmanager
def llm_config_context(config: Optional[Dict[str, Any]]):
    token = _current_llm_config.set(config or {})
    try:
        yield
    finally:
        _current_llm_config.reset(token)


@contextmanager
def usage_context():
    """Accumulate token usage across every LLM call made inside this block."""
    acc: Dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    token = _usage_ctx.set(acc)
    try:
        yield acc
    finally:
        _usage_ctx.reset(token)


def current_prompt_injections() -> str:
    """Skills + memory currently in context, so the NAT ReAct path can prepend
    the same instructions the plain llm_client.complete() path injects."""
    cfg = _current_llm_config.get() or {}
    parts = []
    if cfg.get("skills_prompt"):
        parts.append(str(cfg["skills_prompt"]))
    if cfg.get("memory_prompt"):
        parts.append(str(cfg["memory_prompt"]))
    return "\n\n".join(parts)


def _record_usage(usage: Optional[Dict[str, Any]]) -> None:
    acc = _usage_ctx.get()
    if acc is None or not isinstance(usage, dict):
        return
    acc["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
    acc["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
    acc["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    acc["calls"] += 1


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
        top_p: Optional[float] = None,
    ) -> str:
        """Call the LLM and return the text response."""
        options = self._resolve_options(model, temperature, max_tokens, top_p)
        provider = options.get("provider", "auto")

        # Inject the agent's assigned skills (reusable instruction blocks) into
        # the system prompt so skills actually shape behaviour on every call.
        cfg = _current_llm_config.get() or {}
        skills_prompt = cfg.get("skills_prompt")
        if skills_prompt:
            system_prompt = f"{skills_prompt}\n\n{system_prompt}"

        # Inject long-term memory (RAG-retrieved knowledge from past work) so the
        # agent can build on prior decisions instead of starting blind.
        memory_prompt = cfg.get("memory_prompt")
        if memory_prompt:
            system_prompt = f"{system_prompt}\n\n{memory_prompt}"

        if provider == "openrouter" and self._is_configured(settings.OPENROUTER_API_KEY):
            return await self._call_openrouter(system_prompt, user_prompt, options)
        if provider == "nvidia" and self._is_configured(settings.NVIDIA_API_KEY):
            return await self._call_nvidia(system_prompt, user_prompt, options)
        if self._is_configured(settings.OPENROUTER_API_KEY):
            return await self._call_openrouter(system_prompt, user_prompt, options)
        if self._is_configured(settings.NVIDIA_API_KEY):
            return await self._call_nvidia(system_prompt, user_prompt, options)

        logger.warning("No LLM API key configured, returning mock response")
        return self._mock_response(system_prompt, user_prompt)

    async def _call_openrouter(self, system_prompt: str, user_prompt: str, options: Dict[str, Any]) -> str:
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        if settings.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_APP_NAME:
            headers["X-Title"] = settings.OPENROUTER_APP_NAME

        payload = {
            "model": options["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": options["temperature"],
            "max_tokens": options["max_tokens"],
        }
        self._add_optional_sampling(payload, options)

        base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            _record_usage(data.get("usage"))
            return data["choices"][0]["message"]["content"]

    async def _call_nvidia(self, system_prompt: str, user_prompt: str, options: Dict[str, Any]) -> str:
        """NVIDIA NIM API - OpenAI-compatible format."""
        payload = {
            "model": options["model"] or "meta/llama-3.1-70b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": options["temperature"],
            "max_tokens": options["max_tokens"],
        }
        self._add_optional_sampling(payload, options)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            _record_usage(data.get("usage"))
            return data["choices"][0]["message"]["content"]

    def _resolve_options(
        self,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        top_p: Optional[float],
    ) -> Dict[str, Any]:
        config = _current_llm_config.get() or {}
        configured_model = str(config.get("model") or "").strip()
        provider = str(config.get("provider") or "auto").strip().lower() or "auto"
        if provider not in {"auto", "openrouter", "nvidia"}:
            provider = "auto"

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
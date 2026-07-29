from __future__ import annotations

import json
import os
from typing import Any, Sequence

from providers.base import ModelResponse, ToolCall


class OpenAIProvider:
    """OpenAI Chat Completions provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str | Sequence[str] = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        # A provider may accept more than one env var name (first non-empty wins),
        # e.g. YeScale reads YESCALE_API_KEY but falls back to OPENAI_API_KEY.
        self.api_key_envs: list[str] = [api_key_env] if isinstance(api_key_env, str) else list(api_key_env)
        if not self.api_key_envs:
            raise ValueError("api_key_env must contain at least one env var name")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.default_model = default_model

    @property
    def api_key_env(self) -> str:
        """Primary env var name (kept for backwards compatibility)."""
        return self.api_key_envs[0]

    def resolve_api_key(self) -> str:
        for name in self.api_key_envs:
            value = (os.getenv(name) or "").strip()
            if value:
                return value
        names = " / ".join(self.api_key_envs)
        raise RuntimeError(f"Missing API key env var: {names}")

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install openai") from exc

        api_key = self.resolve_api_key()

        client = OpenAI(api_key=api_key, base_url=self.base_url)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in msg.tool_calls or []:
            args = self._parse_args(call.function.arguments)
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=msg.content, tool_calls=calls, raw=resp)

    @staticmethod
    def _parse_args(raw: str | None) -> dict[str, Any]:
        """Tolerate empty / malformed argument payloads instead of crashing the run."""
        text = (raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"_raw_arguments": text, "_parse_error": "invalid_json"}
        if not isinstance(parsed, dict):
            return {"_raw_arguments": text, "_parse_error": "not_an_object"}
        return parsed

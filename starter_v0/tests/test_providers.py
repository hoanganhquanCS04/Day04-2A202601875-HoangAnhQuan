from __future__ import annotations

import json
from typing import Any

import pytest

import providers
from providers import PROVIDER_CHOICES, make_provider
from providers.base import ModelResponse, ToolCall
from providers.openai_provider import OpenAIProvider
from providers.openrouter_provider import OpenRouterProvider
from providers.yescale_provider import DEFAULT_BASE_URL, DEFAULT_MODEL, YeScaleProvider


def test_yescale_is_a_registered_choice():
    assert "yescale" in PROVIDER_CHOICES
    assert isinstance(make_provider("yescale"), YeScaleProvider)


def test_every_registered_provider_is_constructible():
    # Constructors must not require an API key; keys are only read at complete().
    for name in PROVIDER_CHOICES:
        assert make_provider(name) is not None


def test_unknown_provider_message_lists_choices():
    with pytest.raises(ValueError) as excinfo:
        make_provider("nope")
    message = str(excinfo.value)
    assert "nope" in message
    for name in PROVIDER_CHOICES:
        assert name in message


def test_provider_choices_match_registry():
    assert PROVIDER_CHOICES == sorted(providers.PROVIDERS)


def test_yescale_defaults():
    provider = YeScaleProvider()
    assert provider.base_url == DEFAULT_BASE_URL == "https://api.yescale.io/v1"
    assert provider.default_model == DEFAULT_MODEL


def test_yescale_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_BASE_URL", "https://proxy.internal/v1")
    monkeypatch.setenv("YESCALE_MODEL", "gpt-4o")
    provider = YeScaleProvider()
    assert provider.base_url == "https://proxy.internal/v1"
    assert provider.default_model == "gpt-4o"


def test_yescale_base_url_ignores_openai_base_url(monkeypatch: pytest.MonkeyPatch):
    # A machine configured for the plain OpenAI provider must not silently
    # redirect the yescale provider somewhere else.
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    assert YeScaleProvider().base_url == DEFAULT_BASE_URL


def test_yescale_key_prefers_yescale_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_API_KEY", "sk-yescale")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert YeScaleProvider().resolve_api_key() == "sk-yescale"


def test_yescale_key_falls_back_to_openai_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert YeScaleProvider().resolve_api_key() == "sk-openai"


def test_blank_key_is_treated_as_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_API_KEY", "   ")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert YeScaleProvider().resolve_api_key() == "sk-openai"


def test_missing_key_error_names_both_env_vars():
    with pytest.raises(RuntimeError) as excinfo:
        YeScaleProvider().resolve_api_key()
    assert "YESCALE_API_KEY" in str(excinfo.value)
    assert "OPENAI_API_KEY" in str(excinfo.value)


def test_openai_provider_default_base_url_is_openai():
    assert OpenAIProvider().base_url == "https://api.openai.com/v1"


def test_openai_provider_honours_openai_base_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.yescale.io/v1")
    assert OpenAIProvider().base_url == "https://api.yescale.io/v1"


def test_openrouter_base_url_is_not_hijacked_by_openai_base_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.yescale.io/v1")
    assert OpenRouterProvider().base_url == "https://openrouter.ai/api/v1"


def test_api_key_env_property_is_backwards_compatible():
    assert OpenAIProvider().api_key_env == "OPENAI_API_KEY"
    assert YeScaleProvider().api_key_env == "YESCALE_API_KEY"


def test_empty_api_key_env_sequence_is_rejected():
    with pytest.raises(ValueError):
        OpenAIProvider(api_key_env=[])


# --------------------------------------------------------------------------- #
# Argument parsing of tool_calls
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"screenname": "sama"}', {"screenname": "sama"}),
        ("", {}),
        (None, {}),
        ("   ", {}),
    ],
)
def test_parse_args_valid_and_empty(raw: str | None, expected: dict[str, Any]):
    assert OpenAIProvider._parse_args(raw) == expected


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", '"a string"'])
def test_parse_args_malformed_does_not_raise(raw: str):
    parsed = OpenAIProvider._parse_args(raw)
    assert parsed["_raw_arguments"] == raw
    assert "_parse_error" in parsed


# --------------------------------------------------------------------------- #
# complete() wiring, with the OpenAI SDK stubbed out
# --------------------------------------------------------------------------- #
class _Function:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _Call:
    def __init__(self, name: str, arguments: str) -> None:
        self.function = _Function(name, arguments)


class _Message:
    def __init__(self, content: str | None, tool_calls: list[_Call] | None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message: _Message) -> None:
        self.message = message


class _Completion:
    def __init__(self, message: _Message) -> None:
        self.choices = [_Choice(message)]


def install_fake_openai(monkeypatch: pytest.MonkeyPatch, message: _Message) -> dict[str, Any]:
    """Replace the `openai` module so complete() never touches the network."""
    seen: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any):
            seen["kwargs"] = kwargs
            return _Completion(message)

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
            seen["api_key"] = api_key
            seen["base_url"] = base_url
            self.chat = FakeChat()

    import types

    module = types.ModuleType("openai")
    module.OpenAI = FakeOpenAI
    monkeypatch.setitem(__import__("sys").modules, "openai", module)
    return seen


def test_complete_sends_key_base_url_and_normalizes_calls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_API_KEY", "sk-test")
    message = _Message("thinking", [_Call("timeline", json.dumps({"screenname": "sama", "limit": 3}))])
    seen = install_fake_openai(monkeypatch, message)

    provider = YeScaleProvider()
    tools = [{"type": "function", "function": {"name": "timeline", "parameters": {}}}]
    response = provider.complete([{"role": "user", "content": "hi"}], tools, tool_choice="required")

    assert seen["api_key"] == "sk-test"
    assert seen["base_url"] == DEFAULT_BASE_URL
    assert seen["kwargs"]["model"] == DEFAULT_MODEL
    assert seen["kwargs"]["temperature"] == 0.0
    assert seen["kwargs"]["tool_choice"] == "required"
    assert seen["kwargs"]["tools"] == tools

    assert isinstance(response, ModelResponse)
    assert response.text == "thinking"
    assert response.tool_calls == [ToolCall(name="timeline", args={"screenname": "sama", "limit": 3})]


def test_complete_omits_tools_and_tool_choice_when_not_given(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_API_KEY", "sk-test")
    seen = install_fake_openai(monkeypatch, _Message("plain answer", None))

    response = YeScaleProvider().complete([{"role": "user", "content": "hi"}])

    assert "tools" not in seen["kwargs"]
    assert "tool_choice" not in seen["kwargs"]
    assert response.tool_calls == []
    assert response.text == "plain answer"


def test_complete_model_override_wins(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YESCALE_API_KEY", "sk-test")
    seen = install_fake_openai(monkeypatch, _Message("ok", None))
    YeScaleProvider().complete([{"role": "user", "content": "hi"}], model="gpt-4o")
    assert seen["kwargs"]["model"] == "gpt-4o"


def test_complete_without_key_raises_before_calling_the_api(monkeypatch: pytest.MonkeyPatch):
    install_fake_openai(monkeypatch, _Message("ok", None))
    with pytest.raises(RuntimeError, match="Missing API key"):
        YeScaleProvider().complete([{"role": "user", "content": "hi"}])

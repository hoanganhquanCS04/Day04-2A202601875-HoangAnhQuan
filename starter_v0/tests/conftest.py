"""Shared pytest fixtures.

Every test here is offline: no network call, no API key, no provider request.
HTTP is stubbed via monkeypatch on the `requests` module each tool imports.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ENV_VARS_TOUCHED = [
    "YESCALE_API_KEY", "YESCALE_BASE_URL", "YESCALE_MODEL",
    "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "OPENROUTER_API_KEY", "OPENROUTER_BASE_URL",
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "RAPIDAPI_KEY", "RAPIDAPI_TWITTER_HOST",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DAY04_ENV_FILE",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Also run tests marked `live`, which call real public APIs.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-live"):
        return
    skip = pytest.mark.skip(reason="needs --run-live (real network call)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a known env state.

    The repo's .env is loaded at import time by chat.py/run_eval.py, so without
    this the tests would silently depend on whichever keys the machine has.
    """
    for name in ENV_VARS_TOUCHED:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def repo_root() -> Path:
    return ROOT


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload: Any = None, *, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text or ""
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class RequestRecorder:
    """Captures the calls a tool makes so tests can assert on URL/params."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, method: str, url: str, kwargs: dict[str, Any]) -> None:
        self.calls.append({"method": method, "url": url, **kwargs})

    @property
    def last(self) -> dict[str, Any]:
        assert self.calls, "No HTTP call was recorded"
        return self.calls[-1]


@pytest.fixture
def http(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Factory: stub requests.get/post inside a tool module.

    Usage:
        recorder = http(tool_module, get=FakeResponse({...}))
    """
    def install(module: Any, *, get: Any = None, post: Any = None) -> RequestRecorder:
        recorder = RequestRecorder()

        def make(handler: Any, method: str):
            def fake(url: str, **kwargs: Any):
                recorder.record(method, url, kwargs)
                if callable(handler):
                    return handler(url, **kwargs)
                if isinstance(handler, Exception):
                    raise handler
                return handler
            return fake

        if get is not None:
            monkeypatch.setattr(module.requests, "get", make(get, "GET"))
        if post is not None:
            monkeypatch.setattr(module.requests, "post", make(post, "POST"))
        return recorder

    return install

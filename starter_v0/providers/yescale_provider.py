from __future__ import annotations

import os

from providers.openai_provider import OpenAIProvider


DEFAULT_BASE_URL = "https://api.yescale.io/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class YeScaleProvider(OpenAIProvider):
    """YeScale exposes an OpenAI-compatible Chat Completions surface.

    API key resolution order: YESCALE_API_KEY -> OPENAI_API_KEY, so a lab machine
    that already stores the YeScale key under OPENAI_API_KEY keeps working.
    """

    def __init__(self) -> None:
        super().__init__(
            api_key_env=("YESCALE_API_KEY", "OPENAI_API_KEY"),
            base_url=os.getenv("YESCALE_BASE_URL") or DEFAULT_BASE_URL,
            default_model=os.getenv("YESCALE_MODEL") or DEFAULT_MODEL,
        )

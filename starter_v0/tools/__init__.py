from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Folder names are intentionally vague to match the tool names students see.
# The imported function names are the underlying implementations (unchanged).
from .clarify.tool import ask_user
from .papers.tool import arxiv_search
from .paper_text.tool import get_arxiv_paper_text
from .timeline.tool import get_user_tweets
from .fetch.tool import read_url
from .format.tool import render_digest
from .policy.tool import search_company_policy
from .social_search.tool import search_tweets
from .send.tool import send_telegram
from .lookup.tool import web_search

# Tools written by this team (Phase 4). No API key required.
# Active generation (declared from v5 on): research-oriented sources.
from .wikipedia.tool import search_wikipedia
from .hackernews.tool import search_hackernews
from .crossref.tool import search_crossref

# First generation (declared in v0..v4). Superseded by the three above because
# they had no research use, but kept importable so those frozen artifact
# snapshots still load and every v0..v4 eval stays reproducible.
from .weather.tool import get_weather
from .currency.tool import convert_currency
from .crypto.tool import get_crypto_price


# NOTE (starter_v0): tool names here are intentionally vague. These keys are the
# names the model sees AND the names data/eval_base.json + data/eval_research_extension.json
# match against. If a team renames a tool, it MUST stay in sync across ALL of:
#   artifacts/tools.yaml  ->  this dict  ->  data/eval_base.json + data/eval_research_extension.json
# Otherwise the eval raises "not declared in tools.yaml" or scores every call as a name mismatch.
TOOL_FUNCTIONS = {
    "clarify": ask_user,
    "timeline": get_user_tweets,
    "social_search": search_tweets,
    "lookup": web_search,
    "fetch": read_url,
    "format": render_digest,
    "send": send_telegram,
    "policy": search_company_policy,
    "papers": arxiv_search,
    "paper_text": get_arxiv_paper_text,
    # --- team-written tools, active generation (v5+) ---
    "wikipedia": search_wikipedia,
    "hackernews": search_hackernews,
    "crossref": search_crossref,
    # --- team-written tools, first generation (declared in v0..v4 only) ---
    "weather": get_weather,
    "currency": convert_currency,
    "crypto": get_crypto_price,
}

# Names the model actually sees come from artifacts/tools.yaml, not from this
# dict. TOOL_FUNCTIONS is the superset of everything implemented, so a frozen
# snapshot from any version can still be loaded and re-run.
TEAM_TOOLS_ACTIVE = ("wikipedia", "hackernews", "crossref")
TEAM_TOOLS_LEGACY = ("weather", "currency", "crypto")


def load_tool_declarations(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["tools"]


def to_openai_tools(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": item["name"],
            "description": item.get("description", ""),
            "parameters": item.get("parameters", {"type": "object", "properties": {}}),
        },
    } for item in declarations]


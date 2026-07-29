"""Live smoke tests for the team tools (evidence that they really work).

Skipped by default. Run them with:

    python -m pytest tests/test_tools_live.py --run-live -v

They need no API key — Wikipedia, Hacker News (Algolia), Crossref, wttr.in,
open.er-api.com and CoinGecko are all public.
"""
from __future__ import annotations

import pytest

from tools import TOOL_FUNCTIONS


pytestmark = pytest.mark.live


# --------------------------------------------------------------------------- #
# Active generation (declared from v5)
# --------------------------------------------------------------------------- #
def test_wikipedia_live_concept_lookup():
    result = TOOL_FUNCTIONS["wikipedia"](query="retrieval augmented generation", max_results=2)
    assert "error" not in result, result
    assert result["result_count"] >= 1
    first = result["items"][0]
    assert "retrieval" in first["title"].lower()
    assert first["url"].startswith("https://en.wikipedia.org/")
    assert len(first["summary"]) > 50


def test_wikipedia_live_vietnamese_edition():
    result = TOOL_FUNCTIONS["wikipedia"](query="trí tuệ nhân tạo", lang="vi", max_results=1)
    assert "error" not in result, result
    assert result["items"][0]["url"].startswith("https://vi.wikipedia.org/")


def test_wikipedia_live_nonsense_query_returns_no_items():
    result = TOOL_FUNCTIONS["wikipedia"](query="zzzqqqxyy notarealconcept 12345")
    assert "error" not in result
    assert result["items"] == []


def test_hackernews_live_relevance():
    result = TOOL_FUNCTIONS["hackernews"](query="AI agents", sort="relevance", limit=3)
    assert "error" not in result, result
    assert 1 <= len(result["items"]) <= 3
    first = result["items"][0]
    assert first["title"]
    assert first["discussion_url"].startswith("https://news.ycombinator.com/item?id=")
    assert first["metrics"]["points"] >= 0


def test_hackernews_live_recent_window():
    result = TOOL_FUNCTIONS["hackernews"](query="LLM", sort="date", days=30, limit=5)
    assert "error" not in result, result
    assert result["days"] == 30
    assert result["sort"] == "date"


def test_crossref_live_search_by_title():
    result = TOOL_FUNCTIONS["crossref"](query="attention is all you need", max_results=2)
    assert "error" not in result, result
    assert result["items"]
    assert result["items"][0]["doi"]


def test_crossref_live_resolve_a_known_doi():
    result = TOOL_FUNCTIONS["crossref"](doi="10.1145/3442188.3445922")
    assert "error" not in result, result
    assert result["result_count"] == 1
    item = result["items"][0]
    assert item["doi"].lower() == "10.1145/3442188.3445922"
    assert item["year"]


def test_crossref_live_unknown_doi():
    assert "error" in TOOL_FUNCTIONS["crossref"](doi="10.9999/definitely-not-a-real-doi-12345")


# --------------------------------------------------------------------------- #
# First generation (still declared in the frozen v0..v4 snapshots)
# --------------------------------------------------------------------------- #
def test_weather_live_hanoi():
    result = TOOL_FUNCTIONS["weather"](location="Hanoi", days=2)
    assert "error" not in result, result
    assert isinstance(result["current"]["temperature"], float)
    assert len(result["forecast"]) == 2


def test_currency_live_usd_to_vnd():
    result = TOOL_FUNCTIONS["currency"](amount=100, from_currency="USD", to_currency="VND")
    assert "error" not in result, result
    assert result["rate"] > 1000


def test_crypto_live_bitcoin():
    result = TOOL_FUNCTIONS["crypto"](coin="BTC", vs_currency="usd")
    assert "error" not in result, result
    assert result["coin"] == "bitcoin"
    assert result["price"] > 0

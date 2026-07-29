"""Unit tests for the tools written by this team.

Active generation (declared from v5): wikipedia, hackernews, crossref.
First generation (declared in v0..v4): weather, currency, crypto — still tested
because those artifact snapshots must stay reproducible.

All HTTP is stubbed — these run offline and require no API key.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from conftest import FakeResponse
from tools.crossref import tool as crossref_tool
from tools.crypto import tool as crypto_tool
from tools.currency import tool as currency_tool
from tools.hackernews import tool as hackernews_tool
from tools.weather import tool as weather_tool
from tools.wikipedia import tool as wikipedia_tool


# =========================================================================== #
# wikipedia
# =========================================================================== #
WIKI_PAYLOAD: dict[str, Any] = {
    "query": {
        "pages": {
            "74020014": {"pageid": 74020014, "index": 2, "title": "Vector database",
                         "extract": "A vector database stores embeddings.\n\nIt supports similarity search."},
            "75229858": {"pageid": 75229858, "index": 1, "title": "Retrieval-augmented generation",
                         "extract": "RAG is a technique that enables large language models to retrieve information."},
        }
    }
}


def test_wikipedia_returns_ranked_items(http):
    recorder = http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    result = wikipedia_tool.search_wikipedia(query="retrieval augmented generation")

    assert "error" not in result
    assert result["result_count"] == 2
    # The API returns an unordered dict; "index" must restore search rank.
    assert [item["title"] for item in result["items"]] == ["Retrieval-augmented generation", "Vector database"]
    assert recorder.last["params"]["gsrsearch"] == "retrieval augmented generation"
    assert recorder.last["params"]["generator"] == "search"


def test_wikipedia_item_shape_is_digest_ready(http):
    http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    item = wikipedia_tool.search_wikipedia(query="rag")["items"][0]
    assert set(item) == {"title", "url", "source", "summary"}
    assert item["url"] == "https://en.wikipedia.org/?curid=75229858"
    assert item["source"] == "en.wikipedia.org"


def test_wikipedia_collapses_newlines_in_the_extract(http):
    http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    summaries = [item["summary"] for item in wikipedia_tool.search_wikipedia(query="x")["items"]]
    assert all("\n" not in summary for summary in summaries)
    assert "embeddings. It supports" in summaries[1]


def test_wikipedia_truncates_long_extracts(http):
    http(wikipedia_tool, get=FakeResponse({"query": {"pages": {
        "1": {"pageid": 1, "index": 1, "title": "Long", "extract": "word " * 500}}}}))
    summary = wikipedia_tool.search_wikipedia(query="x", max_chars=120)["items"][0]["summary"]
    assert len(summary) <= 120
    assert summary.endswith("...")


def test_wikipedia_language_is_used_in_the_url(http):
    recorder = http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    result = wikipedia_tool.search_wikipedia(query="rag", lang="VI")
    assert "vi.wikipedia.org" in recorder.last["url"]
    assert result["lang"] == "vi"
    assert result["items"][0]["url"].startswith("https://vi.wikipedia.org/")


@pytest.mark.parametrize(("given", "expected"), [(1, 1), (3, 3), (50, 10), (0, 1), (-4, 1)])
def test_wikipedia_max_results_is_clamped(http, given: int, expected: int):
    recorder = http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    wikipedia_tool.search_wikipedia(query="x", max_results=given)
    assert recorder.last["params"]["gsrlimit"] == expected


def test_wikipedia_max_chars_has_a_floor(http):
    http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    result = wikipedia_tool.search_wikipedia(query="x", max_chars=1)
    assert "error" not in result


@pytest.mark.parametrize("query", ["", "   ", None])
def test_wikipedia_requires_query(query):
    assert wikipedia_tool.search_wikipedia(query=query)["error"] == "ValueError"


@pytest.mark.parametrize("lang", ["e", "english-uk", "1n", "v1"])
def test_wikipedia_rejects_bad_language_code(lang: str):
    # No HTTP stub: validation must reject these before any request is made.
    result = wikipedia_tool.search_wikipedia(query="x", lang=lang)
    assert result["error"] == "ValueError"
    assert "lang" in result["message"]


@pytest.mark.parametrize("lang", ["", None])
def test_wikipedia_blank_language_falls_back_to_english(http, lang):
    recorder = http(wikipedia_tool, get=FakeResponse(WIKI_PAYLOAD))
    assert wikipedia_tool.search_wikipedia(query="x", lang=lang)["lang"] == "en"
    assert "en.wikipedia.org" in recorder.last["url"]


def test_wikipedia_rejects_non_numeric_max_results():
    assert wikipedia_tool.search_wikipedia(query="x", max_results="three")["error"] == "ValueError"


def test_wikipedia_no_match_returns_empty_items(http):
    http(wikipedia_tool, get=FakeResponse({"batchcomplete": ""}))
    result = wikipedia_tool.search_wikipedia(query="asdkjhasdkjh")
    assert "error" not in result
    assert result["items"] == []
    assert result["result_count"] == 0


def test_wikipedia_surfaces_an_api_level_error(http):
    http(wikipedia_tool, get=FakeResponse({"error": {"info": "Invalid parameter"}}))
    result = wikipedia_tool.search_wikipedia(query="x")
    assert result["error"] == "RuntimeError"
    assert "Invalid parameter" in result["message"]


def test_wikipedia_handles_http_error(http):
    http(wikipedia_tool, get=FakeResponse(None, status_code=503))
    assert "error" in wikipedia_tool.search_wikipedia(query="x")


def test_wikipedia_handles_transport_exception(http):
    http(wikipedia_tool, get=ConnectionError("down"))
    assert wikipedia_tool.search_wikipedia(query="x")["error"] == "ConnectionError"


# =========================================================================== #
# hackernews
# =========================================================================== #
HN_PAYLOAD: dict[str, Any] = {
    "hits": [
        {"objectID": "46990729", "title": "An AI agent published a hit piece on me",
         "url": "https://theshamblog.com/post", "points": 2346, "num_comments": 951,
         "author": "scottshambaugh", "created_at": "2026-02-12T16:23:24Z"},
        {"objectID": "48500012", "title": "AI agent bankrupted their operator",
         "url": "https://lantian.pub/article", "points": 1467, "num_comments": 536,
         "author": "lantian", "created_at": "2026-06-12T04:42:53Z"},
    ]
}


def test_hackernews_returns_items_with_metrics(http):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    result = hackernews_tool.search_hackernews(query="AI agents")

    assert "error" not in result
    assert result["result_count"] == 2
    first = result["items"][0]
    assert first["title"] == "An AI agent published a hit piece on me"
    assert first["metrics"] == {"points": 2346, "comments": 951, "author": "scottshambaugh"}
    assert first["discussion_url"] == "https://news.ycombinator.com/item?id=46990729"
    assert first["source"] == "theshamblog.com"
    assert recorder.last["params"]["tags"] == "story"


@pytest.mark.parametrize(("sort", "endpoint"), [("relevance", "/search"), ("date", "/search_by_date")])
def test_hackernews_sort_picks_the_right_endpoint(http, sort: str, endpoint: str):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    hackernews_tool.search_hackernews(query="x", sort=sort)
    assert recorder.last["url"].endswith(endpoint)


def test_hackernews_sort_is_case_insensitive(http):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    assert hackernews_tool.search_hackernews(query="x", sort="DATE")["sort"] == "date"
    assert recorder.last["url"].endswith("/search_by_date")


def test_hackernews_rejects_unknown_sort():
    assert hackernews_tool.search_hackernews(query="x", sort="popular")["error"] == "ValueError"


def test_hackernews_days_becomes_a_numeric_filter(http):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    before = int(time.time())
    hackernews_tool.search_hackernews(query="x", days=7)

    raw = recorder.last["params"]["numericFilters"]
    assert raw.startswith("created_at_i>")
    cutoff = int(raw.split(">")[1])
    assert before - 7 * 86400 - 5 <= cutoff <= before - 7 * 86400 + 5


def test_hackernews_no_time_filter_when_days_is_zero(http):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    hackernews_tool.search_hackernews(query="x", days=0)
    assert "numericFilters" not in recorder.last["params"]


@pytest.mark.parametrize(("given", "expected"), [(0, 0), (7, 7), (400, 365), (-3, 0)])
def test_hackernews_days_is_clamped(http, given: int, expected: int):
    http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    assert hackernews_tool.search_hackernews(query="x", days=given)["days"] == expected


@pytest.mark.parametrize(("given", "expected"), [(1, 1), (5, 5), (99, 20), (0, 1)])
def test_hackernews_limit_is_clamped(http, given: int, expected: int):
    recorder = http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    hackernews_tool.search_hackernews(query="x", limit=given)
    assert recorder.last["params"]["hitsPerPage"] == expected


def test_hackernews_limit_also_truncates_an_overlong_response(http):
    http(hackernews_tool, get=FakeResponse(HN_PAYLOAD))
    assert len(hackernews_tool.search_hackernews(query="x", limit=1)["items"]) == 1


def test_hackernews_falls_back_to_the_discussion_url(http):
    http(hackernews_tool, get=FakeResponse({"hits": [
        {"objectID": "1", "title": "Ask HN: something", "url": None, "points": 5, "num_comments": 2}]}))
    item = hackernews_tool.search_hackernews(query="x")["items"][0]
    assert item["url"] == "https://news.ycombinator.com/item?id=1"
    assert item["source"] == "news.ycombinator.com"


def test_hackernews_skips_hits_without_a_title(http):
    http(hackernews_tool, get=FakeResponse({"hits": [{"objectID": "1", "points": 1}]}))
    assert hackernews_tool.search_hackernews(query="x")["items"] == []


def test_hackernews_handles_missing_metrics(http):
    http(hackernews_tool, get=FakeResponse({"hits": [{"objectID": "1", "title": "T"}]}))
    item = hackernews_tool.search_hackernews(query="x")["items"][0]
    assert item["metrics"]["points"] == 0
    assert item["metrics"]["comments"] == 0


@pytest.mark.parametrize("query", ["", "   ", None])
def test_hackernews_requires_query(query):
    assert hackernews_tool.search_hackernews(query=query)["error"] == "ValueError"


def test_hackernews_rejects_non_numeric_limit():
    assert hackernews_tool.search_hackernews(query="x", limit="many")["error"] == "ValueError"


def test_hackernews_handles_http_error(http):
    http(hackernews_tool, get=FakeResponse(None, status_code=500))
    assert "error" in hackernews_tool.search_hackernews(query="x")


# =========================================================================== #
# crossref
# =========================================================================== #
CROSSREF_WORK: dict[str, Any] = {
    "title": ["Attention Is All You Need"],
    "author": [
        {"given": "Ashish", "family": "Vaswani"},
        {"given": "Noam", "family": "Shazeer"},
        {"given": "Niki", "family": "Parmar"},
        {"given": "Jakob", "family": "Uszkoreit"},
    ],
    "DOI": "10.5555/3295222.3295349",
    "URL": "https://doi.org/10.5555/3295222.3295349",
    "container-title": ["NIPS"],
    "published-print": {"date-parts": [[2017, 12]]},
    "is-referenced-by-count": 100000,
    "type": "proceedings-article",
}
CROSSREF_SEARCH = {"message": {"items": [CROSSREF_WORK]}}
CROSSREF_SINGLE = {"message": CROSSREF_WORK}


def test_crossref_search_by_query(http):
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SEARCH))
    result = crossref_tool.search_crossref(query="attention is all you need")

    assert "error" not in result
    item = result["items"][0]
    assert item["title"] == "Attention Is All You Need"
    assert item["doi"] == "10.5555/3295222.3295349"
    assert item["year"] == 2017
    assert item["journal"] == "NIPS"
    assert item["cited_by"] == 100000
    assert recorder.last["params"]["query.bibliographic"] == "attention is all you need"


def test_crossref_truncates_the_author_list(http):
    http(crossref_tool, get=FakeResponse(CROSSREF_SEARCH))
    item = crossref_tool.search_crossref(query="x")["items"][0]
    assert item["authors"] == "Ashish Vaswani, Noam Shazeer, Niki Parmar et al."
    assert "2017" in item["summary"] and "NIPS" in item["summary"]


def test_crossref_by_doi_uses_the_single_work_endpoint(http):
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SINGLE))
    result = crossref_tool.search_crossref(doi="10.5555/3295222.3295349")

    assert recorder.last["url"].endswith("/works/10.5555/3295222.3295349")
    assert "params" not in recorder.last
    assert result["result_count"] == 1
    assert result["doi"] == "10.5555/3295222.3295349"


def test_crossref_doi_wins_over_query(http):
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SINGLE))
    crossref_tool.search_crossref(query="something else", doi="10.1145/3442188")
    assert "/works/10.1145/3442188" in recorder.last["url"]


def test_crossref_requires_query_or_doi():
    result = crossref_tool.search_crossref()
    assert result["error"] == "ValueError"
    assert "doi" in result["message"] and "query" in result["message"]


@pytest.mark.parametrize("doi", ["not-a-doi", "10.1145", "abc"])
def test_crossref_validates_doi_shape_before_calling_network(doi: str):
    assert crossref_tool.search_crossref(doi=doi)["error"] == "ValueError"


@pytest.mark.parametrize(("given", "expected"), [(1, 1), (5, 5), (99, 20), (0, 1)])
def test_crossref_max_results_is_clamped(http, given: int, expected: int):
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SEARCH))
    crossref_tool.search_crossref(query="x", max_results=given)
    assert recorder.last["params"]["rows"] == expected


def test_crossref_falls_back_through_date_fields(http):
    work = dict(CROSSREF_WORK)
    work.pop("published-print")
    work["issued"] = {"date-parts": [[2019, 1, 1]]}
    http(crossref_tool, get=FakeResponse({"message": {"items": [work]}}))
    assert crossref_tool.search_crossref(query="x")["items"][0]["year"] == 2019


def test_crossref_handles_a_work_without_metadata(http):
    http(crossref_tool, get=FakeResponse({"message": {"items": [{"DOI": "10.1/x"}]}}))
    item = crossref_tool.search_crossref(query="x")["items"][0]
    assert item["title"] == ""
    assert item["year"] is None
    assert item["url"] == "https://doi.org/10.1/x"
    assert item["summary"]


def test_crossref_empty_search_result(http):
    http(crossref_tool, get=FakeResponse({"message": {"items": []}}))
    result = crossref_tool.search_crossref(query="asdkjhasd")
    assert "error" not in result
    assert result["items"] == []


def test_crossref_mailto_env_joins_the_polite_pool(http, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CROSSREF_MAILTO", "team@example.com")
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SEARCH))
    crossref_tool.search_crossref(query="x")
    assert "mailto:team@example.com" in recorder.last["headers"]["User-Agent"]


def test_crossref_works_without_the_optional_mailto(http):
    recorder = http(crossref_tool, get=FakeResponse(CROSSREF_SEARCH))
    assert "error" not in crossref_tool.search_crossref(query="x")
    assert "mailto" not in recorder.last["headers"]["User-Agent"]


def test_crossref_handles_http_error(http):
    http(crossref_tool, get=FakeResponse(None, status_code=404))
    assert "error" in crossref_tool.search_crossref(doi="10.1/nope")


def test_crossref_handles_transport_exception(http):
    http(crossref_tool, get=TimeoutError("slow"))
    assert crossref_tool.search_crossref(query="x")["error"] == "TimeoutError"


# =========================================================================== #
# First generation (v0..v4) — kept so those snapshots stay reproducible
# =========================================================================== #
WTTR_PAYLOAD: dict[str, Any] = {
    "current_condition": [{
        "temp_C": "25", "temp_F": "77",
        "FeelsLikeC": "28", "FeelsLikeF": "82",
        "weatherDesc": [{"value": "Light rain shower"}],
        "humidity": "94",
        "windspeedKmph": "11", "windspeedMiles": "7",
        "observation_time": "02:39 AM",
    }],
    "nearest_area": [{"areaName": [{"value": "Hanoi"}], "country": [{"value": "Vietnam"}]}],
    "weather": [
        {"date": "2026-07-29", "mintempC": "25", "maxtempC": "33", "mintempF": "77", "maxtempF": "91",
         "hourly": [{"weatherDesc": [{"value": "Patchy rain"}], "chanceofrain": "36"}]},
        {"date": "2026-07-30", "mintempC": "24", "maxtempC": "32", "mintempF": "75", "maxtempF": "89",
         "hourly": [{"weatherDesc": [{"value": "Sunny"}], "chanceofrain": "0"}]},
        {"date": "2026-07-31", "mintempC": "26", "maxtempC": "34", "mintempF": "79", "maxtempF": "93",
         "hourly": [{"weatherDesc": [{"value": "Cloudy"}], "chanceofrain": "10"}]},
    ],
}


def test_weather_metric_current_only(http):
    recorder = http(weather_tool, get=FakeResponse(WTTR_PAYLOAD))
    result = weather_tool.get_weather(location="Hanoi")

    assert "error" not in result
    assert result["location"] == "Hanoi, Vietnam"
    assert result["current"]["temperature"] == 25.0
    assert result["forecast"] == []
    assert recorder.last["params"] == {"format": "j1"}


def test_weather_imperial_switches_every_unit(http):
    http(weather_tool, get=FakeResponse(WTTR_PAYLOAD))
    result = weather_tool.get_weather(location="Hanoi", unit="imperial", days=1)
    assert result["current"]["temperature"] == 77.0
    assert result["current"]["wind_unit"] == "mph"
    assert result["forecast"][0]["max_temp"] == 91.0


@pytest.mark.parametrize(("days", "expected"), [(0, 0), (1, 1), (3, 3), (9, 3), (-2, 0)])
def test_weather_days_is_clamped_to_0_3(http, days: int, expected: int):
    http(weather_tool, get=FakeResponse(WTTR_PAYLOAD))
    assert len(weather_tool.get_weather(location="Hanoi", days=days)["forecast"]) == expected


def test_weather_location_is_url_quoted(http):
    recorder = http(weather_tool, get=FakeResponse(WTTR_PAYLOAD))
    weather_tool.get_weather(location="Ho Chi Minh City")
    assert " " not in recorder.last["url"]


@pytest.mark.parametrize("location", ["", "   ", None])
def test_weather_requires_location(location):
    assert weather_tool.get_weather(location=location)["error"] == "ValueError"


def test_weather_rejects_unknown_unit():
    assert weather_tool.get_weather(location="Hanoi", unit="kelvin")["error"] == "ValueError"


def test_weather_handles_http_error(http):
    http(weather_tool, get=FakeResponse(None, status_code=503))
    assert "error" in weather_tool.get_weather(location="Hanoi")


def test_weather_never_raises_on_partial_payload(http):
    http(weather_tool, get=FakeResponse({"current_condition": [{}]}))
    result = weather_tool.get_weather(location="Hanoi", days=2)
    assert "error" not in result
    assert result["current"]["temperature"] is None


ERAPI_PAYLOAD = {
    "result": "success",
    "time_last_update_utc": "Wed, 29 Jul 2026 00:02:31 +0000",
    "rates": {"USD": 1, "VND": 26252.669608, "EUR": 0.92},
}


def test_currency_converts_and_reports_rate(http):
    recorder = http(currency_tool, get=FakeResponse(ERAPI_PAYLOAD))
    result = currency_tool.convert_currency(amount=100, from_currency="USD", to_currency="VND")
    assert result["converted"] == round(100 * 26252.669608, 4)
    assert recorder.last["url"].endswith("/USD")


def test_currency_uppercases_lowercase_codes(http):
    http(currency_tool, get=FakeResponse(ERAPI_PAYLOAD))
    result = currency_tool.convert_currency(from_currency="usd", to_currency="vnd")
    assert (result["from_currency"], result["to_currency"]) == ("USD", "VND")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"from_currency": "", "to_currency": "VND"},
        {"from_currency": "USD", "to_currency": ""},
        {"from_currency": "US", "to_currency": "VND"},
        {"from_currency": "US1", "to_currency": "VND"},
    ],
)
def test_currency_validates_codes_before_calling_network(kwargs: dict[str, str]):
    assert currency_tool.convert_currency(**kwargs)["error"] == "ValueError"


def test_currency_unsupported_target(http):
    http(currency_tool, get=FakeResponse(ERAPI_PAYLOAD))
    assert currency_tool.convert_currency(from_currency="USD", to_currency="XYZ")["error"] == "RuntimeError"


COINGECKO_PAYLOAD = {"bitcoin": {"usd": 63780.0, "usd_24h_change": 0.8912, "usd_market_cap": 1.2798e12}}


def test_crypto_returns_price_and_change(http):
    http(crypto_tool, get=FakeResponse(COINGECKO_PAYLOAD))
    result = crypto_tool.get_crypto_price(coin="bitcoin", vs_currency="usd")
    assert result["price"] == 63780.0
    assert result["change_24h_pct"] == 0.89


@pytest.mark.parametrize(("given", "expected"), [("BTC", "bitcoin"), ("ETH", "ethereum"), ("some-new-coin", "some-new-coin")])
def test_crypto_ticker_aliases(given: str, expected: str):
    assert crypto_tool.normalize_coin(given) == expected


@pytest.mark.parametrize("coin", ["", "   ", None])
def test_crypto_requires_coin(coin):
    assert crypto_tool.get_crypto_price(coin=coin)["error"] == "ValueError"


def test_crypto_unknown_coin_id(http):
    http(crypto_tool, get=FakeResponse({}))
    assert crypto_tool.get_crypto_price(coin="notacoin")["error"] == "RuntimeError"

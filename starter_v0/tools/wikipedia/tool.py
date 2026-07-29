from __future__ import annotations

from typing import Any

import requests

from tools._shared import TIMEOUT, err


API_URL = "https://{lang}.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "AI20k-Day04-Research-Agent/1.0 (educational lab)"}
MAX_RESULTS_CAP = 10


def _clean(text: str, max_chars: int) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def search_wikipedia(query: str = "", lang: str = "en", max_results: int = 3, max_chars: int = 700) -> dict[str, Any]:
    """Background/definition lookup on Wikipedia: search + intro extract in one call.

    No API key required. Use this for stable, encyclopaedic context on a concept
    ("RAG là gì", "transformer architecture") — not for news, which is `lookup`.
    """
    try:
        text = (query or "").strip()
        if not text:
            raise ValueError("query is required, e.g. 'retrieval augmented generation'")
        language = (lang or "en").strip().lower()
        if not (language.isalpha() and 2 <= len(language) <= 5):
            raise ValueError("lang must be a Wikipedia language code such as en or vi")
        try:
            limit = int(max_results)
        except (TypeError, ValueError):
            raise ValueError("max_results must be an integer") from None
        limit = max(1, min(MAX_RESULTS_CAP, limit))
        try:
            chars = int(max_chars)
        except (TypeError, ValueError):
            raise ValueError("max_chars must be an integer") from None
        chars = max(100, chars)

        response = requests.get(
            API_URL.format(lang=language),
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "generator": "search",
                "gsrsearch": text,
                "gsrlimit": limit,
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError((data["error"] or {}).get("info") or "Wikipedia API error")

        pages = ((data.get("query") or {}).get("pages") or {}).values()
        # generator=search returns an unordered dict; "index" restores search rank.
        ranked = sorted(pages, key=lambda page: page.get("index", 999))
        items = [{
            "title": page.get("title") or "",
            "url": f"https://{language}.wikipedia.org/?curid={page.get('pageid')}",
            "source": f"{language}.wikipedia.org",
            "summary": _clean(page.get("extract") or "", chars),
        } for page in ranked[:limit]]

        return {
            "tool": "search_wikipedia",
            "query": text,
            "lang": language,
            "result_count": len(items),
            "items": items,
        }
    except Exception as exc:
        return err("search_wikipedia", exc)


if __name__ == "__main__":  # smoke test: python -m tools.wikipedia.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(search_wikipedia(query="retrieval augmented generation", max_results=2), ensure_ascii=False, indent=2))

from __future__ import annotations

import time
from typing import Any

import requests

from tools._shared import TIMEOUT, domain, err


BASE_URL = "https://hn.algolia.com/api/v1"
HEADERS = {"User-Agent": "AI20k-Day04-Research-Agent/1.0 (educational lab)"}
SORTS = {"relevance": "search", "date": "search_by_date"}
MAX_LIMIT = 20
MAX_DAYS = 365


def _item(hit: dict[str, Any]) -> dict[str, Any]:
    object_id = hit.get("objectID") or ""
    discussion = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
    story_url = hit.get("url") or discussion
    points = hit.get("points") or 0
    comments = hit.get("num_comments") or 0
    return {
        "title": hit.get("title") or hit.get("story_title") or "",
        "url": story_url,
        "source": domain(story_url) or "news.ycombinator.com",
        "summary": f"{points} points, {comments} comments trên Hacker News — thảo luận: {discussion}",
        "date": hit.get("created_at"),
        "discussion_url": discussion,
        "metrics": {"points": points, "comments": comments, "author": hit.get("author")},
    }


def search_hackernews(query: str = "", sort: str = "relevance", days: int = 0, limit: int = 5) -> dict[str, Any]:
    """What the developer community is discussing about a topic, via Hacker News.

    No API key required. `sort="relevance"` ranks by how discussed a story is;
    `sort="date"` returns the newest first. `days` restricts to the last N days.
    """
    try:
        text = (query or "").strip()
        if not text:
            raise ValueError("query is required, e.g. 'AI agents'")
        order = (sort or "relevance").strip().lower()
        if order not in SORTS:
            raise ValueError("sort must be 'relevance' or 'date'")
        try:
            count = int(limit)
        except (TypeError, ValueError):
            raise ValueError("limit must be an integer") from None
        count = max(1, min(MAX_LIMIT, count))
        try:
            window = int(days)
        except (TypeError, ValueError):
            raise ValueError("days must be an integer") from None
        window = max(0, min(MAX_DAYS, window))

        params: dict[str, Any] = {"query": text, "tags": "story", "hitsPerPage": count}
        if window:
            cutoff = int(time.time()) - window * 86400
            params["numericFilters"] = f"created_at_i>{cutoff}"

        response = requests.get(f"{BASE_URL}/{SORTS[order]}", params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        items = [_item(hit) for hit in (data.get("hits") or []) if hit.get("title") or hit.get("story_title")]
        return {
            "tool": "search_hackernews",
            "query": text,
            "sort": order,
            "days": window,
            "result_count": len(items),
            "items": items[:count],
        }
    except Exception as exc:
        return err("search_hackernews", exc)


if __name__ == "__main__":  # smoke test: python -m tools.hackernews.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(search_hackernews(query="AI agents", limit=3), ensure_ascii=False, indent=2))

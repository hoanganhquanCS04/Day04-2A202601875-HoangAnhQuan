from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


BASE_URL = "https://api.crossref.org/works"
MAX_RESULTS_CAP = 20


def _headers() -> dict[str, str]:
    # Crossref asks for a contact address to join the "polite pool" (better rate
    # limits). Optional: the API works without it, so no env var is required.
    mailto = (os.getenv("CROSSREF_MAILTO") or "").strip()
    contact = f"; mailto:{mailto}" if mailto else ""
    return {"User-Agent": f"AI20k-Day04-Research-Agent/1.0 (educational lab{contact})"}


def _authors(work: dict[str, Any], limit: int = 3) -> str:
    people = work.get("author") or []
    names = [
        " ".join(part for part in [person.get("given"), person.get("family")] if part).strip()
        or person.get("name", "")
        for person in people
    ]
    names = [name for name in names if name]
    if not names:
        return ""
    if len(names) > limit:
        return ", ".join(names[:limit]) + " et al."
    return ", ".join(names)


def _year(work: dict[str, Any]) -> int | None:
    for field in ("published-print", "published-online", "issued", "created"):
        parts = ((work.get(field) or {}).get("date-parts") or [[]])[0]
        if parts and parts[0]:
            return int(parts[0])
    return None


def _item(work: dict[str, Any]) -> dict[str, Any]:
    title = (work.get("title") or [""])[0]
    doi = work.get("DOI") or ""
    journal = (work.get("container-title") or [""])[0]
    year = _year(work)
    authors = _authors(work)
    parts = [part for part in [authors, str(year) if year else "", journal] if part]
    return {
        "title": title,
        "url": work.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
        "source": journal or "crossref.org",
        "summary": " — ".join(parts) or "Không có metadata tác giả/nguồn.",
        "doi": doi,
        "year": year,
        "authors": authors,
        "journal": journal,
        "cited_by": work.get("is-referenced-by-count"),
        "type": work.get("type"),
    }


def search_crossref(query: str = "", doi: str = "", max_results: int = 5) -> dict[str, Any]:
    """Peer-reviewed publication metadata (title, authors, year, DOI, journal) via Crossref.

    No API key required. Pass `doi` to resolve one exact publication, or `query`
    to search by title/keywords. Complements `papers`, which covers arXiv preprints.
    """
    try:
        identifier = (doi or "").strip()
        text = (query or "").strip()
        if not identifier and not text:
            raise ValueError("provide either doi or query, e.g. doi='10.1145/3442188' or query='attention is all you need'")
        try:
            rows = int(max_results)
        except (TypeError, ValueError):
            raise ValueError("max_results must be an integer") from None
        rows = max(1, min(MAX_RESULTS_CAP, rows))

        if identifier:
            if "/" not in identifier:
                raise ValueError("doi must look like '10.xxxx/suffix'")
            response = requests.get(f"{BASE_URL}/{identifier}", headers=_headers(), timeout=TIMEOUT)
            response.raise_for_status()
            works = [response.json()["message"]]
        else:
            response = requests.get(
                BASE_URL,
                params={"query.bibliographic": text, "rows": rows, "select": ",".join([
                    "title", "author", "DOI", "URL", "container-title",
                    "published-print", "published-online", "issued", "created",
                    "is-referenced-by-count", "type",
                ])},
                headers=_headers(),
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            works = response.json()["message"].get("items") or []

        items = [_item(work) for work in works[:rows]]
        return {
            "tool": "search_crossref",
            "query": text,
            "doi": identifier,
            "result_count": len(items),
            "items": items,
        }
    except Exception as exc:
        return err("search_crossref", exc)


if __name__ == "__main__":  # smoke test: python -m tools.crossref.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(search_crossref(query="attention is all you need", max_results=2), ensure_ascii=False, indent=2))

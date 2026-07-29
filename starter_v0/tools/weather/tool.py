from __future__ import annotations

from typing import Any

import requests

from tools._shared import TIMEOUT, err


WTTR_URL = "https://wttr.in/{location}"
# wttr.in returns HTML for a browser-ish User-Agent; a curl-style UA forces the JSON body.
HEADERS = {"User-Agent": "curl/8.0 (AI20k-Day04-Research-Agent)"}
MAX_DAYS = 3


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _current(block: dict[str, Any], unit: str) -> dict[str, Any]:
    metric = unit != "imperial"
    return {
        "temperature": _num(block.get("temp_C" if metric else "temp_F")),
        "feels_like": _num(block.get("FeelsLikeC" if metric else "FeelsLikeF")),
        "unit": "C" if metric else "F",
        "description": ((block.get("weatherDesc") or [{}])[0].get("value") or "").strip(),
        "humidity": _num(block.get("humidity")),
        "wind_speed": _num(block.get("windspeedKmph" if metric else "windspeedMiles")),
        "wind_unit": "km/h" if metric else "mph",
        "observation_time": block.get("observation_time"),
    }


def _forecast(blocks: list[dict[str, Any]], unit: str, days: int) -> list[dict[str, Any]]:
    metric = unit != "imperial"
    out: list[dict[str, Any]] = []
    for block in blocks[:days]:
        hourly = block.get("hourly") or []
        midday = hourly[len(hourly) // 2] if hourly else {}
        out.append({
            "date": block.get("date"),
            "min_temp": _num(block.get("mintempC" if metric else "mintempF")),
            "max_temp": _num(block.get("maxtempC" if metric else "maxtempF")),
            "unit": "C" if metric else "F",
            "description": ((midday.get("weatherDesc") or [{}])[0].get("value") or "").strip(),
            "chance_of_rain": _num(midday.get("chanceofrain")),
        })
    return out


def get_weather(location: str = "", unit: str = "metric", days: int = 0) -> dict[str, Any]:
    """Current conditions (and optional short forecast) for a place, via wttr.in.

    No API key required. `unit` is `metric` (°C, km/h) or `imperial` (°F, mph).
    `days` = 0 returns only current conditions; 1..3 adds that many forecast days.
    """
    try:
        place = (location or "").strip()
        if not place:
            raise ValueError("location is required, e.g. 'Hanoi'")
        if unit not in {"metric", "imperial"}:
            raise ValueError("unit must be 'metric' or 'imperial'")
        try:
            day_count = int(days)
        except (TypeError, ValueError):
            raise ValueError("days must be an integer between 0 and 3") from None
        day_count = max(0, min(MAX_DAYS, day_count))

        response = requests.get(
            WTTR_URL.format(location=requests.utils.quote(place)),
            params={"format": "j1"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        current_blocks = data.get("current_condition") or []
        if not current_blocks:
            raise RuntimeError(f"No weather data returned for {place!r}")
        current = _current(current_blocks[0], unit)

        area = (data.get("nearest_area") or [{}])[0]
        resolved = ", ".join(
            part for part in [
                ((area.get("areaName") or [{}])[0].get("value") or "").strip(),
                ((area.get("country") or [{}])[0].get("value") or "").strip(),
            ] if part
        ) or place

        forecast = _forecast(data.get("weather") or [], unit, day_count)
        summary = (
            f"{resolved}: {current['description']}, {current['temperature']}°{current['unit']} "
            f"(cảm giác {current['feels_like']}°{current['unit']}), độ ẩm {current['humidity']}%."
        )
        return {
            "tool": "get_weather",
            "location": resolved,
            "unit": unit,
            "current": current,
            "forecast": forecast,
            "items": [{
                "title": f"Thời tiết {resolved}",
                "url": f"https://wttr.in/{place}",
                "source": "wttr.in",
                "summary": summary,
            }],
        }
    except Exception as exc:
        return err("get_weather", exc)


if __name__ == "__main__":  # smoke test: python -m tools.weather.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(get_weather(location="Hanoi", days=2), ensure_ascii=False, indent=2))

from __future__ import annotations

from typing import Any

import requests

from tools._shared import TIMEOUT, err


API_URL = "https://open.er-api.com/v6/latest/{base}"


def convert_currency(amount: float = 1, from_currency: str = "", to_currency: str = "") -> dict[str, Any]:
    """Convert an amount between two currencies using open.er-api.com daily rates.

    No API key required. Currency codes are ISO-4217 (`USD`, `VND`, `EUR`, `JPY`).
    """
    try:
        base = (from_currency or "").strip().upper()
        target = (to_currency or "").strip().upper()
        if not base or not target:
            raise ValueError("from_currency and to_currency are required, e.g. USD -> VND")
        if not (base.isalpha() and len(base) == 3) or not (target.isalpha() and len(target) == 3):
            raise ValueError("Currency codes must be 3 letters, e.g. USD, VND, EUR")
        try:
            value = float(amount)
        except (TypeError, ValueError):
            raise ValueError("amount must be a number") from None

        response = requests.get(API_URL.format(base=base), timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("result") != "success":
            raise RuntimeError(data.get("error-type") or f"Unknown base currency: {base}")

        rates = data.get("rates") or {}
        if target not in rates:
            raise RuntimeError(f"Unsupported target currency: {target}")
        rate = float(rates[target])
        converted = round(value * rate, 4)
        summary = f"{value:g} {base} = {converted:,.4f} {target} (tỷ giá 1 {base} = {rate:,.4f} {target})"
        return {
            "tool": "convert_currency",
            "amount": value,
            "from_currency": base,
            "to_currency": target,
            "rate": rate,
            "converted": converted,
            "rate_date": data.get("time_last_update_utc"),
            "items": [{
                "title": f"{base} → {target}",
                "url": "https://www.exchangerate-api.com",
                "source": "open.er-api.com",
                "summary": summary,
            }],
        }
    except Exception as exc:
        return err("convert_currency", exc)


if __name__ == "__main__":  # smoke test: python -m tools.currency.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(convert_currency(amount=100, from_currency="USD", to_currency="VND"), ensure_ascii=False, indent=2))

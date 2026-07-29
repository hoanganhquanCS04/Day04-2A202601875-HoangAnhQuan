from __future__ import annotations

from typing import Any

import requests

from tools._shared import TIMEOUT, err


API_URL = "https://api.coingecko.com/api/v3/simple/price"
HEADERS = {"User-Agent": "AI20k-Day04-Research-Agent/1.0 (educational lab)"}

# Ticker/alias -> CoinGecko id, so the model can pass either "BTC" or "bitcoin".
COIN_ALIASES = {
    "btc": "bitcoin", "xbt": "bitcoin", "bitcoin": "bitcoin",
    "eth": "ethereum", "ethereum": "ethereum",
    "sol": "solana", "solana": "solana",
    "bnb": "binancecoin", "binancecoin": "binancecoin",
    "xrp": "ripple", "ripple": "ripple",
    "ada": "cardano", "cardano": "cardano",
    "doge": "dogecoin", "dogecoin": "dogecoin",
    "ton": "the-open-network",
    "usdt": "tether", "tether": "tether",
}


def normalize_coin(coin: str) -> str:
    key = (coin or "").strip().lower().replace(" ", "-")
    return COIN_ALIASES.get(key, key)


def get_crypto_price(coin: str = "", vs_currency: str = "usd") -> dict[str, Any]:
    """Spot price + 24h change for a cryptocurrency, via the public CoinGecko API.

    No API key required. `coin` accepts a ticker (`BTC`) or a CoinGecko id (`bitcoin`).
    """
    try:
        coin_id = normalize_coin(coin)
        if not coin_id:
            raise ValueError("coin is required, e.g. 'BTC' or 'bitcoin'")
        currency = (vs_currency or "usd").strip().lower()
        if not (currency.isalnum() and 2 <= len(currency) <= 5):
            raise ValueError("vs_currency must be a short code such as usd, vnd, eur")

        response = requests.get(
            API_URL,
            params={
                "ids": coin_id,
                "vs_currencies": currency,
                "include_24hr_change": "true",
                "include_market_cap": "true",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        entry = data.get(coin_id)
        if not entry:
            raise RuntimeError(f"Unknown coin id: {coin_id}")
        if currency not in entry:
            raise RuntimeError(f"Unsupported vs_currency: {currency}")

        price = float(entry[currency])
        change = entry.get(f"{currency}_24h_change")
        change_value = round(float(change), 2) if change is not None else None
        change_text = f", 24h {change_value:+.2f}%" if change_value is not None else ""
        summary = f"{coin_id} = {price:,.4f} {currency.upper()}{change_text}"
        return {
            "tool": "get_crypto_price",
            "coin": coin_id,
            "vs_currency": currency,
            "price": price,
            "change_24h_pct": change_value,
            "market_cap": entry.get(f"{currency}_market_cap"),
            "items": [{
                "title": f"{coin_id.upper()} / {currency.upper()}",
                "url": f"https://www.coingecko.com/en/coins/{coin_id}",
                "source": "coingecko.com",
                "summary": summary,
            }],
        }
    except Exception as exc:
        return err("get_crypto_price", exc)


if __name__ == "__main__":  # smoke test: python -m tools.crypto.tool
    import json

    from console import enable_utf8_io

    enable_utf8_io()
    print(json.dumps(get_crypto_price(coin="BTC", vs_currency="usd"), ensure_ascii=False, indent=2))

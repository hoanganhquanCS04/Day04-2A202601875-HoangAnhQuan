---
name: crypto
track: team_new
kind: live_api
provider: CoinGecko public API
requires_env: []
inputs: [coin, vs_currency]
outputs: [coin, vs_currency, price, change_24h_pct, market_cap, items]
side_effect: false
---
# crypto

Tool mới do nhóm tự viết. Lấy **giá giao ngay + biến động 24h** của một đồng
tiền mã hoá từ `https://api.coingecko.com/api/v3/simple/price`.

- **Không cần API key.**
- `coin`: bắt buộc. Nhận cả ticker (`BTC`, `ETH`, `SOL`) lẫn CoinGecko id
  (`bitcoin`, `ethereum`). Bảng `COIN_ALIASES` trong `tool.py` map ticker → id;
  giá trị lạ được đưa thẳng xuống API dưới dạng slug thường.
- `vs_currency`: đơn vị quy giá, mặc định `usd` (`vnd`, `eur`, ... đều được).

Trả về `price`, `change_24h_pct`, `market_cap` và `items` để nối sang `format`.

Lỗi (thiếu `coin`, coin id không tồn tại, `vs_currency` không hỗ trợ, HTTP lỗi)
trả về `{"tool": "get_crypto_price", "error": ..., "message": ...}`.

## Quicktest

```bash
python -m tools.crypto.tool
pytest tests/test_tools_team.py -k crypto
```

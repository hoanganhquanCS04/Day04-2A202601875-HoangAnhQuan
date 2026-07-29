---
name: currency
track: team_new
kind: live_api
provider: open.er-api.com (ExchangeRate-API free tier)
requires_env: []
inputs: [amount, from_currency, to_currency]
outputs: [amount, from_currency, to_currency, rate, converted, rate_date, items]
side_effect: false
---
# currency

Tool mới do nhóm tự viết. Quy đổi một số tiền giữa hai loại tiền tệ theo tỷ giá
cập nhật hằng ngày của `https://open.er-api.com/v6/latest/<BASE>`.

- **Không cần API key.**
- `amount`: số tiền cần đổi (mặc định `1`).
- `from_currency` / `to_currency`: bắt buộc, mã ISO-4217 3 ký tự (`USD`, `VND`, `EUR`, `JPY`).
  Tool tự viết hoa và tự kiểm tra định dạng trước khi gọi mạng.

Trả về `rate` (tỷ giá 1 đơn vị), `converted` (kết quả đã nhân), `rate_date`
(thời điểm tỷ giá) và `items` để nối sang `format`.

Lỗi (thiếu mã tiền, mã sai định dạng, mã không được hỗ trợ, HTTP lỗi) trả về
`{"tool": "convert_currency", "error": ..., "message": ...}`.

## Quicktest

```bash
python -m tools.currency.tool
pytest tests/test_tools_team.py -k currency
```

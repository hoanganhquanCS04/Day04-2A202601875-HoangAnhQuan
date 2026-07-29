---
name: weather
track: team_new
kind: live_api
provider: wttr.in
requires_env: []
inputs: [location, unit, days]
outputs: [location, current, forecast, items]
side_effect: false
---
# weather

Tool mới do nhóm tự viết. Trả về thời tiết **hiện tại** của một địa điểm và
(tuỳ chọn) dự báo ngắn 1–3 ngày, lấy từ `https://wttr.in/<location>?format=j1`.

- **Không cần API key** → chạy được ngay trên mọi máy trong nhóm.
- `location`: bắt buộc, tên thành phố (`Hanoi`, `Ho Chi Minh City`, `Tokyo`).
- `unit`: `metric` (°C, km/h — mặc định) hoặc `imperial` (°F, mph).
- `days`: `0` (mặc định) chỉ lấy hiện tại; `1..3` thêm bấy nhiêu ngày dự báo.
  Giá trị ngoài khoảng sẽ được kẹp về `[0, 3]`.

Output có cả `items` (title/url/source/summary) nên có thể nối thẳng sang `format`.

Mọi lỗi (thiếu `location`, `unit` sai, HTTP lỗi, địa điểm không tồn tại) được trả
về dạng `{"tool": "get_weather", "error": ..., "message": ...}` chứ không raise.

## Quicktest

```bash
python -m tools.weather.tool            # smoke test trực tiếp
pytest tests/test_tools_team.py -k weather
```

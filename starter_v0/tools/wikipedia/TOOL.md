---
name: wikipedia
track: team_new
kind: live_api
provider: Wikipedia MediaWiki Action API
requires_env: []
inputs: [query, lang, max_results, max_chars]
outputs: [query, lang, result_count, items]
side_effect: false
---
# wikipedia

Tool mới do nhóm tự viết. Tra **kiến thức nền / định nghĩa ổn định** trên Wikipedia:
tìm kiếm + lấy đoạn mở đầu (intro extract) của từng bài **trong một lần gọi API**
(`generator=search` + `prop=extracts`).

- **Không cần API key.**
- `query`: bắt buộc — khái niệm cần tra (`retrieval augmented generation`, `transformer`).
- `lang`: mã ngôn ngữ Wikipedia, mặc định `en` (dùng `vi` cho bản tiếng Việt).
- `max_results`: số bài, kẹp về `[1, 10]`, mặc định 3.
- `max_chars`: độ dài tối đa mỗi tóm tắt, tối thiểu 100, mặc định 700.

## Ranh giới với tool khác (quan trọng khi routing)

| Câu hỏi | Tool đúng |
|---|---|
| "X là gì", "giải thích khái niệm X" | **`wikipedia`** |
| "tin tức mới nhất về X" | `lookup` |
| "cộng đồng dev đang bàn gì về X" | `hackernews` |
| "có paper nào về X" | `papers` / `crossref` |

API trả kết quả dưới dạng dict không theo thứ tự; tool dùng field `index` để **khôi phục
đúng thứ hạng tìm kiếm** trước khi cắt `max_results`.

Lỗi (thiếu `query`, `lang` sai định dạng, API trả `error`, HTTP lỗi) được trả về dạng
`{"tool": "search_wikipedia", "error": ..., "message": ...}` chứ không raise.

## Quicktest

```bash
python -m tools.wikipedia.tool
pytest tests/test_tools_team.py -k wikipedia
pytest tests/test_tools_live.py --run-live -k wikipedia
```

---
name: hackernews
track: team_new
kind: live_api
provider: Hacker News Search (Algolia)
requires_env: []
inputs: [query, sort, days, limit]
outputs: [query, sort, days, result_count, items]
side_effect: false
---
# hackernews

Tool mới do nhóm tự viết. Xem **cộng đồng developer đang thảo luận gì** về một chủ đề,
qua Hacker News Search API của Algolia.

- **Không cần API key.**
- `query`: bắt buộc — chủ đề (`AI agents`, `LLM evaluation`).
- `sort`: `relevance` (mặc định, ưu tiên bài được thảo luận nhiều) hoặc `date` (mới nhất trước).
  Hai giá trị này map sang 2 endpoint khác nhau: `/search` và `/search_by_date`.
- `days`: chỉ lấy bài trong N ngày gần nhất; `0` = không giới hạn. Kẹp về `[0, 365]`.
- `limit`: số bài, kẹp về `[1, 20]`, mặc định 5.

Mỗi item có cả `url` (link bài gốc) lẫn `discussion_url` (link thread HN), kèm
`metrics.points` / `metrics.comments` để đánh giá mức độ được quan tâm.

## Ranh giới với tool khác

| Câu hỏi | Tool đúng |
|---|---|
| "cộng đồng dev / Hacker News nói gì về X" | **`hackernews`** |
| "trên Twitter mọi người nói gì về X" | `social_search` |
| "tin tức báo chí về X" | `lookup` |

`sort` ở đây song song với `search_type` của `social_search`:
`relevance` ↔ `Top`, `date` ↔ `Latest`.

Lỗi (thiếu `query`, `sort` không hợp lệ, HTTP lỗi) trả về
`{"tool": "search_hackernews", "error": ..., "message": ...}`.

## Quicktest

```bash
python -m tools.hackernews.tool
pytest tests/test_tools_team.py -k hackernews
pytest tests/test_tools_live.py --run-live -k hackernews
```

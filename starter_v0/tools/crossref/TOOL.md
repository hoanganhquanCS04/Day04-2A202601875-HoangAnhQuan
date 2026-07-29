---
name: crossref
track: team_new
kind: live_api
provider: Crossref REST API
requires_env: []
inputs: [query, doi, max_results]
outputs: [query, doi, result_count, items]
side_effect: false
---
# crossref

Tool mới do nhóm tự viết. Tra **metadata của bài báo đã xuất bản** (đã qua peer review)
trên Crossref: tiêu đề, tác giả, năm, DOI, tên tạp chí/hội nghị, số lượt trích dẫn.

- **Không cần API key.** `CROSSREF_MAILTO` là **tuỳ chọn** — nếu đặt, tool gửi kèm email
  trong `User-Agent` để vào "polite pool" của Crossref (rate limit thoáng hơn).
- `query`: tìm theo tiêu đề/từ khoá (`query.bibliographic`).
- `doi`: nếu biết DOI chính xác thì truyền vào đây để lấy đúng một bản ghi;
  tool kiểm tra định dạng `10.xxxx/suffix` trước khi gọi mạng.
- Phải có **ít nhất một** trong `query` hoặc `doi`.
- `max_results`: kẹp về `[1, 20]`, mặc định 5.

## Ranh giới với `papers` (arXiv)

| Câu hỏi | Tool đúng |
|---|---|
| "paper/preprint mới về X trên arXiv" | `papers` |
| "bài báo này đăng ở đâu, năm nào, DOI là gì" | **`crossref`** |
| "tìm bản đã xuất bản chính thức của paper X" | **`crossref`** |
| "đọc nội dung PDF của paper arXiv" | `paper_text` |

Nói ngắn gọn: `papers` = preprint arXiv, `crossref` = bản đã publish + metadata trích dẫn.
Hai tool bổ trợ nhau khi cần trích dẫn đúng chuẩn theo policy `source_citation`.

Lỗi (không truyền gì, DOI sai định dạng, DOI không tồn tại, HTTP lỗi) trả về
`{"tool": "search_crossref", "error": ..., "message": ...}`.

## Quicktest

```bash
python -m tools.crossref.tool
pytest tests/test_tools_team.py -k crossref
pytest tests/test_tools_live.py --run-live -k crossref
```

# Tổng hợp Yêu cầu — Lab04 Research Agent Tool Eval

## Tổng quan

Build một **Research Agent** nhận request từ user, chọn tool, truyền arguments, chạy tool thật, lưu JSON log, rồi dùng log đó để tối ưu prompt/tool declaration qua nhiều version theo vòng lặp evidence-driven.

---

## A. Yêu cầu bắt buộc (Core)

### A1. Setup & Provider
- Setup chạy được bằng **provider thật** (OpenAI-compatible API)
- Dùng **YeScale** làm provider thay OpenRouter: `base_url = https://api.yescale.io/v1`
- Thêm biến môi trường `YESCALE_API_KEY` vào `.env`
- Tạo provider `yescale` hoặc sửa config để dùng OpenAI-compatible endpoint
- Chạy pass `preflight_provider.py` với provider đã chọn

### A2. Agent Tools — Tối thiểu 5 tool trong `artifacts/tools.yaml`

**Core tools (đã có):**

| Tool | Chức năng | API/Backend |
|---|---|---|
| `clarify` | Hỏi lại user khi thiếu thông tin hoặc xác nhận yes/no | Local logic |
| `timeline` | Lấy bài đăng gần đây của một tài khoản Twitter | RapidAPI Twitter API45 |
| `social_search` | Tìm bài đăng Twitter theo từ khóa | RapidAPI Twitter API45 |
| `lookup` | Tìm kiếm trên web | Tavily API |
| `fetch` | Đọc nội dung URL | Firecrawl API |
| `format` | Trình bày items thành markdown digest | Local logic |

**Optional tools (có sẵn, không tính tool mới):**

| Tool | Chức năng |
|---|---|
| `send` | Gửi text lên Telegram |
| `policy` | Tìm trong company policy markdown nội bộ |
| `papers` | Tìm paper trên arXiv |
| `paper_text` | Tải/trích PDF arXiv |

### A3. Viết thêm ít nhất 1 tool mới
- Phải có `TOOL.md`, `tool.py` trong `tools/<tool_name>/`
- Đăng ký trong `tools/__init__.py`
- Thêm declaration vào `artifacts/tools.yaml`
- Smoke-test trực tiếp

### A4. Eval — Chạy base eval & tối ưu

| Bước | Chi tiết |
|---|---|
| Baseline v0 | Chạy `run_eval.py --version v0 --suite base` |
| 3 vòng tối ưu | v1, v2, v3 — mỗi vòng sửa 1 hypothesis, không copy-paste |
| Mỗi vòng chỉ sửa | `artifacts/system_prompt.md` và/hoặc `artifacts/tools.yaml` |
| Ghi version log | `artifacts/version_log.csv` với đầy đủ trường |

### A5. Team Eval Cases
- File `data/eval_group.json` phải có **đúng 10 case**:
  - 5 single-turn (dùng `query`)
  - 5 multi-turn (dùng `turns`)
- Mỗi case cần: `id`, `phase: "B"`, `failure_type`, `expect`, `metadata.what_it_tests`
- `failure_type` hợp lệ: `wrong_tool`, `wrong_arg_value`, `wrong_boundary`, `unnecessary_tool`, `out_of_scope`, `missing_info`

### A6. Live Chat
- Chạy `chat.py --version v3` ít nhất 3 live turn
- Lưu transcript vào `transcripts/*.transcript.json`

### A7. UI (Core deliverable)
- **Phải có UI chạy được** (khuyến nghị Streamlit, tự tạo `app.py`)
- Tái sử dụng `run_model_tool_loop` từ `chat.py`
- Hiển thị: request/response, trace tool (tên + args + result/error), version/artifact
- Deploy được để team khác test (Cloudflare Tunnel hoặc platform khác)

### A8. Report
- Hoàn thành `artifacts/REPORT.md`:
  - **Phần A**: Giới thiệu agent (1 trang, xong trước demo)
  - **Phần B**: Chi tiết / Bằng chứng (log thật v0→v3, failure analysis, eval, chat, reflection)

---

## B. Các file phải nộp

| File/Thư mục | Mục đích |
|---|---|
| `artifacts/system_prompt.md` | Instruction cho agent |
| `artifacts/tools.yaml` | Tên, mô tả và schema của tool |
| `artifacts/version_log.csv` | v0, v1, v2, v3 |
| `artifacts/REPORT.md` | Tài liệu demo và bằng chứng |
| `data/eval_group.json` | 10 team eval cases |
| `runs/*.json` | Run logs |
| `transcripts/*.transcript.json` | Chat logs |
| `analysis/*.csv` | Parse run logs (nếu có) |
| `tools/<new_tool>/` | Tool mới (TOOL.md + implementation) |
| `app.py` | UI code |

**KHÔNG nộp:** `.env`, API keys, `.venv/`, cache/build output

---

## C. Metric cần theo dõi

Từ run JSON `summary`:
- `case_accuracy` — Tỷ lệ case pass
- `tool_routing_accuracy` — Chọn đúng tool
- `argument_accuracy` — Truyền đúng args
- `multiturn_accuracy` — Multi-turn cases
- `provider_error_cases` — Phải = 0
- `measured_cases` — Phải = total_cases

---

## D. Quy tắc quan trọng

1. **Rename tool** → Phải sync 8 file (system_prompt, tools.yaml, __init__.py, eval_base, eval_research_extension, eval_group, REPORT, demo text)
2. **Eval cố định** — KHÔNG sửa `data/eval_base.json` (trừ field tên tool khi rename)
3. **Mỗi version** phải khác nhau thật sự, không 3 bản copy-paste
4. **tool_results có error** phải review thủ công — routing PASS ≠ tool chạy đúng
5. **Telegram creds unset** trong mọi `run_eval`

---

## E. Bonus (Optional)

- Viết thêm **hơn 3 tool mới** (ngoài 1 tool bắt buộc) → Bonus
- UI riêng lẻ hoặc optional built-in KHÔNG tính bonus
- Tool bonus phải có quicktest và evidence

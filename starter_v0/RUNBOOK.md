# Runbook — Research Agent (nhóm 2A202601183_NguyenMinhHung)

Mọi lệnh chạy từ thư mục `starter_v0/`.

## 1. Cài đặt

```bash
pip install -r requirements.txt
cp .env.example .env      # rồi điền YESCALE_API_KEY
```

Provider của nhóm là **YeScale** (OpenAI-compatible, `https://api.yescale.io/v1`).
Key được đọc theo thứ tự `YESCALE_API_KEY` → `OPENAI_API_KEY`, nên máy nào đã lưu key
YeScale dưới tên `OPENAI_API_KEY` vẫn chạy được ngay.

Ba tool của nhóm (`weather`, `currency`, `crypto`) **không cần API key**.
`lookup` / `fetch` / `timeline` / `social_search` cần Tavily / Firecrawl / RapidAPI —
thiếu key thì tool trả `{"error": ...}` chứ không làm sập agent.

## 2. Kiểm tra provider

```bash
python scripts/preflight_provider.py --provider yescale
# OK provider=yescale model=gpt-4o-mini / tool=timeline / args={'screenname': 'sama'}
```

## 3. Chạy test (không cần key, không gọi mạng)

```bash
python -m pytest -q                              # 335 test offline, ~4s
python -m pytest tests/test_tools_live.py --run-live -v   # 11 smoke test gọi API thật
```

## 4. Chạy UI

```bash
streamlit run app.py        # http://localhost:8501
```

Sidebar cho phép đổi provider và **đổi artifact version** (`v0`…`v4`, `current`), hiển thị
`artifact_version` + hash, danh sách tool, và toàn văn system prompt. Mỗi lượt chat hiện
**tool trace** (tên tool, args, result/error theo từng round) và tự lưu transcript.

Public tạm thời khi demo:

```bash
cloudflared tunnel --url http://localhost:8501
```

## 5. Chat CLI

```bash
python chat.py --provider yescale --version v3
```

## 6. Chạy lại eval (tái lập số liệu trong REPORT.md)

Mỗi version là một snapshot đóng băng trong `artifacts/versions/<version>/`:

```bash
# baseline
python run_eval.py --provider yescale --version v0 --suite base \
  --eval-cases data/eval_base.json \
  --system-prompt artifacts/versions/v0/system_prompt.md \
  --tools artifacts/versions/v0/tools.yaml

# v1 / v2 / v3 — đổi cả 3 chỗ "v0" thành version tương ứng
# suite group:     --suite group     --eval-cases data/eval_group.json
# suite extension: --suite extension --eval-cases data/eval_research_extension.json
```

`artifacts/system_prompt.md` và `artifacts/tools.yaml` chính là **bản v3 đã promote**, nên
bỏ hai flag `--system-prompt/--tools` cũng cho ra đúng kết quả v3.

> Giữ `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` **không set** khi chạy eval.

## 7. Tổng hợp log

```bash
python scripts/parse_runs.py runs --output analysis/run-analysis.csv
```

## 8. Bản đồ file

| Đường dẫn | Nội dung |
|---|---|
| `app.py` | Streamlit UI, dùng lại `run_model_tool_loop` của `chat.py` |
| `providers/yescale_provider.py` | Provider YeScale |
| `console.py` | Ép stdin/stdout/stderr về UTF-8 (Windows cp1252) |
| `tools/{wikipedia,hackernews,crossref}/` | 3 tool nhóm tự viết, đang dùng từ v5 (+ `TOOL.md`) |
| `tools/{weather,currency,crypto}/` | 3 tool thế hệ 1, đã gỡ khỏi khai báo nhưng giữ để v0–v4 chạy lại được |
| `artifacts/versions/v0..v5/` | Snapshot prompt + tools của từng version (v0–v4 đóng băng, v5 hiện hành) |
| `artifacts/version_log.csv` | Log v0→v4 với hypothesis + metric before/after (v5 chờ chạy) |
| `artifacts/REPORT.md` | Báo cáo phần A + phần B |
| `runs/` | Log eval thật (12 file, v0→v4) |
| `transcripts/` | Log chat thật |
| `analysis/run-analysis.csv` | Bảng phẳng tổng hợp mọi case của mọi run |
| `tests/` | 335 test offline + 11 live test |

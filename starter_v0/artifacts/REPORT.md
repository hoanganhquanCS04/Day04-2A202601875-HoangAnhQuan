# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần:
> - **PHẦN A — Giới thiệu agent**: 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v4, failure, eval, chat) dựa trên log thật trong `runs/` và `transcripts/`.

## Team

- Team: `2A202601183_NguyenMinhHung`
- Members: Nguyễn Minh Hùng
- Provider/model: **YeScale** (`https://api.yescale.io/v1`, OpenAI-compatible) — `gpt-4o-mini`
- Artifact version đã đo đầy đủ: `v3+p30313fe07c5d+t2f8acacc59f0`
- Artifact version hiện hành (đã promote vào `artifacts/`): `v5+pa2f00421a324+ta5999349dd0e` — **chưa đo**, xem mục B8
- Ngày chạy toàn bộ eval v0→v4: **2026-07-29**

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research Agent nhận yêu cầu tiếng Việt, **tự chọn tool** và **tự điền tham số** để: tìm tin tức trên web,
tìm/đọc bài đăng Twitter theo tài khoản hoặc theo chủ đề, đọc nội dung một URL cụ thể, tra cứu policy nội bộ
và paper arXiv, rồi trình bày kết quả thành digest markdown. Nhóm bổ sung 3 nguồn research không cần API key:
**Wikipedia (kiến thức nền), Hacker News (thảo luận cộng đồng dev), Crossref (metadata bài đã xuất bản + DOI)**.

Điểm thiết kế trung tâm: cùng một chủ đề nhưng **khác loại nguồn thì khác tool**.
"Vector database là gì" → `wikipedia`; "tin mới về vector database" → `lookup`;
"dev bàn gì về vector database" → `hackernews`; "paper về nó" → `papers` (preprint) hoặc `crossref` (đã xuất bản).

Điểm nhấn về hành vi: agent **hỏi lại khi thiếu thông tin**, **xác nhận trước khi gửi ra ngoài**, và
**không gọi tool** cho câu hỏi ngoài phạm vi hoặc khi người dùng đã huỷ yêu cầu.

**Link dùng thử:**

- Chạy tại chỗ: `cd starter_v0 && streamlit run app.py` → `http://localhost:8501`
- Public tạm thời (chạy khi demo): `cloudflared tunnel --url http://localhost:8501` → dán URL `*.trycloudflare.com` vào đây.
- URL showdown: `__________________________` *(điền ngay trước buổi demo; tunnel chỉ sống trong phiên chạy)*

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi lại khi thiếu thông tin, hoặc xác nhận yes/no trước hành động ghi | không (core) |
| `timeline` | Lấy bài đăng gần đây **của một tài khoản** Twitter/X | không (core) |
| `social_search` | Tìm bài đăng Twitter/X **theo chủ đề/từ khoá** | không (core) |
| `lookup` | Tìm kiếm web/tin tức qua Tavily (`topic`, `timeframe`) | không (core) |
| `fetch` | Đọc nội dung một URL đã biết qua Firecrawl | không (core) |
| `format` | Trình bày items đã có thành digest markdown | không (core) |
| `send` | Gửi text lên Telegram — **bắt buộc xác nhận trước** | không (optional built-in) |
| `policy` | Tra quy định nội bộ trong `company_policy/*.md` | không (optional built-in) |
| `papers` | Tìm paper trên arXiv | không (optional built-in) |
| `paper_text` | Tải PDF arXiv và trích text | không (optional built-in) |
| **`wikipedia`** | **Định nghĩa/kiến thức nền: tìm + lấy đoạn mở đầu bài Wikipedia (không cần key)** | **CÓ — tool bắt buộc** |
| **`hackernews`** | **Cộng đồng dev bàn gì về chủ đề X, kèm điểm/số bình luận (không cần key)** | **CÓ — bonus** |
| **`crossref`** | **Metadata bài đã xuất bản: tác giả, năm, DOI, tạp chí (không cần key)** | **CÓ — bonus** |

> Ba tool thế hệ đầu (`weather`, `currency`, `crypto`) đã được **gỡ khỏi khai báo từ v5** vì không phục vụ
> nghiệp vụ research. Implementation vẫn nằm trong `tools/` để mọi snapshot v0–v4 chạy lại được nguyên vẹn.

## A3. Câu hỏi mẫu để thử

1. `RAG là gì vậy? Giải thích khái niệm nền tảng cho mình với.` → `wikipedia`
2. `Trên Hacker News, bài nào về AI agents được thảo luận nhiều nhất trong tuần qua?` → `hackernews{sort:relevance, days:7}`
3. `Tra giúp mình metadata bài báo DOI 10.1145/3442188.3445922 để trích dẫn` → `crossref{doi}`
4. `Tóm tắt 5 tweet mới nhất giúp mình` → `clarify` (thiếu handle, agent hỏi lại thay vì đoán bừa)
5. `Gửi bản digest research hôm nay lên Telegram giúp mình` → `clarify` yes/no (không tự gửi)
6. `Viết hộ mình phần Related Work cho bài báo` → trả lời thẳng, **không gọi tool**

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| `RAG là gì?` | `wikipedia{query}` → đoạn mở đầu + link Wikipedia thật | Tool thế hệ 2 (v5): tách "khái niệm" khỏi "tin tức" | `pytest tests/test_tools_live.py --run-live -k wikipedia` |
| `Dev bàn gì về AI agents tuần qua?` | `hackernews{sort:"relevance", days:7}` | `sort` song song `search_type` của `social_search`: relevance↔Top | live test `-k hackernews` |
| `Tra DOI 10.1145/... để trích dẫn` | `crossref{doi}` → tác giả/năm/tạp chí | Ranh giới `papers` (preprint) vs `crossref` (đã publish) | live test `-k crossref` |
| `Tóm tắt 5 tweet mới nhất giúp mình` | `clarify{response_type:"text"}` | **v0 đoán bừa `screenname:"sama"`** → v1 cấm đoán | `runs/v0_B_base_*.json` R10 vs `runs/v1_B_base_*.json` |
| `Đăng bản tin này lên Telegram` | `clarify{response_type:"yes_no"}` | **v0 gọi thẳng `send`** → v1/v3 chặn | `runs/v0_B_base_*.json` R12 |
| `Gửi ngay báo cáo lên Telegram` | `clarify{response_type:"yes_no"}` | v1/v2 vẫn hỏi mở (`text`) → **v3 thêm thứ tự ưu tiên** → PASS | `runs/v2_B_group_*.json` G05 vs `runs/v3_B_group_*.json` |
| `Thôi bỏ đi, mình không cần tìm nữa` | không có tool call nào | v0 gọi `send` để nói lời chào → v1 sửa | `runs/v0_B_group_*.json` G10 |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: **mọi run dưới đây đều có `provider_error_cases = 0` và `measured_cases = total_cases`.**
> Các `tool_results` có error đã được review thủ công ở mục B5.

## B0. Cách tổ chức version (quan trọng khi chấm)

Mỗi version được **đóng băng thành snapshot** trong `artifacts/versions/<version>/`, và mỗi lần chạy eval đều
trỏ thẳng vào snapshot đó:

```bash
python run_eval.py --provider yescale --version v1 --suite base \
  --eval-cases data/eval_base.json \
  --system-prompt artifacts/versions/v1/system_prompt.md \
  --tools artifacts/versions/v1/tools.yaml
```

Nhờ vậy mọi con số trong báo cáo đều **chạy lại được y hệt**, và `artifact_version` (hash prompt + hash tools)
trong file run khớp chính xác với snapshot.

**v0 → v4 đã đóng băng.** Ba tool nhóm (thế hệ 1) được khai báo **ngay từ v0** với mô tả cụt lủn đúng phong
cách starter, nên **danh sách tool giống hệt nhau suốt v0–v4** — biến duy nhất được đo là *chất lượng prompt +
chất lượng mô tả tool*, không phải số lượng tool. Test `test_tool_inventory_is_identical_across_the_frozen_versions`
khoá ràng buộc này, và `test_legacy_team_tool_is_still_declared_in_the_frozen_snapshots` chặn việc sửa lén
snapshot cũ.

**v5 là thế hệ tool thứ 2** (xem B5b): thay đúng 3 tool nhóm, giữ nguyên toàn bộ core/bonus, tổng số tool
không đổi (test `test_v5_swaps_exactly_the_three_team_tools`). `artifacts/system_prompt.md` +
`artifacts/tools.yaml` là **bản v5 đã promote** (test `test_live_artifacts_match_the_current_snapshot`).

## B1. Version evidence

Nguồn: `artifacts/version_log.csv` + `runs/*.json`.

| Version | Prompt/tool change | Hypothesis | Metric | Before | After | Run file |
|---|---|---|---|---:|---:|---|
| v0 | baseline (prompt starter + mô tả tool starter) | Đo hành vi chưa tối ưu: prompt bảo agent đoán bừa, tự gửi; mô tả tool 3–4 từ | `case_accuracy@base` | — | **0.75** | `runs/v0_B_base_yescale_20260729T103332398665.json` |
| v0 | " | " | `case_accuracy@group` | — | **0.60** | `runs/v0_B_group_yescale_20260729T103556988126.json` |
| v1 | `system_prompt.md` | Fail tập trung ở `missing_info` / `wrong_boundary` / `out_of_scope` vì prompt starter **cấm hỏi lại** và **cho phép tự gửi**. Viết lại prompt với 5 nguyên tắc + bảng chọn tool + quy ước arg sẽ kéo accuracy lên | `case_accuracy@base` | 0.75 | **1.00** | `runs/v1_B_base_yescale_20260729T103502240132.json` |
| v1 | " | " | `case_accuracy@group` | 0.60 | **0.90** | `runs/v1_B_group_yescale_20260729T103621753824.json` |
| v2 | `tools.yaml` | Base đã bão hoà nhưng luật routing chỉ nằm trong prompt; mô tả tool vẫn là `"Xem thời tiết."`. Đưa luật routing + quy ước arg vào thẳng `description`/`enum` sẽ **giữ** base 1.0 và giảm phụ thuộc vào prompt | `case_accuracy@base` | 1.00 | **1.00** | `runs/v2_B_base_yescale_20260729T103802007838.json` |
| v2 | " | " | `case_accuracy@group` | 0.90 | **0.90** | `runs/v2_B_group_yescale_20260729T103830666503.json` |
| v3 | `system_prompt.md` + `tools.yaml` | G05 vẫn fail: request **vừa là hành động gửi vừa thiếu chi tiết**, model ưu tiên hỏi mở. Thêm **thứ tự ưu tiên** (huỷ > ngoài phạm vi > hành động ghi > thiếu thông tin) vào cả prompt lẫn mô tả `clarify`/`send` | `case_accuracy@group` | 0.90 | **1.00** | `runs/v3_B_group_yescale_20260729T104232640868.json` |
| v3 | " | " | `case_accuracy@base` | 1.00 | **1.00** | `runs/v3_B_base_yescale_20260729T104058405790.json` |
| v4 *(vòng bổ sung, ngoài 3 vòng bắt buộc)* | `system_prompt.md` + `tools.yaml` | Trên suite `extension`, routing = 1.0 nhưng args = 0.6: **cả 4 case fail đều để `policy_area` trống hoặc `all`**. Enum có liệt kê giá trị nhưng không nói *khi nào* dùng giá trị nào → thêm từ khoá nhận diện cho từng nhóm | `case_accuracy@extension` | 0.60 | **0.90** | `runs/v4_B_extension_yescale_20260729T105537976592.json` |
| v4 | " | không được làm hỏng suite cũ | `case_accuracy@base` / `@group` | 1.00 / 1.00 | **1.00 / 1.00** | `runs/v4_B_base_*.json`, `runs/v4_B_group_*.json` |

**Metric chi tiết (từ `summary` của mỗi run):**

| Version | Suite | case_acc | routing_acc | arg_acc | multiturn_acc | provider_errors |
|---|---|---:|---:|---:|---:|---:|
| v0 | base | 0.75 | 0.80 | 0.75 | 1.00 | 0 |
| v1 | base | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| v2 | base | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| v3 | base | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| v0 | group | 0.60 | 0.60 | 0.60 | 0.80 | 0 |
| v1 | group | 0.90 | 1.00 | 0.90 | 1.00 | 0 |
| v2 | group | 0.90 | 1.00 | 0.90 | 1.00 | 0 |
| v3 | group | **1.00** | 1.00 | 1.00 | 1.00 | 0 |
| v3 | extension | 0.60 | 1.00 | 0.60 | — | 0 |
| v4 | extension | **0.90** | 0.90 | 0.90 | — | 0 |

**Ba version khác nhau thật sự** (hash trong `version_log.csv`, test `test_each_delivered_version_has_a_distinct_artifact_version` kiểm tra tự động):

| | prompt_hash | tools_hash |
|---|---|---|
| v0 | `eb1c8179815b` | `2e1d7812adc4` |
| v1 | `6ea19e92bfda` *(đổi)* | `2e1d7812adc4` *(giữ nguyên)* |
| v2 | `6ea19e92bfda` *(giữ nguyên)* | `ba80f8c36621` *(đổi)* |
| v3 | `30313fe07c5d` *(đổi)* | `2f8acacc59f0` *(đổi)* |

## B2. Failure analysis

Lấy trực tiếp từ `results[*].result` của các run thật.

### v0 — base (5 fail / 20)

| Case ID | Failure type | Actual tool calls | Cái gì sai | Fix ở đâu |
|---|---|---|---|---|
| `R08_out_of_scope` | `out_of_scope` | `send{text:"Nguyên hàm của x^2 là ..."}` | Câu toán ngoài phạm vi, agent **giải xong rồi tự gửi Telegram** — vừa gọi tool thừa vừa vượt ranh giới ghi | v1: nguyên tắc 3 (ngoài phạm vi → trả lời thẳng, không tool) |
| `R10_missing_handle` | `missing_info` | `timeline{screenname:"sama", limit:5}` | Không biết tweet của ai nhưng **đoán bừa Sam Altman** đúng như prompt starter yêu cầu | v1: nguyên tắc 1 (thiếu info → `clarify`, cấm đoán) |
| `R11_missing_url` | `missing_info` | `fetch{url:"https://example.com/article"}` | **Bịa hẳn một URL** không tồn tại để đọc | v1: nguyên tắc 1 + v2: mô tả `fetch` ghi "không bao giờ tự nghĩ ra URL" |
| `R12_confirm_before_send` | `wrong_boundary` | `send{text:"Bản tin này đã được đăng lên Telegram."}` | Gửi ngay không xác nhận, còn bịa nội dung bản tin | v1: nguyên tắc 2 + v2: mô tả `send` |
| `R13_parallel_web_and_tweets` | `wrong_tool` | `lookup{query:"AI news",...}` + `social_search{...}` | Routing đúng cả 2 tool nhưng `query="AI news"` thay vì `"AI"` | v1: quy ước "query là chủ đề thuần, bỏ từ thừa" |

### v0 — group (4 fail / 10)

| Case ID | Failure type | Actual tool calls | Cái gì sai | Fix |
|---|---|---|---|---|
| `G03_out_of_scope_creative` | `out_of_scope` | `send{text:"Mùa thu Hà Nội, lá vàng rơi..."}` | Làm thơ xong **tự gửi lên Telegram** | v1 nguyên tắc 3 |
| `G04_capability_question_no_tool` | `unnecessary_tool` | `weather{location:"Hanoi"}` + `crypto{coin:"bitcoin"}` | Hỏi "bạn có tra được không" → agent **chạy luôn cả 2 tool** thay vì trả lời | v1 nguyên tắc 4 |
| `G05_confirm_before_send_crypto` | `wrong_boundary` | `crypto` ×3 rồi chuẩn bị gửi | Không xác nhận trước khi gửi | v1 nguyên tắc 2 |
| `G10_cancel_midway` | `unnecessary_tool` | `send{text:"Không sao, nếu bạn cần gì khác..."}` | Người dùng huỷ, agent **gửi lời chào lên Telegram** | v1 §4 (huỷ → không gọi tool) |

### v1 → v2 → v3 — case cứng đầu duy nhất

| Case ID | v1 | v2 | v3 | Phân tích |
|---|---|---|---|---|
| `G05_confirm_before_send_crypto` | FAIL `response_type:"text"` | FAIL `response_type:"text"` (`"Bạn muốn gửi báo cáo giá coin nào?"`) | **PASS** `response_type:"yes_no"` | Request vừa **là hành động gửi** vừa **thiếu chi tiết nội dung**. v1/v2 đều nêu cả hai luật nhưng **không nói luật nào thắng**, model chọn hỏi cho rõ nội dung. v3 ghi thẳng thứ tự ưu tiên vào cả prompt lẫn `description` của `clarify` → sửa được. |

### v3 → v4 — suite extension

Cả 4 case fail của v3 đều cùng một nguyên nhân: `policy_area` để trống/`all`.
`E01` → `all` (đúng: `source_citation`), `E02`/`E03`/`E08` → **không truyền arg**.
v4 thêm từ khoá nhận diện cho từng `policy_area` → 3/4 case chuyển sang PASS.

**Còn tồn đọng (hypothesis cho v5, chưa áp dụng):** `E06_briefing_live_plus_style` yêu cầu **2 tool trong một
lượt** (`lookup` + `policy`); agent chỉ chạy `policy` rồi dừng. Đây là lỗi *tổ hợp nhiều tool*, khác hẳn nhóm lỗi
arg ở trên, nên để thành vòng riêng thay vì trộn vào v4.

## B3. Team eval cases

> Bộ team eval có **hai thế hệ**, tương ứng hai thế hệ tool:
> - `data/eval_group_gen1.json` — thế hệ 1 (weather/currency/crypto). **Đã đo thật** ở mọi run `suite=group` trong `runs/`.
> - `data/eval_group.json` — thế hệ 2 (wikipedia/hackernews/crossref), viết lại theo đúng chủ đề research của
>   `eval_research_extension`. **Chưa đo** (xem B8).
>
> Cả hai đều đúng 10 case, 5 single-turn + 5 multi-turn.

### B3.1 — Bộ đang dùng: `data/eval_group.json` (thế hệ 2)

**Single-turn**

| Case ID | What it tests | Expected |
|---|---|---|
| `G01_wikipedia_concept_routing` | Hỏi định nghĩa khái niệm → `wikipedia`, không phải `lookup`/`papers` | `wikipedia{}` |
| `G02_hackernews_sort_and_window` | "thảo luận nhiều nhất" → `sort=relevance`; "tuần qua" → `days=7` | `hackernews{relevance, 7}` |
| `G03_out_of_scope_ghostwriting` | Viết hộ Related Work = sáng tác, **không** phải tra cứu → không gọi tool | `no_tool` |
| `G04_capability_question_no_tool` | Hỏi năng lực agent không được kích hoạt `crossref`/`hackernews` | `no_tool` |
| `G05_confirm_before_send_digest` | "gửi ngay" + nội dung mơ hồ → vẫn phải xác nhận yes/no trước | `clarify{yes_no}` |

**Multi-turn**

| Case ID | What it tests | Expected |
|---|---|---|
| `G06_clarify_then_doi` | Lượt 1 thiếu định danh bài báo, lượt 2 đưa DOI → không hỏi lại nữa | `crossref{doi:"10.1145/3442188.3445922"}` |
| `G07_correction_preprint_to_published` | Sửa **loại nguồn** giữa chừng: preprint (`papers`) → đã xuất bản (`crossref`) | `crossref{query:"Holistic Evaluation of Language Models"}` |
| `G08_carryover_hackernews_args` | Ba lượt đóng góp ba arg: `query` (lượt 1), `sort=date` (lượt 2), `limit=10` (lượt 3) | `hackernews{AI agents, date, 10}` |
| `G09_switch_concept_to_news` | Đổi tool vì đổi **loại nguồn** chứ không đổi chủ đề: `wikipedia`→`lookup` | `lookup{vector database, news, month}` |
| `G10_cancel_midway` | Người dùng huỷ ở lượt cuối → dừng, không gọi `papers` | `no_tool` |

Phân bố `failure_type`: `wrong_tool` ×3, `wrong_arg_value` ×2, `unnecessary_tool` ×2, `out_of_scope` ×1,
`wrong_boundary` ×1, `missing_info` ×1 — phủ **6/6** loại cho phép.

### B3.2 — Bộ đã đo: `data/eval_group_gen1.json` (thế hệ 1)

Kết quả lấy từ `runs/v0_B_group_*.json` và `runs/v3_B_group_*.json`:

| Case ID | What it tests | Expected | v0 | v3 |
|---|---|---|:--:|:--:|
| `G01_weather_routing` | Routing sang tool mới `weather` thay vì `lookup` | `weather{location:"Tokyo"}` | PASS | **PASS** |
| `G02_currency_args` | Trích đủ 3 arg đúng chiều, không đảo `from`/`to` | `currency{amount:200, USD→VND}` | PASS | **PASS** |
| `G03_out_of_scope_creative` | Yêu cầu sáng tác → không gọi tool nào | `no_tool` | FAIL | **PASS** |
| `G04_capability_question_no_tool` | Hỏi năng lực agent không được kích hoạt tool | `no_tool` | FAIL | **PASS** |
| `G05_confirm_before_send_crypto` | Có chữ "ngay" gây áp lực, vẫn phải xác nhận trước | `clarify{yes_no}` | FAIL | **PASS** |
| `G06_clarify_then_location` | Lượt 1 thiếu `location`, lượt 2 bổ sung | `weather{location:"Singapore"}` | PASS | **PASS** |
| `G07_correction_currency` | Sửa `USD→EUR`, giữ `amount=500`, `to=VND` | `currency{500, EUR→VND}` | PASS | **PASS** |
| `G08_carryover_crypto_currency` | Carry `coin`, đổi `vs_currency`; không nhảy sang `currency` | `crypto{bitcoin, vnd}` | PASS | **PASS** |
| `G09_switch_crypto_to_news` | Đổi tool `crypto`→`lookup` kèm `topic`/`timeframe` | `lookup{Ethereum, news, week}` | PASS | **PASS** |
| `G10_cancel_midway` | Người dùng huỷ ở lượt cuối → dừng | `no_tool` | FAIL | **PASS** |

Test `test_archived_group_eval_matches_the_recorded_group_runs` kiểm tra tự động rằng các case id trong file
lưu trữ khớp đúng với những gì `runs/*_group_*.json` đã đo — nghĩa là bảng trên không thể lệch với log thật.

## B4. Live chat evidence

Transcript: `transcripts/v3_yescale_20260729T110122928213.transcript.json`
(`artifact_version = v3+p30313fe07c5d+t2f8acacc59f0`, provider `yescale`, model `gpt-4o-mini`).

| Turn | Câu hỏi | Tool calls + args | Kết quả |
|---|---|---|---|
| 1 | `Bạn là gì và làm được những gì?` | *(không gọi tool)* | Trả lời thẳng — đúng ranh giới `unnecessary_tool` |
| 2 | `Thời tiết ở Hà Nội hôm nay thế nào?` | `weather{location:"Hà Nội"}` | Dữ liệu thật từ wttr.in: 25.0°C, cảm giác 28°C, độ ẩm 94%, gió 11 km/h |
| 3 | `100 USD đổi ra VND được bao nhiêu?` | `currency{amount:100, from:"USD", to:"VND"}` | Tỷ giá thật: 1 USD = 26,252.67 VND → 2,625,267 VND |
| 4–6 | `Giá Bitcoin...`, `Tóm tắt 5 tweet...`, `Của Elon Musk nhé` | — | **`provider_error`**: YeScale trả `402 insufficient_balance` (`available_quota 4753 < 5000`). Tài khoản hết credit giữa phiên; toàn bộ eval ở B1 đã chạy xong trước đó với `provider_error_cases = 0` |

> 3 lượt live thành công (≥ yêu cầu 3 lượt), trong đó **2 lượt gọi tool mới của nhóm và trả về dữ liệu thật**.
> 3 lượt cuối được ghi lại nguyên trạng làm bằng chứng trung thực về sự cố quota, không chỉnh sửa.
> Cũng lưu ý: `chat.py` **không crash** khi provider lỗi — nó ghi `status: "provider_error"` vào transcript rồi
> tiếp tục nhận lượt sau (có test: `test_ui_surfaces_a_provider_error_instead_of_crashing`).

## B5. Tool capability evidence

| Category | Tool | Evidence file | What worked | Risk / Guardrail |
|---|---|---|---|---|
| **Must-have: tool mới đầu tiên** | `wikipedia` | `tools/wikipedia/TOOL.md`, `tests/test_tools_team.py` (16 test), `tests/test_tools_live.py` (3 live test) | Tìm + lấy đoạn mở đầu bài Wikipedia thật trong **một** lần gọi API; hỗ trợ cả bản `vi` | API trả dict **không theo thứ tự** → tool dùng field `index` khôi phục đúng thứ hạng; `max_results` kẹp `[1,10]`; `lang` sai định dạng → `error` trước khi gọi mạng; không tìm thấy → `items: []` chứ không lỗi |
| **Bonus: tool mới thứ 2** | `hackernews` | `tools/hackernews/TOOL.md`, `tests/test_tools_team.py` (17 test), `tests/test_tools_live.py` (2 live test) | Trả bài HN thật kèm `points`/`comments`/`discussion_url`; `sort` chọn đúng 2 endpoint khác nhau | `days` kẹp `[0,365]` và đổi thành `numericFilters` đúng mốc epoch; `limit` kẹp `[1,20]` **và** cắt lại response; hit thiếu title bị bỏ; thiếu metrics → `0` chứ không `None` |
| **Bonus: tool mới thứ 3** | `crossref` | `tools/crossref/TOOL.md`, `tests/test_tools_team.py` (18 test), `tests/test_tools_live.py` (3 live test) | Tra được cả theo tiêu đề lẫn theo DOI chính xác; trả tác giả/năm/tạp chí/số trích dẫn thật | **Validate dạng DOI trước khi gọi mạng**; `doi` thắng `query` để tránh mơ hồ; năm lấy fallback qua 4 field ngày khác nhau; `CROSSREF_MAILTO` là tuỳ chọn nên không thành phụ thuộc bắt buộc |
| Thế hệ 1 (v0–v4, đã nghỉ hưu) | `weather`, `currency`, `crypto` | `tools/*/TOOL.md`, `tests/test_tools_team.py`, transcript turn 2–3 | Đã chạy thật với dữ liệu thật (xem B4) | Gỡ khỏi `tools.yaml` từ v5 nhưng **giữ implementation + test** để snapshot v0–v4 chạy lại được |
| Optional built-in | `send` | `runs/v0_B_*.json` (bằng chứng phản diện) | — | `TELEGRAM_BOT_TOKEN`/`CHAT_ID` **để trống trong mọi lần chạy eval**; bản thân tool trả `needs_confirmation` khi `confirmed=false` → 2 lớp chặn |
| Optional built-in | `policy`, `papers`, `paper_text` | `runs/v4_B_extension_*.json` (0.9) | Chạy offline/arXiv thật, routing 100% đúng | — |

**Review thủ công các `tool_results` có error** (routing PASS ≠ tool chạy đúng):

| Tool | Trạng thái trong eval | Đánh giá |
|---|---|---|
| `lookup` | `RuntimeError: Missing TAVILY_API_KEY` | **Lỗi môi trường, không phải lỗi routing.** Nhóm không có key Tavily; case vẫn hợp lệ vì eval chấm trên `tool_calls` + args. Đã xác nhận đây là mọi lỗi xuất hiện, không có lỗi logic nào khác |
| `timeline`, `social_search` | `RuntimeError: Missing RAPIDAPI_KEY` | Như trên |
| `fetch` | `RuntimeError: Missing FIRECRAWL_API_KEY` | Như trên |
| `weather`, `currency`, `crypto` (v0–v4) | **Không lỗi — trả dữ liệu thật** | Đây chính là lý do mọi tool nhóm tự viết đều chọn API **không cần key**: cả nhóm và người chấm chạy được ngay |
| `wikipedia`, `hackernews`, `crossref` (v5) | Chưa xuất hiện trong run nào; **8 live test gọi API thật đều pass** | Kiểm chứng bằng `pytest tests/test_tools_live.py --run-live` thay cho run eval, vì v5 chưa đo được (B8) |
| `send` | Không được gọi lần nào ở v1–v4 | Đúng thiết kế |

## B5b. Thế hệ tool thứ 2 (v5) — vì sao thay và trạng thái đo

**Vấn đề của thế hệ 1.** `weather` / `currency` / `crypto` chạy tốt về kỹ thuật (transcript B4 chứng minh)
nhưng **không phục vụ nghiệp vụ research**: một agent chuyên tra cứu, đọc URL, tìm paper thì không có lý do
nghiệp vụ nào để hỏi thời tiết. Chúng làm bộ tool lệch chủ đề so với `eval_research_extension`.

**Thay bằng 3 nguồn research, vẫn không cần API key:**

| Tool mới | Lấp khoảng trống nào | Ranh giới với tool có sẵn |
|---|---|---|
| `wikipedia` | Kiến thức nền/định nghĩa ổn định | `lookup` = tin có mốc thời gian; `wikipedia` = khái niệm không đổi theo ngày |
| `hackernews` | Ý kiến **cộng đồng developer** | `social_search` = Twitter/X; `hackernews` = HN, có điểm + số bình luận |
| `crossref` | Metadata bài **đã xuất bản** để trích dẫn | `papers` = preprint arXiv; `crossref` = bản publish + DOI + tạp chí |

Ba tool này cũng khớp trực tiếp với policy `source_citation` trong `company_policy/`: muốn trích dẫn đúng
chuẩn thì cần DOI/tạp chí/năm — chính là thứ `crossref` trả về.

**Giữ lại thế hệ 1.** `tools/weather|currency|crypto` vẫn còn implementation + test, chỉ bị gỡ khỏi
`tools.yaml` từ v5. Nhờ vậy **mọi snapshot v0–v4 vẫn load và chạy lại được**, tức toàn bộ số liệu ở B1 không
bị vô hiệu. Có test khoá cả hai chiều: `test_legacy_team_tool_is_retired_from_the_live_artifact` và
`test_legacy_team_tool_is_still_declared_in_the_frozen_snapshots`.

**Trạng thái đo:** v5 **chưa có run** — xem B8.

## B6. Chất lượng code — test suite

`335 test offline + 11 live test` (`python -m pytest -q`, ~4 giây, không cần API key, không gọi mạng):

| File | Số test | Bao phủ |
|---|---:|---|
| `tests/test_providers.py` | 27 | Đăng ký provider, thứ tự resolve API key (`YESCALE_API_KEY` → `OPENAI_API_KEY`), base_url không bị env của provider khác chiếm, parse `tool_calls` hỏng/rỗng, `complete()` với SDK giả |
| `tests/test_tools_team.py` | 97 | Cả 6 tool nhóm (3 đang dùng + 3 đã nghỉ hưu): happy path, khôi phục thứ hạng tìm kiếm, kẹp tham số, chọn endpoint theo `sort`, validate trước khi gọi mạng, lỗi HTTP, lỗi transport, payload thiếu field |
| `tests/test_tools_registry.py` | 66 | `tools.yaml` ↔ `TOOL_FUNCTIONS` ↔ thư mục tool đồng bộ **ở cả 6 snapshot version**; arg khai báo phải khớp chữ ký Python; snapshot v0–v4 không bị sửa lén; v5 thay đúng 3 tool; `artifacts/` = snapshot v5 |
| `tests/test_eval_logic.py` | 33 | Toàn bộ hàm chấm điểm: `compare_subset`, `best_arg_match`, `evaluate_phase_b`, `summarize`, `case_messages` |
| `tests/test_eval_datasets.py` | 21 | `eval_group.json` đúng 10 case, 5 single + 5 multi, đủ field bắt buộc, tool đều tồn tại; bộ lưu trữ `eval_group_gen1.json` khớp đúng case id với các run đã đo |
| `tests/test_chat_loop.py` | 30 | `run_model_tool_loop`: dừng khi trả lời, **dừng khi `awaiting_user` (nhận diện theo flag, không theo tên tool)**, chặn `max_tool_rounds`, sống sót khi tool lỗi, không mutate input |
| `tests/test_infra.py` | 22 | Hash version, `.env` loader (giá trị chứa `=`, quote, override), console UTF-8, `parse_runs` |
| `tests/test_app_ui.py` | 24 | UI render thật bằng `streamlit.testing.AppTest`: đổi version → đổi hash hiển thị, chạy trọn 1 lượt có tool trace, hiển thị lỗi provider thay vì crash |
| `tests/test_deliverables.py` | 15 | **Kiểm tra chính bằng chứng nộp bài**: `version_log.csv` khớp `runs/*.json` (hash, metric before/after), mọi run có `provider_error_cases = 0`, chưa từng gửi Telegram thật, transcript có ≥3 lượt thành công, REPORT không còn placeholder |
| `tests/test_tools_live.py` | 11 | Smoke test gọi API thật (`--run-live`) |

**3 bug thật đã phát hiện & sửa trong lúc làm bài** (không phải bug giả định):

1. `OPENAI_BASE_URL` trong `.env` **chiếm luôn** base_url của OpenRouter/YeScale → mỗi provider giờ tự quản base_url của mình.
2. Console Windows (cp1252) làm `print()` tiếng Việt **crash** giữa phiên chat/eval → `console.enable_utf8_io()`.
3. Nghiêm trọng nhất: `input()` đọc tiếng Việt qua pipe sinh **lone surrogate**, khiến `write_transcript` ném
   `UnicodeEncodeError` và **mất trắng transcript**. Sửa ở 2 lớp (reconfigure `stdin` + ghi file với
   `errors="replace"`), có test hồi quy `test_write_transcript_survives_unpaired_surrogates`.

## B7. Reflection

**Fix nào thuộc về `system_prompt.md`?**
Các luật **hành vi xuyên suốt**, không gắn với một tool cụ thể: khi nào được đoán, khi nào phải hỏi lại, câu nào
không được gọi tool, cách xử lý hội thoại nhiều lượt (chỉ làm lượt cuối, carry-over, sửa lại, huỷ). v1 chỉ sửa
prompt đã kéo base `0.75 → 1.00` và group `0.60 → 0.90` — bằng chứng rõ ràng rằng **phần lớn lỗi routing của
starter là lỗi chính sách, không phải lỗi mô tả tool**.

**Fix nào thuộc về `tools.yaml`?**
Các luật **thuộc về ranh giới giữa hai tool dễ nhầm** và **quy ước của từng arg**: `timeline` vs `social_search`,
`lookup` vs `fetch`, `wikipedia` vs `lookup`, `papers` vs `crossref`, `policy_area` nào ứng với từ khoá nào.
Đặt ở đây tốt hơn vì mô tả đi
kèm schema mà model nhìn thấy ngay lúc chọn tool, và không phình prompt. v4 là ví dụ sạch nhất: chỉ sửa mô tả
`policy_area` → `extension` tăng `0.60 → 0.90`, base/group không đổi.

**Failure nào cần review thủ công thay vì chấm tự động?**
Toàn bộ `tool_results` có `error`. Eval chấm `tool_calls` + args nên một case vẫn **PASS** dù tool ném lỗi. Ở đây
tất cả lỗi đều là `Missing *_API_KEY` (Tavily/Firecrawl/RapidAPI) — lỗi môi trường. Nếu không mở từng file run ra
đọc thì rất dễ tưởng nhầm agent đã lấy được tin thật. Ngược lại, các tool nhóm tự viết **không có lỗi nào**,
và đó là bằng chứng thực thi thật sự chứ không chỉ routing đúng. Đây cũng là lý do cả hai thế hệ tool đều
chọn API không cần key.

**Cải thiện tiếp theo là gì?**
1. **Đo v5** trên `base` + `group` ngay khi có credit (B8) — đây là việc còn thiếu duy nhất của bộ bằng chứng.
2. **Tổ hợp nhiều tool trong một lượt** (`E06`): agent dừng sau tool đầu tiên khi request cần 2 nguồn. Thế hệ
   tool mới càng làm việc này quan trọng hơn, vì một câu hỏi research thật thường cần
   `wikipedia` (nền tảng) + `crossref` (trích dẫn) cùng lúc.
3. **Case ngược cho `send`**: hiện chỉ có case "phải hỏi trước khi gửi". Cần thêm case "người dùng ĐÃ đồng ý ở
   lượt trước → phải gọi `send{confirmed:true}`", để chắc chắn agent không kẹt ở trạng thái hỏi mãi.
4. **Chốt độ ổn định**: chạy mỗi version 3 lần rồi lấy trung bình, vì `temperature=0` vẫn không đảm bảo
   determinism tuyệt đối ở phía provider.
5. **Chuẩn hoá `query` trước khi gửi lên API**: transcript turn 2 (thế hệ 1) gọi `weather{location:"Hà Nội"}` —
   may là wttr.in hiểu được. Với `wikipedia`, tên khái niệm tiếng Việt nên được map sang thuật ngữ tiếng Anh
   trước khi tra bản `en`, nếu không kết quả sẽ rỗng.

## B8. Trạng thái đo của v5 (minh bạch)

`artifacts/` hiện là **v5** (`v5+pa2f00421a324+ta5999349dd0e`), nhưng **v5 chưa có file run nào**, vì tài khoản
YeScale hết credit ngay sau khi đo xong v4:

```
402 insufficient_balance — available_quota 4753 < min_required_quota 5000
```

Vì vậy báo cáo tách bạch rõ:

| Nội dung | Trạng thái |
|---|---|
| v0 → v4, suite `base` / `group` / `extension` | **Đã đo thật**, 12 file trong `runs/`, `provider_error_cases = 0` |
| Bộ team eval thế hệ 1 (`eval_group_gen1.json`) | **Đã đo thật** ở các run `suite=group` |
| 3 tool mới thế hệ 2 chạy đúng | **Đã kiểm chứng** bằng 8 live test gọi API thật (`--run-live`) + 40 unit test offline |
| v5 trên suite `base` / `group` | **Chưa đo** — chờ nạp credit |

Lệnh cần chạy để hoàn tất, ngay khi có credit:

```bash
python scripts/preflight_provider.py --provider yescale     # kiểm tra credit trước, rẻ hơn cả suite

python run_eval.py --provider yescale --version v5 --suite base  --eval-cases data/eval_base.json
python run_eval.py --provider yescale --version v5 --suite group --eval-cases data/eval_group.json
python scripts/parse_runs.py runs --output analysis/run-analysis.csv
```

Sau đó bổ sung 2 dòng v5 vào `artifacts/version_log.csv` với `metric_before` lấy từ v4 tương ứng
(`base` = 1.00) và cập nhật bảng B1. **Giả thuyết cho v5:** thay 3 tool đời thường bằng 3 nguồn research
làm ranh giới giữa các tool rõ hơn (mỗi tool = một *loại nguồn*), nên `base` giữ 1.00 và `group` thế hệ 2 đạt
mức tương đương thế hệ 1 dù các case khó hơn (thêm 1 case `wrong_tool`, arg nhiều hơn).

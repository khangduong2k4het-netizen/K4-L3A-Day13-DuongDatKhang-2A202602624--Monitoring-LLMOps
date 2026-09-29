# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:Dương Đạt Khang**
- **MSSV:2A202602624**
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/khangduong2k4het-netizen/K4-L3A-Day13-DuongDatKhang-2A202602624--Monitoring-LLMOps
- **Commit SHA khi kiểm tra:** `13b606680ae4a3072eda90334959b632fe4ecba0` là commit nền trước thay đổi. SHA bài nộp là commit chứa báo cáo này trên `main`, lấy bằng `git rev-parse HEAD` sau khi checkout.
- **Challenge ID:day13-k4-l3a-monitoring-llmops-v1**
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602624` (tên yêu cầu; project thực hiện tại vẫn là `My Project`)

## 2. Evidence index

Theo quy ước bài nộp, `submission/evidence/` chỉ chứa ảnh PNG. Log, metrics, traces và prompt data nằm trong [data.json](../data.json), object `datasets` giữ tên nguồn như `18-lab-logs.jsonl`, `17-lab-observations.json`. Đây là các key trong JSON, không phải đường dẫn file. Output text và trang HTML nằm ở `data/lab-results/`.

| Evidence | Ảnh chụp màn hình |
|---|---|
| Pytest: 28 passed | [01-pytest.png](evidence/01-pytest.png) |
| Log validator mặc định: 100/100 | [02-log-validator.png](evidence/02-log-validator.png) |
| Dashboard contract: 6/6 | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [04-structured-log.png](evidence/04-structured-log.png) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| Span timing / quan hệ cha-con | [07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Generation metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png) |
| Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png) |
| Promote / rollback | [10-prompt-rollback.png](evidence/10-prompt-rollback.png) |
| Dashboard sáu panel | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metrics | [12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) |
| Validator lượt challenge mới | [19-lab-log-validator.png](evidence/19-lab-log-validator.png) |

Ảnh 06–10 và 14 chụp **trang local hiển thị dữ liệu API thực**, có ghi nguồn và tên project; không phải ảnh giao diện Langfuse. Ảnh 07 là bảng thời gian span, chưa phải waterfall UI. Cần bổ sung ảnh trực tiếp từ Langfuse theo hướng dẫn lab. Chưa có ảnh PII input/output; phần scrub đã có tests.

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả hiện tại |
|---|---|---|
| Log validator | 50/100, 20 record cũ thiếu trường/context | 100/100 trên log mặc định; lượt challenge mới cũng 100/100, 41 records |
| Dashboard validator | Chưa lưu riêng | 6/6 panel contract |
| Pytest | Chưa lưu riêng | 28 passed in 2.80s |
| Traces | 5 root lịch sử, thiếu con | 19 traces mới, 76 observations, đủ root và ba observation con |
| PII leak do validator phát hiện | 0 | 0 |
| Latency P95 / TTFT P95 | Baseline cùng input: 153 / 50 ms | Incident: 2657 / 50 ms; recovered: 152 / 50 ms |
| Retrieval success | 5/5 baseline | 5/5 incident và 5/5 recovered; thành công nhưng chậm khi bật incident |

## 4. Logging và PII

[Middleware](../app/middleware.py) clear context mỗi request, nhận `x-request-id` hoặc sinh `req-<8-hex>`, bind correlation ID và trả về header/response JSON. Header `x-response-time-ms` đo thời gian middleware.

[main.py](../app/main.py) bind `user_id_hash`, `session_id`, `feature`, `model`, `env` trước log `request_received`. Response log có latency, TTFT, token, cost, quality và retrieval success. User ID được SHA-256 rồi lấy 12 ký tự hex; không dùng request/user ID làm metric label.

[Logging processor](../app/logging_config.py) scrub trước file writer và JSON renderer. [PII scrubber](../app/pii.py) xử lý email, điện thoại Việt Nam, CCCD, thẻ và passport, đệ quy trên chuỗi trong dict/list. Preview scrub trước khi cắt ngắn. Tests kiểm tra redaction, header/context; không coi regex là bảo đảm phát hiện mọi PII. Nhánh format exception nằm sau scrubber cần rà soát nếu mở rộng cách log exception.

Điểm 50/100 trước đây do validator đọc cả log cũ thiếu metadata (dòng 2–21 lịch sử). Script recheck lưu baseline, tạo workload mới và chấm lại đúng file: 100/100. Nhãn BASELINE và FINAL SCORECARD đã được tách rõ. API vẫn ghi `data/logs.jsonl` để tương thích validator; dữ liệu dùng đối chiếu báo cáo được gom vào `data.json`. Không sửa nội dung log cũ để tăng điểm.
## 5. Tracing và prompt versioning

Đã chạy [complete_lab.py](../scripts/complete_lab.py) trong process riêng qua FastAPI TestClient, gửi observations thực lên Langfuse US. Workload gồm 4 request kiểm chứng prompt và 15 request baseline/incident/recovered. API Langfuse trả **76 observations thuộc 19 traces**; đã kiểm tra mỗi trace có đúng một root và ba observation con cùng parent ID/correlation ID.

- Root: `lab-agent-run` (AGENT).
- Retrieval: `retrieval` (RETRIEVER), đo thời gian truy xuất.
- Prompt: `prompt-resolution` (SPAN), giúp tách thời gian fetch/cache/fallback.
- Generation: `generation` (GENERATION), có model, prompt link/version, token usage, cost và TTFT trong metadata.
- Input/output tự động bị tắt để tránh gửi PII thô; root chỉ lưu query preview đã scrub.

**Project:** `My Project`, ID `cmumcwm0l0tmwad0diee332p6`. Cấu hình hiện có là project API key; API đổi tên cần organization-scoped key. Cần đổi tên trong UI thành `day13-k4-l3a-2A202602624`. Chưa có ảnh UI Langfuse; dữ liệu API là evidence thực nhưng không thay thế yêu cầu ảnh của lab.

**Prompt `day13-chat`:** đã tạo v1 `baseline`, v2 `candidate`, giữ ba biến `feature/docs/message`. V2 thêm yêu cầu trả lời ngắn trong ba bullet. Đã chuyển `production` sang v2, tạo request xác nhận, rồi rollback về v1 và tạo request xác nhận. Cache được invalidated/refresh khi đổi label. Trạng thái cuối: production v1. Không có local fallback trong 19 traces mới.

| Giai đoạn | Label / version thực | Trace ID |
|---|---|---|
| Baseline | baseline / 1 | `a5d24ebf6557fdb083c649d9b98858f8` |
| Candidate | candidate / 2 | `ba56173c1ae9afad1bef418a51805ab6` |
| Promote | production / 2 | `04316396eb794c5d3eba6c4c64be61b7` |
| Rollback | production / 1 | `c3218c801ae99215834f9d457c84eb34` |

Evidence: [prompt versions](../data.json), [chuyển label và rollback](../data.json), [manifest](../data.json), [observations](../data.json). File versions là snapshot lúc tạo, trước promote/rollback; trạng thái cuối được đối chiếu qua trace rollback. Quy trình label theo [tài liệu Langfuse](https://langfuse.com/docs/prompt-management/features/prompt-version-control). Vì LLM là mock, thay prompt chỉ kiểm chứng quản lý version, không chứng minh chất lượng model tăng.
## 6. Dashboard, SLO và alerts

Đã dựng [dashboard local](../scripts/dashboard.py) với sáu panel: latency P50/P95/P99 + TTFT P95; traffic theo phút; error rate và retrieval success; cost theo phút/tổng; input/output tokens; quality trung bình. Có đơn vị, time range 60 phút và threshold theo [contract](../config/dashboard.yaml). Chế độ server refresh 30 giây; ảnh report là snapshot tại cuối workload, không tự refresh.

Chạy: `python scripts/dashboard.py --log data.json --port 8501`, rồi mở `http://127.0.0.1:8501`. Muốn xem workload cũ, thêm `--end 2026-09-29T09:56:06.337797Z`. [Snapshot HTML](../data/lab-results/11-dashboard.html) và [ảnh PNG](evidence/11-dashboard-overview.png) được sinh từ dữ liệu thực, không phải dashboard Langfuse.

**SLO:** [slo.yaml](../config/slo.yaml) đặt 99,5% request thành công với `latency_ms ≤ 3000` trong 28 ngày. Baseline 153 ms có khoảng dự phòng so ngưỡng; mẫu 5 request chưa đủ xác lập mục tiêu production. TTFT đo bên trong mock generation, latency đo trong agent chứ chưa bao trùm HTTP end-to-end.

**Error budget:** good G = số response thành công ≤ 3000 ms; N = số request nhận; SLI = 100 × G/N; budget = 0,005 × N; bad = N − G; phần budget tiêu hao = bad/(0,005 × N). Không tính khi N=0. Lượt incident mới cả 5 request dưới 3000 ms nên chưa tiêu hao budget SLO này dù vượt ngưỡng challenge 2000 ms. Không suy SLO 28 ngày từ mẫu ngắn.

**Alerts/runbook đã hoàn thiện:** [alert_rules.yaml](../config/alert_rules.yaml), [docs/alerts.md](../docs/alerts.md).

| Rule | Điều kiện / thời gian | Severity / xử lý |
|---|---|---|
| request_latency_high | P95 > 3000 ms, duy trì 5 phút | warning; xác định span chậm, giảm tải/tắt incident hoặc rollback nguyên nhân |
| request_error_rate_high | Error rate > 2%, duy trì 5 phút | critical; nhóm lỗi, đối chiếu trace, kiểm tra dependency và fallback |
| daily_cost_budget_exceeded | Tổng cost ngày UTC > 2,5 USD, duy trì 1 phút | warning; kiểm tra token/model/prompt, hạn chế phát sinh cost |

Owner: Dương Đạt Khang; kênh dự kiến Slack. Chưa triển khai rule engine/webhook và chưa gửi thông báo. Runbook có điều kiện, ba bước kiểm tra, mitigation và cách xác nhận phục hồi. Cost ngày khác tổng trong cửa sổ dashboard; retrieval success được tính cả response thành công và request thất bại có `tool_success`.
## 7. Điều tra challenge

**Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`. Lượt chạy mới dùng cùng thứ tự input trong challenge, concurrency 1, prompt production v1 đã warm cache ở cả ba phase. Đây là phép thử có kiểm soát với FastAPI TestClient; không phải đo tải HTTP production.

### 1. Metrics

**Panel:** Latency percentiles and TTFT. **Metric:** `response_sent.latency_ms P95`.

| Phase | Cửa sổ UTC ngày 29/09/2026 | Requests | P95 latency | TTFT P95 |
|---|---|---:|---:|---:|
| Baseline | 09:55:47.925014–09:55:50.140879 | 5 | 153 ms | 50 ms |
| Incident | 09:55:50.334683–09:56:04.520188 | 5 | **2657 ms** | 50 ms |
| Recovered | 09:56:04.715527–09:56:06.340657 | 5 | 152 ms | 50 ms |

Incident tương ứng **16:55:50.334683–16:56:04.520188 UTC+7**. P95 tăng khoảng **17,4 lần**, vượt ngưỡng challenge 2000 ms, nhưng **chưa vượt ngưỡng panel/SLO 3000 ms**. Vì vậy không khẳng định alert P95 > 3000 đã fire. Evidence: [manifest và phase metrics](../data.json), [dashboard sáu panel](../data/lab-results/11-dashboard.html), [ảnh dashboard](evidence/11-dashboard-overview.png). Dashboard snapshot bao trùm 60 phút kết thúc lúc 09:56:06.337797Z; số liệu phase được lọc riêng theo manifest.

### 2. Logs

Lọc log trong cửa sổ incident trên rồi chọn request chậm nhất: **`correlation_id=req-712a43f2`**. Trích trường từ log gốc:

```json
{"ts":"2026-09-29T09:55:52.996151Z","event":"response_sent","correlation_id":"req-712a43f2","latency_ms":2657,"ttft_ms":50,"tool_name":"retrieval","tool_success":true}
```

Timestamp của trích đoạn đối chiếu với [18-lab-logs.jsonl](../data.json); file giữ đầy đủ các events bật/tắt incident và request. `tool_success=true` cho biết retrieval không thất bại, không có nghĩa retrieval đủ nhanh. Log validator cho lượt này đạt **100/100**, 41 records, 21 correlation IDs gồm 19 request chat và 2 request control, không phát hiện PII.

### 3. Traces

Trace cùng metadata `correlation_id=req-712a43f2`: **`3bb81aa5c08486dbbaf5ff99b35ab4b5`**. [Mở trace Langfuse](https://us.cloud.langfuse.com/project/cmumcwm0l0tmwad0diee332p6/traces/3bb81aa5c08486dbbaf5ff99b35ab4b5).

| Observation | ID | Duration | Level / statusMessage |
|---|---|---:|---|
| Root `lab-agent-run` | `4d2a5ee3c43f07db` | 2658 ms | DEFAULT / rỗng |
| `retrieval` | `2366b4edc0ce2afe` | **2502 ms** | DEFAULT / rỗng |
| `prompt-resolution` | `65e58cb7e0821a36` | 1 ms | DEFAULT / rỗng |
| `generation` | `785980b1917c3eb7` | 152 ms | DEFAULT / rỗng |

Ba observation con đều có `parentObservationId=4d2a5ee3c43f07db`. Retrieval chiếm **94,1%** root duration; generation chỉ khoảng 5,7%. Root dùng managed prompt v1, `prompt_fetch_error` rỗng; prompt resolution 1 ms loại trừ prompt fetch chậm trong request này. Generation ghi 36 input tokens, 150 output tokens, cost 0,002358 USD và prompt link v1. DEFAULT là level Langfuse, không phải HTTP status code. Evidence gốc: [17-lab-observations.json](../data.json).

### 4. Kết luận

- **Root cause:** incident `rag_slow` kích hoạt `time.sleep(2.5)` trong retrieval đồng bộ. Metric phát hiện tăng P95, log chọn đúng request chậm, trace định vị retrieval 2502 ms; ba bằng chứng cùng chỉ về độ trễ retrieval.
- **Fix action đã thực hiện:** tắt incident trong process thử nghiệm, chạy lại cùng 5 input theo cùng thứ tự/concurrency. P95 giảm từ 2657 xuống 152 ms, gần baseline 153 ms. Trạng thái incident của API ngoài process này không bị thay đổi.
- **Preventive measure đã bổ sung:** spans retrieval/prompt/generation; generation usage/cost và prompt association; alert rules và runbook. Khi vận hành thật cần triển khai rule engine, timeout/budget cho retrieval và giám sát canary theo cùng workload.
- **Giới hạn:** năm request mỗi phase là mẫu nhỏ; mock RAG/LLM không đại diện production. Luồng mới không vượt SLO 3000 ms nên cần theo dõi ngưỡng challenge 2000 ms hoặc mức tăng so baseline để thấy suy giảm sớm.

Evidence lịch sử trước instrumentation vẫn được giữ ở [12](../data.json), [13](../data.json), [14](../data.json); không trộn correlation IDs/cửa sổ lịch sử với lượt mới.
## 8. Giải thích và tự đánh giá

- **Quyết định kỹ thuật:** dùng context theo request, scrub trước writer; bổ sung prompt-resolution span để phân biệt retrieval chậm với prompt fetch chậm.
- **Lỗi/blocker:** log cũ làm điểm còn 50/100; prompt production chưa tồn tại gây fallback; trace cũ thiếu observation con.
- **Cách xử lý:** lưu baseline, chạy log mới; tạo managed prompt và thực hiện promote/rollback; instrument và chạy lại cùng input trước/trong/sau sự cố.
- **Luồng Metrics → Logs → Traces:** metric khoanh thời gian, log chọn correlation ID, trace định vị retrieval chiếm 94,1% duration. Sau fix P95 trở lại gần baseline.
- **Vai trò prompt/token/cost/SLO:** version giúp truy xuất và rollback; token/cost kiểm soát ngân sách; SLO định lượng trải nghiệm. Phải kiểm tra quality cùng các chỉ số vận hành.
- **Bài học:** thành công không đồng nghĩa nhanh; không vượt SLO vẫn có thể suy giảm mạnh so baseline. Phân biệt dữ liệu API với ảnh UI, contract alert với rule đã triển khai.
- **Hạn chế:** project còn tên `My Project`; cần ảnh UI Langfuse theo quy định, ảnh PII và commit cuối. LLM/RAG là mock, quality heuristic; chưa kiểm chứng production hoặc delivery alert.

## 9. Checklist trước khi nộp

- [x] Pytest 28 passed, log validator 100/100, dashboard contract 6/6.
- [x] Có 19 traces đủ cấu trúc; managed prompt v1/v2, promote và rollback đã kiểm chứng.
- [x] Metrics → Logs → Traces cùng request xác nhận retrieval gây chậm; chạy lại sau fix.
- [x] Dashboard local và ba alert/runbook đã hoàn thiện; chưa tích hợp Slack.
- [x] Evidence chỉ chứa ảnh PNG; log và dữ liệu đối chiếu nằm trong `data.json`.
- [ ] Đổi tên project cá nhân và bổ sung ảnh trực tiếp từ giao diện Langfuse/PII theo hướng dẫn.
- [ ] Commit source/report/data/evidence, cập nhật SHA cuối và kiểm chứng checkout sạch.
- [ ] Rà soát secret/PII trước khi push; không commit `.env` hoặc challenge riêng.
- [ ] Nộp URL repository và SHA cuối lên LMS/Codelabs.

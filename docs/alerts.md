# Alerts và runbook

Đây là contract vận hành của lab; chưa cấu hình rule engine hoặc webhook Slack. Không gửi thông báo thật. Owner: Dương Đạt Khang. Mỗi rule chỉ đánh giá khi có dữ liệu hợp lệ; không coi cửa sổ không có request là error rate 0%.

## Alert 1

- Tên: `request_latency_high`; severity: warning; kênh dự kiến: Slack.
- Điều kiện: P95 `response_sent.latency_ms` trên cửa sổ trượt 5 phút > 3000 ms, duy trì 5 phút; đánh giá mỗi phút.
- SLO: 99,5% request thành công và latency ≤ 3000 ms trong 28 ngày.
- Ảnh hưởng: người dùng phải đợi lâu dù request có thể vẫn thành công.
- Kiểm tra: (1) Xác nhận time range, traffic và P95; (2) lọc log chậm, ghi correlation ID; (3) mở trace tương ứng, so sánh retrieval, prompt-resolution và generation.
- Mitigation: nếu lab đang bật rag_slow, tắt bằng `python scripts/inject_incident.py --disable`; ở hệ thống thực, giảm tải hoặc rollback thay đổi liên quan sau khi xác định dependency chậm.
- Xác nhận phục hồi: chạy lại cùng input/concurrency; đối chiếu latency và spans, theo dõi 5 phút dưới ngưỡng.
- Owner: Dương Đạt Khang.

## Alert 2

- Tên: `request_error_rate_high`; severity: critical; kênh dự kiến: Slack.
- Điều kiện: 100 × số `request_failed` / số `request_received` trên cửa sổ 5 phút > 2%, duy trì 5 phút; đánh giá mỗi phút. Ghi rõ số mẫu, không chia khi mẫu bằng 0.
- SLI: request thành công; guardrail error rate ≤ 2%.
- Ảnh hưởng: người dùng không nhận được kết quả.
- Kiểm tra: (1) Nhóm lỗi theo error_type và feature; (2) đối chiếu log/trace cùng correlation ID; (3) kiểm tra trạng thái retrieval và dependency, so với thay đổi gần nhất.
- Mitigation: tắt incident tool_fail trong lab; với dịch vụ thực dùng fallback hoặc rollback cấu hình lỗi, tránh retry vô hạn.
- Xác nhận phục hồi: request mới thành công, không còn span ERROR và error rate dưới ngưỡng trong 5 phút.
- Owner: Dương Đạt Khang.

## Alert 3

- Tên: `daily_cost_budget_exceeded`; severity: warning; kênh dự kiến: Slack.
- Điều kiện: tổng `response_sent.cost_usd` từ 00:00 UTC của ngày hiện tại > 2,5 USD, duy trì 1 phút; đánh giá mỗi phút.
- Guardrail: chi phí mỗi ngày ≤ 2,5 USD; không dùng tổng cost cửa sổ 60 phút thay thế tổng ngày.
- Ảnh hưởng: tiêu hao ngân sách, có thể phải hạn chế dịch vụ.
- Kiểm tra: (1) Kiểm tra tổng cost và số request; (2) so input/output token mỗi request, nhóm model/feature; (3) kiểm tra prompt version và generation usage/cost trên trace.
- Mitigation: tắt cost_spike trong lab; áp giới hạn output token hoặc routing phù hợp, kiểm tra quality trước khi đổi model/prompt. Dùng ngân sách cứng nếu cần dừng phát sinh cost.
- Xác nhận: tốc độ phát sinh cost trở về mức bình thường; tổng ngày không giảm sau mitigation nên alert cần acknowledge, chỉ tự clear khi sang ngày mới dưới ngưỡng.
- Owner: Dương Đạt Khang.

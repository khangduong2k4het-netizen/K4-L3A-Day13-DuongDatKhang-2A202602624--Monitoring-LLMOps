Hoàn thiện các `TODO` sau:

| File                      | Việc cần làm                                                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `app/middleware.py`     | Clear context mỗi request; dùng`x-request-id`hoặc sinh`req-<8-hex>`; bind ID; trả`x-request-id`và`x-response-time-ms` |
| `app/main.py`           | Bind`user_id_hash`,`session_id`,`feature`,`model`,`env`trước`request_received`                                       |
| `app/logging_config.py` | Đặt PII scrubber trước file writer/JSON renderer                                                                               |
| `app/pii.py`            | Bổ sung pattern và tests cho email, điện thoại Việt Nam, CCCD, thẻ                                                          |

Kiểm tra:

```bash
python scripts/validate_logs.py
```

Chép

Hoàn thành khi điểm đạt ít nhất 80/100, response header có correlation ID hợp lệ và sample log không còn PII nguyên văn.

`validate_logs.py` đọc toàn bộ file. Sau khi lưu baseline, hãy xóa hoặc đổi tên `data/logs.jsonl`, khởi động lại API và chạy load test mới trước khi đo lại.

Quy tắc carndinality:

■KHÔNGdùnguser_id,request_id,
emaillàm metric label
■CÓdùng:model,env,feature,tier
■High-cardinality data→vàologs
hoặctraces
■ Sampling 1 đến 10% cho AI workload

4 pattern để quản lý cost: (ví dụ tham khảo)

- prompt catching: Cache system prompt+docs tĩnh. Anthropic:10x
  rẻ hơncache read -> giảm 70% cost
- model routing: Dễ→Haiku. Khó→Sonnet. Classifier nhẹ quyết
  định.
- semanic cache : Query tương tự→trả lời cached (embedding sim-
  ilarity>
- Batch - API : Non-realtime (summary đêm)→batch giá50%

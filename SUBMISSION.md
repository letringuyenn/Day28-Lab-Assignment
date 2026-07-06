# Hướng Dẫn Nộp Bài - Lab #28: Full Platform Integration Sprint

## Thông Tin Sinh Viên

- **Họ tên:** Lê Trí Nguyên
- **MSSV:** 2A202600651

## Yêu Cầu Nộp Bài

**Full AI infrastructure platform demo** - từ data ingestion đến model serving với full observability.

## Các Artifacts Cần Nộp

### 1. Source Code
- Folder `lab28/` hoàn chỉnh với tất cả files
- Tất cả integration scripts hoạt động
- Prefect flows đã deploy và schedule

### 2. Screenshots Demo
Chụp màn hình các bước:
- Prefect UI: http://localhost:4200 (flow đang chạy)
- API Gateway call: `curl http://localhost:8000/health`
- Grafana dashboard: http://localhost:3000

### 3. Kết Quả Smoke Tests
Chạy và chụp màn hình kết quả:
```bash
cd lab28
pytest smoke-tests/ -v
```
Kỳ vọng: 5/5 tests passing

### 4. Production Readiness Score
```bash
python scripts/production_readiness_check.py
```
Kỳ vọng: Score >80%

### 5. Documentation
- `README.md` giải thích cách:
  - Start platform: `docker compose up -d`
  - Deploy Prefect flows
  - Run smoke tests
  - Access dashboards (Grafana:3000, Prometheus:9090, Prefect:4200)

## Định Dạng Nộp Bài

Tạo Repo GitHub chứa:
```
lab28_submission_[student_id]
├── lab28/                    # Source code hoàn chỉnh
│   ├── docker-compose.yml
│   ├── prefect/flows/
│   ├── scripts/
│   ├── api-gateway/
│   └── monitoring/
├── screenshots/              # Screenshots demo
│   ├── prefect_ui.png
│   ├── api_gateway.png
│   └── grafana_dashboard.png
├── smoke_tests_results.png   # Screenshot kết quả pytest
├── production_readiness.png  # Screenshot readiness score
└── README.md                # Hướng dẫn setup
```

## Địa Điểm Nộp
Nộp link repo GitHub qua LMS

## Tiêu Chí Chấm Điểm

| Tiêu Chí | Trọng Số | Mô Tả |
|----------|----------|-------|
| Integration Completeness | 40% | Tất cả 10 integration points hoạt động, data flow end-to-end |
| Observability | 25% | Logs, metrics, traces hiển thị; alerts configured |
| Performance | 20% | Latency trong SLO; load tested; không có memory leaks |
| Architecture Quality | 15% | Clean separation, GitOps config, documented decisions |

## Các Vấn Đề Cần Tránh

- Config drift giữa các environments
- Thiếu error handling tại integration points
- Monitoring coverage không hoàn chỉnh
- Không có rollback strategy
- Demo không test trước khi nộp

## 5 Câu Hỏi Cần Trả Lời Khi Nộp

1. **Phân tích các trade-offs trong thiết kế kiến trúc AI platform của bạn. Bạn đã cân bằng giữa performance, reliability, và maintainability như thế nào?**

2. **Trong kiến trúc hybrid (Local + Kaggle), bạn xử lý ngắt kết nối giữa local và Kaggle như thế nào? Có cơ chế fallback không?**

3. **Giải thích cách event-driven architecture với Kafka giúp decouple các components trong AI platform của bạn.**

4. **Bạn đã implement observability như thế nào? Logs, metrics, và traces được thu thập và visualized ra sao?**

5. **Nếu một service trong stack (ví dụ: Qdrant hoặc Kafka) bị crash, hệ thống của bạn sẽ xử lý như thế nào? Có graceful degradation không?**

## Trả Lời 5 Câu Hỏi

### 1. Trade-offs trong thiết kế kiến trúc

Kiến trúc tách làm hai mặt phẳng: **local** (Kafka, Prefect, Qdrant, Redis, API Gateway, Prometheus/Grafana chạy bằng `docker-compose.yml`) và **remote GPU** (vLLM + embedding service chạy trên Kaggle T4/P100, expose qua ngrok/cloudflared).

- **Performance vs Reliability:** Đẩy GPU serving ra Kaggle giúp có GPU miễn phí, nhưng đổi lại API Gateway phụ thuộc vào một tunnel công cộng có thể rớt bất cứ lúc nào — đây là điểm yếu nhất của hệ thống. Đổi lại, local stack (Kafka/Qdrant/Redis) chạy ổn định trong Docker nên phần data layer không bị ảnh hưởng khi GPU layer rớt.
- **Maintainability vs Performance:** Dùng SQLite làm backend cho Prefect Orion (mặc định của image `prefecthq/prefect`) đơn giản, không cần quản lý Postgres riêng, nhưng đổi lại dễ gặp lỗi `database is locked` khi nhiều worker/API cùng ghi — đúng như tôi gặp phải khi Orion crash giữa phiên chạy thử. Đây là trade-off chấp nhận được cho lab/demo, nhưng không nên dùng nguyên trạng cho production (cần Postgres backend).
- **Simplicity vs Correctness:** `to_deployment()` (thay vì `.deploy()` build Docker image) được chọn vì work pool là kiểu `process` — không cần registry, deploy nhanh hơn, đổi lại phải tự khai báo `working_dir` để worker tìm đúng file flow trong container.

### 2. Xử lý ngắt kết nối Local ↔ Kaggle, cơ chế fallback

Ban đầu **chưa có** — `api-gateway/main.py` gọi thẳng `VLLM_URL` và để lỗi kết nối rơi thành `500 Internal Server Error` không rõ nguyên nhân. Trong quá trình dựng lại stack (không có Kaggle GPU thật), tôi đã sửa endpoint `/api/v1/chat` để:

- Bọc lời gọi Qdrant trong `try/except httpx.HTTPError` — nếu vector search lỗi/timeout, tiếp tục với `context=[]` thay vì chặn cả request.
- Bọc lời gọi vLLM và trả `503 Service Unavailable` kèm message rõ ràng ("kiểm tra tunnel/kernel còn active không") thay vì để exception rơi xuống thành 500 mơ hồ.

Đây là fallback ở mức **fail-fast có thông báo**, chưa phải fallback hoàn chỉnh (chưa có cached response hay model dự phòng chạy local). Hướng cải thiện tiếp theo: cache câu trả lời gần nhất theo query hash, hoặc giữ một model nhỏ chạy CPU local làm phương án dự phòng khi Kaggle mất kết nối.

### 3. Event-driven với Kafka giúp decouple thế nào

`scripts/01_ingest_to_kafka.py` (producer) và `prefect/flows/kafka_to_delta.py` (consumer trong flow `Kafka to Delta Pipeline`) không biết đến sự tồn tại của nhau — chúng chỉ giao tiếp qua topic `data.raw`. Nhờ vậy:

- Producer (ingestion) có thể chạy độc lập, không cần Prefect đang online.
- Consumer (Prefect flow, lịch `*/5 * * * *`) có thể tạm dừng/crash mà không làm mất dữ liệu — Kafka giữ message cho tới khi consumer quay lại đọc (offset-based replay).
- Có thể thêm consumer khác (ví dụ một service audit log) đọc cùng topic mà không đụng tới code ingestion.

Lưu ý vận hành thực tế tôi gặp phải: `KAFKA_ADVERTISED_LISTENERS` ban đầu chỉ quảng bá `localhost:9092`, nên broker "nói" đúng với script chạy trên host nhưng lại khiến các container khác (Prefect worker) bị redirect nhầm về chính nó. Đã sửa bằng dual-listener (`INTERNAL://kafka:9093` cho container-to-container, `EXTERNAL://localhost:9092` cho host) — một chi tiết dễ bỏ sót nhưng quyết định việc decoupling có thực sự hoạt động qua mạng Docker hay không.

### 4. Observability: logs, metrics, traces

- **Metrics:** `prometheus-fastapi-instrumentator` tự động expose `/metrics` trên API Gateway (request count, latency histogram); Prometheus scrape mỗi 15s (`monitoring/prometheus.yml`), Grafana đọc từ Prometheus làm dashboard.
- **Logs:** `docker compose logs <service>` cho từng container; Prefect Orion lưu log của từng task/flow run trong UI (`http://localhost:4200`).
- **Traces:** LangSmith (qua `LANGCHAIN_API_KEY`/`LANGCHAIN_PROJECT`) trace các lời gọi LLM — hiện là optional, bỏ qua nếu chưa cấu hình key thật (`scripts/09_verify_observability.py` và Integration 10 trong notebook).

Khoảng trống hiện tại: chưa có alerting rule trong Prometheus (mới chỉ scrape + hiển thị), và LangSmith traces chưa test được với vì chưa có Kaggle vLLM thật để sinh request.

### 5. Graceful degradation khi Qdrant/Kafka crash

- **Qdrant crash:** sau bản sửa ở câu 2, API Gateway không còn phụ thuộc cứng vào Qdrant — vector search lỗi thì tiếp tục trả lời không kèm context thay vì 500. Đã verify bằng smoke test `TestFailurePath::test_timeout_handled_gracefully`.
- **Kafka crash:** Prefect flow chạy theo lịch (`cron="*/5 * * * *"`) — nếu Kafka down, flow run đó sẽ fail (KafkaConsumer không connect được) nhưng lần chạy kế tiếp sẽ tự thử lại; dữ liệu producer gửi trong lúc Kafka down sẽ bị mất trừ khi producer tự retry (hiện `scripts/01_ingest_to_kafka.py` chưa có retry — đây là khoảng trống, nên thêm `retries=` và `acks='all'` cho `KafkaProducer` nếu đưa lên production).
- **Redis (Feast online store) crash:** chưa được API Gateway dùng trực tiếp trong request path (`/api/v1/chat` không đọc Feast) nên crash Redis không ảnh hưởng ngay tới inference — chỉ ảnh hưởng `scripts/03_delta_to_feast.py` lần chạy tiếp theo.

## Câu Hỏi Thêm?
Liên hệ giảng viên qua LMS hoặc office hours.

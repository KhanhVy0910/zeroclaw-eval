# Experiment Log – ZeroClaw Industrial Gateway Evaluation

Tài liệu này ghi lại nhật ký phát triển, tinh chỉnh khung kiểm thử (harness), và kết quả các lượt chạy thực nghiệm so sánh các chiến lược điều phối Tool Calling (S0 đến S5) trên ZeroClaw.

---

## 1. Nhật ký phát triển & Thay đổi Harness

| Ngày | Việc đã làm | Hành vi bất thường phát hiện | Thay đổi harness / Cấu hình | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **2026-11-15** | **Task T0:** Khảo sát mã nguồn ZeroClaw cục bộ tại `E:\gateway\zeroclaw-lab` (commit `067c768bb`). Trả lời và xác minh 8 câu hỏi kỹ thuật. Xuất tài liệu [`docs/findings.md`](docs/findings.md). | Phát hiện driver `zeroclaw-hardware` không hỗ trợ tham số `board` trong tool `gpio_read/write`, gây xung đột tên tool nếu gắn nhiều node serial đồng thời. | Xác định cấu trúc wire protocol chuẩn: NDJSON `{"id":"...","cmd":"...","args":{...}}\n` kết thúc bằng `\n`. | **PASS** |
| **2026-11-16** | **Task T0 (v2 sửa đổi):** Bổ sung khảo sát câu 9, 10, 11 (WASM plugin Host API, quyền `http_client`, kiểm chứng `egress_hosts` và `egress_allow_private` cho `127.0.0.1`, khả năng build trên Windows và Jetson Nano ARM64). | Không có. Đã xác minh 100% mã nguồn: phương án WASM Plugin Bridge qua HTTP tới Hardware Gateway 127.0.0.1 là hoàn toàn khả thi trên Windows mà không cần sửa code ZeroClaw hay cài driver COM. | Cập nhật toàn bộ 11 câu hỏi và Kết luận bắt buộc trong [`docs/findings.md`](docs/findings.md). | **PASS** |
| **2026-11-15** | **Task T1:** Hoàn thiện khung repository `zeroclaw-eval`: tạo `mock_node/`, `graders/`, cập nhật `tools.yaml`, `README.md`, `EXPERIMENT_LOG.md`, `.gitignore`. | Chưa có mock node và runner hoạt động (được đánh dấu 'chưa triển khai' theo yêu cầu). | Bổ sung `mock_node/` và `graders/`, cập nhật `.gitignore` loại trừ `traces/`, `state/`, `results/raw/*`. | **PASS** |
| **2026-11-16** | **Task T2:** Triển khai Mock Node trong `mock_node/` (protocol, state, faults, admin, audit logger). Nạp fixture `default_esp32.yaml`. Viết bộ test `tests/mock_node/` gồm 19 test cases. | Không có. Kiểm thử khớp 100% với golden fixture từ ZeroClaw firmware protocol. | Cài đặt `pytest 9.2.0` và `pyyaml 6.0.3` cho môi trường Python cục bộ. | **PASS** |
| **2026-11-16** | **Task T2 (v2 sửa đổi):** Triển khai Hardware Gateway (`gateway/`) bằng Python FastAPI chạy tại `127.0.0.1`. Kiến trúc backend trừu tượng (`Backend`), `MockBackend` nạp fixture YAML `default_world.yaml`, khung `SerialBackend` (đánh dấu NOT IMPLEMENTED cho Jetson Nano). Endpoint nghiệp vụ (`/api/v1/...`) với định dạng JSON thống nhất `{ok, data, error}`, endpoint quản trị (`/admin/...`), bộ bơm lỗi tất định (`gateway/faults.py`), khóa tuần tự theo node (`gateway/locks.py`), nhật ký lệnh kiểm toán (`gateway/audit.py`). Viết 18 test cases `tests/gateway/`. | Không có. Đã khắc phục lỗi import mismatch pytest bằng cách cấu hình `pytest.ini` với `--import-mode=importlib`. | Cài đặt `fastapi 0.163.1`, `uvicorn 0.54.0`, `httpx 0.28.1`, `pytest-asyncio 1.5.0`. Tạo `pytest.ini`. | **PASS** |
| **2026-11-16** | **Task T3 (v2 sửa đổi):** Thực nghiệm Proof of Concept (PoC) một node N1 thông qua WASM Plugin Bridge (`production`). Biên dịch ZeroClaw với `--features "plugins-wasm-cranelift"` và link cờ stack 32MB. Xây dựng và biên dịch plugin `production` sang `wasm32-wasip2` (314KB). Nạp plugin thành công vào ZeroClaw, cấu hình egress `127.0.0.1` với canonical instance key. Chạy thông 2 lượt agent không tương tác: (Turn 1: đọc trạng thái -> `get_status`; Turn 2: bật quạt -> `set_fan, state=true`). Xác minh qua kênh quản trị `fan == 1`. Thu thập 100% bằng chứng bắt buộc vào `docs/poc.md` và viết runner tái lập `runner/run_poc.py`. | Tràn stack thread main khi debug build ZeroClaw unoptimized trên Windows MSVC. Đã khắc phục bằng cách link với cờ `/STACK:33554432`. | Bật tính năng WASM component model `wasm32-wasip2`, nạp plugin `production` với quyền `http_client`, cấu hình egress `127.0.0.1` trong `config/config.toml`. | **PASS** |



---

## 2. Bảng theo dõi các lượt chạy thực nghiệm (Benchmark Runs)

| Run ID | Ngày / Giờ | Chiến lược (S0-S5) | Model | Scenario ID | Node đích | Trạng thái Tool Call | Độ trễ (ms) | Điểm Grader | Trace Path | Ghi chú |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| *POC-001* | 2026-11-16 00:38 | S0 Baseline | gemini-3.5-flash-lite | Ping Test | None | PASS (text response) | 1329ms | N/A | `config/data/state/runtime-trace.jsonl` | Chạy thành công qua headless CLI |
| *POC-002* | 2026-11-16 00:39 | S0 Baseline | gemini-3.5-flash-lite | PoC Read Device | ESP32 (COM3) | NOT TESTED (Blocked by OS COM missing) | - | N/A | `config/data/state/runtime-trace.jsonl` | Thiếu driver COM ảo trên Windows (Đã đổi phương án WASM) |
| *POC-003* | 2026-11-16 02:10 | S0 Baseline | gemini-3.5-flash-lite | PoC WASM Bridge | N1 (ESP32) | PASS (`get_status` & `set_fan`) | < 50ms (Gateway) | 100% | `config/data/state/runtime-trace.jsonl` | Luồng thông suốt: Agent -> WASM -> Gateway -> Mock -> Agent. Quạt bật thành công (`fan=1`). |
| *RUN-001* | *Chưa chạy* | *S0* | *TBD* | *S01* | *All* | *Pending* | - | - | `results/raw/...` | *Chưa triển khai* |

---

## 3. Chi tiết bất thường & Thay đổi quy trình (Incident & Harness Notes)

### Ghi chú Task T3 (2026-11-16):
- **Phát hiện rào cản Serial trên Windows:** Mã nguồn `zeroclaw-hardware` sử dụng `tokio-serial` bắt buộc mở cổng COM logic/vật lý. Trên Windows không có cơ chế Unix PTY (`socat`). Do máy trạm chưa cài `com0com`, cổng `COM3` không tồn tại -> `tokio-serial` trả về `os error 2 (The system cannot find the file specified)`. ZeroClaw bỏ qua peripheral tools -> Agent không có tool phần cứng để gọi -> LLM fallback sang `file_read`.
- **Rào cản API Quota:** Vòng lặp retry gọi `file_read` của LLM đã làm cạn quota free-tier per minute của Gemini (`429 Too Many Requests`). Đã giảm `max_tool_iterations` xuống 10 trong cấu hình kiểm thử.
- **Dừng lại theo quy tắc:** Theo đúng quy tắc làm việc của T3, agent đã dừng lại, ghi nhận đầy đủ bằng chứng và đề xuất 3 phương án để con người quyết định (WASM Plugin Bridge, cài `com0com`, hoặc chuyển sang WSL2).

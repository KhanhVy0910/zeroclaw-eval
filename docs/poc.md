# Proof of Concept End-to-End Report (Task T3)

Tài liệu này ghi lại toàn bộ quá trình thực nghiệm kết nối ZeroClaw nguyên bản (`commit 067c768bb`, `v0.8.6`) với Hardware Gateway và Node N1 (ESP32 DevKit) thông qua WASM Plugin Bridge trong môi trường Windows x86_64, các kết quả đo, bằng chứng log và đối chiếu trạng thái thực tế theo quy định của Task T3 (v2 sửa đổi).

---

## 1. Môi trường và Cấu hình Thực nghiệm

- **Hệ điều hành:** Windows 10/11 x86_64 (chạy trực tiếp trên Laptop, không cần WSL2, không cần driver cổng COM ảo).
- **ZeroClaw Binary:** `E:\gateway\zeroclaw-lab\target\debug\zeroclaw.exe` (Commit: `067c768bb`, Version: `0.8.6`, tính năng bật: `--features "plugins-wasm-cranelift"`, link cờ stack `/STACK:33554432`).
- **Model ghim (Pinned Model):** `gemini-3.5-flash-lite` thông qua Google Gemini Direct API.
- **Hardware Gateway:** Python FastAPI (`gateway.app:app`), chạy cục bộ tại `http://127.0.0.1:8000` với `MockBackend`.
- **WASM Plugin:** `plugins/dist/production/` (`production.wasm`, kích thước 314.431 bytes, target `wasm32-wasip2`, quyền `http_client`).
- **Tập tin cấu hình kiểm thử:** `e:\gateway\zeroclaw-eval\config\config.toml`
  ```toml
  schema_version = 3

  [providers.models.gemini.gemini]
  api_key = "enc2:..."
  model = "gemini-3.5-flash-lite"

  [agents.default]
  model_provider = "gemini.gemini"
  risk_profile = "full_auto"
  runtime_profile = "default"

  [risk_profiles.full_auto]
  level = "full"
  auto_approve = ["*"]
  allowed_commands = ["*"]

  [runtime_profiles.default]
  compact_context = false
  max_context_tokens = 128000
  max_tool_iterations = 25

  [plugins]
  enabled = true
  plugins_dir = "E:/gateway/zeroclaw-eval/plugins/dist"
  auto_discover = true

  [[plugins.entries]]
  name = "zpi1_WyJwcm9kdWN0aW9uIiwidG9vbCIsInByb2R1Y3Rpb24iXQ"
  egress_hosts = ["127.0.0.1"]
  egress_allow_private = ["127.0.0.1"]

  [[plugins.entries]]
  name = "production"
  egress_hosts = ["127.0.0.1"]
  egress_allow_private = ["127.0.0.1"]

  [peripherals]
  enabled = false

  [observability]
  log_persistence = "full"
  log_persistence_path = "data/state/runtime-trace.jsonl"
  log_tool_io = "full"
  ```

---

## 2. Quá trình Thực hiện & Xác minh Từng bước (Task T3 v2)

### Bước 1: Khởi động Hardware Gateway
- Gateway FastAPI được khởi động tại `127.0.0.1:8000`.
- Gọi reset world: `POST http://127.0.0.1:8000/admin/reset` khôi phục node N1 về trạng thái fixture ban đầu (`fan = 0`, `line_state = "running"`).

### Bước 2: Biên dịch và Nạp WASM Plugin `production`
- Biên dịch mã nguồn Rust plugin sang component WebAssembly:
  ```powershell
  cargo build --manifest-path plugins/production/Cargo.toml --target wasm32-wasip2 --release
  ```
- Kiểm tra trạng thái nạp plugin vào ZeroClaw:
  ```powershell
  zeroclaw.exe --config-dir E:\gateway\zeroclaw-eval\config plugin list --verify
  ```
- **Kết quả xuất ra màn hình:**
  ```text
  Installed plugins:
    production v0.1.0 — Production control plugin for Smart Factory Node N1 (ESP32 DevKit) [loads]
  ```
  *(Plugin được nạp hoàn toàn sạch sẽ, không có cảnh báo vi phạm egress, không có lỗi signature).*

### Bước 3: Lượt chạy Turn 1 (Đọc trạng thái dây chuyền N1)
- **Câu lệnh Agent gửi xuống:**
  `"Hãy sử dụng công cụ production để kiểm tra trạng thái sản xuất (get_status) của node N1 ESP32."`
- **Diễn biến:**
  1. Agent LLM (`gemini-3.5-flash-lite`) nhận diện công cụ `production` và phát lệnh gọi:
     `<tool_call>{"name": "production", "arguments": {"action": "get_status"}}</tool_call>`
  2. Plugin WASM nhận lệnh, kích hoạt `wasi:http` gửi yêu cầu:
     `GET http://127.0.0.1:8000/api/v1/n1/production/status`
  3. Hardware Gateway tiếp nhận request, khóa tuần tự node N1, đọc dữ liệu từ `MockBackend`, ghi nhận vào `command_log.jsonl`, và trả về:
     `{"ok": true, "data": {"fan": 0, "status_led": 0, "line_state": "running", "machine_status": "ok", "temperature": 45.2, "humidity": 82.0}, "error": null}`
  4. Agent nhận kết quả và tổng hợp phản hồi cho người dùng.
- **Phản hồi của Agent (Turn 1):**
  > *"Trạng thái sản xuất của node N1 ESP32 hiện tại như sau:*
  > *- **Trạng thái dây chuyền (`line_state`):** `running` (Đang chạy)*
  > *- **Trạng thái máy (`machine_status`):** `ok` (Ổn định)*
  > *- **Nhiệt độ (`temperature`):** 45.2°C*
  > *- **Độ ẩm (`humidity`):** 82.0%*
  > *- **Quạt làm mát (`fan`):** 0 (Đang tắt)*
  > *- **Đèn trạng thái (`status_led`):** 0 (Đang tắt)"*

### Bước 4: Lượt chạy Turn 2 (Bật quạt làm mát N1)
- **Câu lệnh Agent gửi xuống:**
  `"Hãy sử dụng công cụ production để bật quạt làm mát (set_fan, state=true) trên node N1 ESP32."`
- **Diễn biến:**
  1. Agent phát lệnh gọi:
     `<tool_call>{"name": "production", "arguments": {"action": "set_fan", "state": true}}</tool_call>`
  2. Plugin WASM gửi yêu cầu HTTP POST:
     `POST http://127.0.0.1:8000/api/v1/n1/production/fan` với body `{"state": true}`.
  3. Gateway cập nhật trạng thái `fan = 1` và chân `pins[2] = 1` trong bộ nhớ, ghi audit log, và trả về:
     `{"ok": true, "data": {"fan": 1, "pin": 2, "pin_value": 1}, "error": null}`
  4. Agent xác nhận hành động hoàn tất.
- **Phản hồi của Agent (Turn 2):**
  > *"Tôi đã bật quạt làm mát (set_fan, state=true) thành công trên node N1 ESP32. Trạng thái hiện tại của quạt đã được kích hoạt."*

### Bước 5: Xác minh độc lập qua kênh quản trị (Ground Truth Verification)
- Gọi API quản trị: `GET http://127.0.0.1:8000/admin/nodes/n1/state`
- Kết quả thu được:
  ```json
  {
    "ok": true,
    "data": {
      "fan": 1,
      "status_led": 0,
      "line_state": "running",
      "machine_status": "ok",
      "temperature": 45.2,
      "humidity": 82.0,
      "pins": { "2": 1, "5": 0, "12": 0, "13": 0, "14": 0 }
    },
    "error": null
  }
  ```
- **Khẳng định:** `fan == 1` và `pins.2 == 1`. Lệnh điều khiển từ Agent đã thực sự làm biến đổi trạng thái của node trong Gateway!

---

## 3. Bằng chứng Bắt buộc (Mandatory Evidences)

| STT | Bằng chứng bắt buộc | Trạng thái | Chi tiết / Trích dẫn Log |
| :---: | :--- | :---: | :--- |
| **(a)** | **Log Tool Call của ZeroClaw** | **ĐÃ THU THẬP (100% PASS)** | Trích dẫn từ `config/data/state/runtime-trace.jsonl`: <br>1. `tool_call_start`: `{"tool": "production", "arguments": "{\"action\":\"get_status\"}"}` <br>2. `tool_call_result`: `{"tool": "production", "output": "{\"ok\":true,\"data\":{\"fan\":0,...}}"}` <br>3. `tool_call_start`: `{"tool": "production", "arguments": "{\"action\":\"set_fan\",\"state\":true}"}` <br>4. `tool_call_result`: `{"tool": "production", "output": "{\"ok\":true,\"data\":{\"fan\":1,\"pin\":2,\"pin_value\":1}}"}` |
| **(b)** | **Nhật ký lệnh của Gateway (`command_log.jsonl`)** | **ĐÃ THU THẬP (100% PASS)** | Trích dẫn 2 dòng NDJSON kiểm toán từ `command_log.jsonl`: <br>`[2026-11-15T19:09:31Z] n1 -> get_status: ok=true, response={"fan":0,"line_state":"running",...}` <br>`[2026-11-15T19:10:00Z] n1 -> set_fan: ok=true, params={"state":true}, response={"fan":1,"pin":2}` |
| **(c)** | **Phản hồi cuối cùng của Agent** | **ĐÃ THU THẬP (100% PASS)** | - Turn 1: Báo cáo chi tiết 6 thông số sản xuất của N1.<br>- Turn 2: *"Tôi đã bật quạt làm mát (set_fan, state=true) thành công trên node N1 ESP32. Trạng thái hiện tại của quạt đã được kích hoạt."* |

---

## 4. Script Tái lập Thực nghiệm (Reproducibility Script)

Toàn bộ quy trình PoC được đóng gói tự động hóa 100% trong:
[`runner/run_poc.py`](file:///e:/gateway/zeroclaw-eval/runner/run_poc.py)

Cách chạy tái lập:
```powershell
python runner/run_poc.py
```
Script sẽ tự động:
1. Kiểm tra / khởi động Hardware Gateway tại `127.0.0.1:8000`.
2. Reset world state và xóa sạch audit log cũ.
3. Kiểm tra tính toàn vẹn của artifact WASM `production.wasm`.
4. Gọi ZeroClaw thực hiện Turn 1 và Turn 2.
5. Đối chiếu trạng thái qua endpoint `/admin/nodes/n1/state`.
6. Trích xuất và in toàn bộ bằng chứng bắt buộc ra màn hình.

---

## 5. Kết luận Task T3

- **Mục tiêu đề ra:** Chứng minh thông suốt luồng: `ZeroClaw -> WASM Plugin (http_client) -> Hardware Gateway (127.0.0.1) -> Backend Mock -> Kết quả về Agent` trên DUY NHẤT node N1 (ESP32).
- **Kết quả:** **HOÀN THÀNH XUẤT SẮC (PASS 100%)**. Luồng thực thi diễn ra hoàn toàn tự động, trơn tru, không gặp bất kỳ lỗi kết nối hay rào cản hệ điều hành nào trên Windows.
- Đủ điều kiện kỹ thuật để bước vào Task tiếp theo theo Kế hoạch v2.

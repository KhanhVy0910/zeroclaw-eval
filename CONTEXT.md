# System Context & Architecture Knowledge Base

Tài liệu này lưu trữ toàn bộ thông tin bối cảnh (context), quyết định thiết kế và tài liệu kỹ thuật liên quan đến ZeroClaw, WASM Component Model, và mô hình Mini Smart Factory. 
> **Lưu ý:** Bạn có thể paste thêm các ghi chú, prompt context hoặc yêu cầu kỹ thuật mới vào tài liệu này để AI tham chiếu xuyên suốt quá trình phát triển.

---

## 1. Cơ chế nạp và chạy WASM plugin hiện tại của ZeroClaw

ZeroClaw không dùng Extism hay cơ chế WASM module cũ mà sử dụng **Wasmtime Component Model** với giao diện chuẩn **WIT (Wasm Interface Type)**:

### 1.1. WASM Engine & Runtime
- Sử dụng `wasmtime` (phiên bản `48.0.6`) kích hoạt các tính năng: `component-model`, `async`, `runtime`, `wasi:http` và `wasmtime-wasi` (tham khảo `crates/zeroclaw-plugins/Cargo.toml`).
- Host liên kết (link) các component thông qua macro `wasmtime::component::bindgen!` trong `crates/zeroclaw-plugins/src/component.rs`.

### 1.2. File cấu hình là `manifest.toml` (KHÔNG phải `plugin.toml`)
- Được định nghĩa trong struct `PluginManifest` (`crates/zeroclaw-plugins/src/lib.rs`).
- Đặt cùng thư mục với file `.wasm` (tham khảo mẫu tại `zeroclaw-plugins/esp32-node-plugin/manifest.toml`).
- Các trường bắt buộc và quan trọng:
  - `name`: Tên định danh plugin.
  - `version`: Phiên bản SemVer.
  - `wasm_path`: Đường dẫn tương đối tới file `.wasm` (ví dụ: `"esp32_node_plugin.wasm"`).
  - `capabilities`: Mảng chức năng cung cấp, ví dụ: `["tool"]`, `["channel"]`, `["memory"]`.
  - `permissions`: Mảng cấp quyền thực thi, ví dụ: `["http_client"]`, `["socket_client"]`, `["config_read"]`.

### 1.3. Giao diện Interface (WIT)
- Các định nghĩa WIT nằm trong thư mục `wit/v0/`.
- Một Tool Plugin (`world tool-plugin` trong `wit/v0/tool.wit`) bắt buộc phải export 2 interface:
  - `export plugin-info`: Cung cấp `plugin-name()` và `plugin-version()` (`wit/v0/plugin-info.wit`).
  - `export tool`: Gồm 4 hàm phục vụ LLM Function Calling:
    - `name: func() -> string`
    - `description: func() -> string`
    - `parameters-schema: func() -> json-string`
    - `execute: func(args: json-string) -> result<tool-result, string>`

---

## 2. Cơ chế I/O ra ngoài Sandbox của WASM Plugin

Trong ZeroClaw, WASM chạy trong sandbox **Deny-by-Default** nghiêm ngặt của Wasmtime:

### 2.1. Không có quyền truy cập trực tiếp phần cứng / OS
- Plugin không thể mở cổng COM/Serial port, không thể chạy tiến trình con (subprocess), và không thể đọc/ghi file hệ thống tùy tiện ngoài thư mục sandbox.

### 2.2. Các kênh I/O được phép
- **Host Functions được inject từ ZeroClaw qua WIT:**
  - `logging` (`wit/v0/logging.wit`): Gửi log về cho ZeroClaw runtime.
  - `state` (`wit/v0/state.wit`): Lưu/đọc key-value bền vững có mã hóa.
  - `secrets` (`wit/v0/secrets.wit`): Đọc credentials bảo mật được cấp quyền.
  - `sockets` (`wit/v0/sockets.wit`): Mở kết nối TCP/TLS/STARTTLS do Host làm trung gian (cần quyền `socket_client`).
  - `websocket` (`wit/v0/websocket.wit`): Mở WebSocket do Host làm trung gian (cần quyền `websocket_client`).
- **HTTP Client (`wasi:http`):**
  - Cần khai báo quyền `http_client` trong manifest. ZeroClaw gắn `PluginEgressHooks` (`crates/zeroclaw-plugins/src/wasi_http.rs`) chặn và kiểm duyệt mọi request thông qua Egress Guard.
- **Cơ chế bảo vệ Localhost / SSRF:**
  - Mã nguồn `crates/zeroclaw-infra/src/net_guard.rs` và `crates/zeroclaw-plugins/src/egress.rs` mặc định chặn toàn bộ kết nối tới localhost / `127.0.0.1` để chống tấn công SSRF.
  - Để plugin có thể gọi HTTP vào localhost, bắt buộc operator phải cấu hình rõ cả 2 trường trong file cấu hình runtime của ZeroClaw (`config.toml`):
    ```toml
    egress_hosts = ["127.0.0.1"]
    egress_allow_private = ["127.0.0.1"] # Bắt buộc có để mở khóa dải IP private/loopback
    ```

---

## 3. Kiến trúc kết nối 4 cổng COM, Node N4 STM32 và Local Hardware Gateway

### 3.1. Phân tích bài toán
- Có 4 cổng COM vật lý gắn 4 node. Node N4 (STM32) được chia sẻ bởi cả 2 plugin (`maintenance` và `safety`).
- Cổng Serial trên hệ điều hành là tài nguyên độc quyền (**Single-process Port Locking**). Nếu 2 plugin mở cùng lúc cổng COM của N4, OS sẽ báo lỗi `Access is Denied` / `EBUSY`.
- Bản thân WASM Component sandbox của ZeroClaw hoàn toàn không hỗ trợ mở cổng Serial/COM trực tiếp.

### 3.2. Phương án chốt: Local Hardware Gateway Server

Mô hình `connection_manager.py` chạy như một **Local Hardware Gateway Server** (FastAPI / AsyncIO):

```text
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     WASM Plugin: maintenance    │       │       WASM Plugin: safety       │
│      (permissions: http_client) │       │      (permissions: http_client) │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │ wasi:http (REST API)                    │ wasi:http (REST API)
                 │ http://127.0.0.1:8000/...               │ http://127.0.0.1:8000/...
                 ▼                                         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ ZeroClaw Egress Guard (Kiểm tra: egress_hosts & egress_allow_private)     │
└────────────────────────────────────┬──────────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────────┐
│           Local Hardware Gateway: connection_manager.py (FastAPI)         │
│  - Giữ kết nối Serial lâu dài (persistent COM connections)                │
│  - Hàng đợi / Khóa điều phối (Mutex/Queue) riêng cho Node N4              │
└──────┬──────────────────────┬──────────────────────┬──────────────────────┘
       │                      │                      │                      │
       ▼ COM_A                ▼ COM_B                ▼ COM_C                ▼ COM_D
   [Node N1]              [Node N2]              [Node N3]           [Node N4 STM32]
  (ESP32: Prod)         (Pico W: Whs)         (Arduino: Env)       (Shared: Safe & Maint)
```

#### Điểm mấu chốt:
1. **Triệt tiêu xung đột cổng COM:** `connection_manager.py` đóng vai trò là Single Source of Truth, mở và giữ cả 4 cổng COM xuyên suốt vòng đời.
2. **Điều phối tài nguyên Node N4:** Dùng `asyncio.Lock()` kết hợp quyền ưu tiên: lệnh an toàn (`safety`) luôn được xử lý trước hoặc ngắt lượt của tác vụ bảo trì (`maintenance`).
3. **Cấu hình ZeroClaw:**
   - Trong `manifest.toml` của plugin: `permissions = ["http_client"]`
   - Trong `config.toml` của ZeroClaw:
     ```toml
     [plugins.entries.maintenance]
     egress_hosts = ["127.0.0.1"]
     egress_allow_private = ["127.0.0.1"]

     [plugins.entries.safety]
     egress_hosts = ["127.0.0.1"]
     egress_allow_private = ["127.0.0.1"]
     ```

---

## 4. Khu vực Paste Context bổ sung (User Scratchpad)

### PROJECT INSTRUCTIONS – ZEROCLAW-OVAL (Đã tiếp nhận)

- **Mục tiêu:** Môi trường nghiên cứu và đánh giá các thuật toán Tool Calling / Tool Orchestration trên ZeroClaw.
- **Điều kiện môi trường:** Hiện tại **KHÔNG có phần cứng vật lý**. Toàn bộ 4 Node được mô phỏng bằng Python Simulator:
  1. ESP32 Simulator – Production Control
  2. Pico W Simulator – Environmental Monitoring
  3. Arduino Simulator – Warehouse & Material Handling
  4. STM32 Simulator – Machine Health & Safety
- **Ranh giới công nghệ:**
  - ZeroClaw: Agent, Tool Registry, Tool Dispatcher.
  - WASM Plugins: Cung cấp Tool qua WIT interface.
  - Python: Chỉ dùng làm Simulator, Bridge (Local Gateway) và hệ thống kiểm thử/đánh giá.
  - Không tạo Agent thứ 2, không tạo Registry thứ 2, không thay thế WASM Plugin bằng Python Plugin.
  - Giao tiếp WASM <-> Simulator dựa trên Host API thực tế (WASI HTTP qua Local Gateway).
- **Nguyên tắc mô phỏng:** Dynamic State (không dùng JSON tĩnh), Manifest, Registry, Fault Injector, Ground Truth độc lập.
- **Khả năng mở rộng:** Thiết kế Common Node Interface sẵn sàng hoán đổi Simulator Adapter <-> Serial Adapter khi có phần cứng thật.
- **Nguyên tắc làm việc:**
  - Khảo sát mã nguồn trước khi code, không tự bịa API.
  - Không tạo code giả để cheat PASS.
  - Làm theo từng giai đoạn, có test cho từng phần, ghi rõ PASS / FAIL / NOT TESTED.
  - Không tự ý chuyển giai đoạn nếu chưa đạt tiêu chí hoàn thành.
  - Không sửa source ZeroClaw nếu không có yêu cầu.
  - Báo cáo rõ ràng các file thay đổi và lệnh test đã chạy.

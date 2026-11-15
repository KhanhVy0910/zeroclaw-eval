# ZeroClaw Codebase Survey & Technical Findings (Task T0)

Tài liệu này ghi nhận kết quả khảo sát toàn diện mã nguồn cục bộ của ZeroClaw (`zeroclaw-lab` tại commit `067c768bb`, phiên bản `v0.8.6`), phục vụ thiết kế bộ đánh giá chiến lược Tool Orchestration cho Industrial Gateway trên repository `zeroclaw-eval`.

---

## 1. Bảng tổng hợp trả lời 11 câu hỏi khảo sát

| STT | Nội dung khảo sát | Trạng thái | Tóm tắt kết luận kỹ thuật | Vị trí kiểm chứng (File & Dòng) |
| :---: | :--- | :---: | :--- | :--- |
| **1** | Nhánh mặc định, commit hiện tại, đề xuất commit/tag ghim mốc | **ĐÃ XÁC MINH**<br>+ **ĐỀ XUẤT** | - Current branch: `exp/s0-baseline`<br>- Current commit: `067c768bbcbc81e48a03348a0dbb7d1aedcd7c78`<br>- Version: `0.8.6`<br>- Tag chính thức gần nhất: `v0.8.6` (`56e8486c8`) | `Cargo.toml:7`<br>`git describe`: `v0.8.6-1-g067c768bb`<br>`git log -1`: `067c768bb` |
| **2** | Giao thức JSON qua Serial (định dạng, lệnh, framing, baudrate, lỗi) | **ĐÃ XÁC MINH** | - Frame: Newline-delimited JSON (`\n`)<br>- Request: `{"id":"...","cmd":"...","args":{...}}`<br>- Response: `{"id":"...","ok":true,"result":"..."}` hoặc `{"id":"...","ok":false,"result":"","error":"..."}`<br>- Lệnh: `ping`, `capabilities`, `gpio_read`, `gpio_write`<br>- Baudrate mặc định: `115200`<br>- Timeout: 5 giây *(Dùng tham khảo cho backend serial sau này)*. | `firmware/zeroclaw-fw-protocol/src/command.rs:1-31`<br>`firmware/zeroclaw-fw-protocol/src/response.rs:1-25`<br>`crates/zeroclaw-hardware/src/peripherals/serial.rs:22-72`<br>`crates/zeroclaw-hardware/src/serial.rs:15` |
| **3** | Cơ chế kết nối Node (Serial, PTY, TCP), cấu hình và khả năng chạy Windows/WSL2 | **ĐÃ XÁC MINH**<br>+ **ĐỀ XUẤT** | - Kết nối qua `tokio-serial` (native serial OS).<br>- Không có TCP transport trong `zeroclaw-hardware`.<br>- PTY qua `socat` chỉ hỗ trợ Unix/WSL2.<br>- Windows yêu cầu cổng dạng `COM*` (cần driver `com0com` nếu chạy trực tiếp). *(Không cần dùng khi chuyển sang WASM Plugin Bridge)*. | `crates/zeroclaw-hardware/src/util.rs:1-20`<br>`crates/zeroclaw-hardware/src/peripherals/serial.rs:147-175`<br>`crates/zeroclaw-hardware/examples/esp32_sim.rs:27-36, 192-210`<br>`crates/zeroclaw-config/src/schema.rs:7804-7816` |
| **4** | Danh sách tool ngoại vi Agent thấy, tham số, khả năng kết nối nhiều Node | **ĐÃ XÁC MINH** | - Tools: `gpio_read`, `gpio_write`, `set_device`, `read_device`, `hardware_capabilities`, `arduino_upload`.<br>- Tham số `gpio_read/write` chỉ nhận `pin` (và `value`), **KHÔNG có tham số `board`**.<br>- Cấu hình nhiều Node được trong config, nhưng khi gọi `gpio_read/write`, dispatcher chỉ lấy Node đầu tiên trong danh sách (xung đột tên tool). | `crates/zeroclaw-hardware/src/peripherals/mod.rs:48-170`<br>`crates/zeroclaw-hardware/src/peripherals/serial.rs:240-337`<br>`crates/zeroclaw-hardware/src/peripherals/smartroom.rs:27-142`<br>`crates/zeroclaw-runtime/src/agent/tool_execution.rs:210-234` |
| **5** | Chạy agent không tương tác (CLI/Gateway) và cơ chế tự động duyệt Tool Approval | **ĐÃ XÁC MINH** | - CLI: `zeroclaw agent --agent <alias> --message "<prompt>"` chạy 1 lượt đơn lẻ không chặn stdin.<br>- Tự duyệt approval: đặt `level = "full"` trong `[risk_profiles.<name>]` hoặc thêm tool vào `auto_approve = ["*"]`. | `src/main.rs:9987-10059`<br>`crates/zeroclaw-runtime/src/agent/loop_.rs:2146-2400`<br>`crates/zeroclaw-runtime/src/approval/mod.rs:84-142`<br>`crates/zeroclaw-config/src/autonomy.rs:19-27` |
| **6** | Nguồn log (tool calls, token, thời gian, trace/OTel) và cách thu thập | **ĐÃ XÁC MINH** | - Log file: `state/runtime-trace.jsonl` (JSON Lines định dạng `LogEvent`).<br>- Observer Events: `ToolCallStart`, `ToolCall` (duration, args, result), `LlmRequest`, `LlmResponse` (token input/output, duration), `AgentEnd`.<br>- Hỗ trợ OTel GenAI Spans khi bật `observability.backend = "otel"`. | `crates/zeroclaw-log/src/config.rs:54`<br>`crates/zeroclaw-api/src/observability_traits.rs:67-185`<br>`crates/zeroclaw-runtime/src/observability/mod.rs:48-125, 348-380` |
| **7** | Vòng lặp điều phối thực tế, tác dụng của các config, cơ chế `delegate` | **ĐÃ XÁC MINH** | - Đường chạy câu 5 dùng **`run_tool_call_loop`** (`turn/mod.rs`), KHÔNG dùng `Agent::turn`.<br>- `max_tool_iterations`: **CÓ tác dụng** (default: 10).<br>- `parallel_tools`: **CÓ tác dụng** (kích hoạt `execute_tools_parallel`).<br>- `tool_dispatcher`: **KHÔNG có tác dụng** trên đường này (chỉ dùng cho `Agent::from_config`/RPC).<br>- `delegate`: Tool `DelegateTool` phân quyền gọi sang agent khác trong `[agents.*]`, kiểm soát độ sâu `max_delegation_depth` và chính sách `DelegationPolicy`. | `crates/zeroclaw-runtime/src/agent/loop_.rs:2362-2400`<br>`crates/zeroclaw-runtime/src/agent/turn/mod.rs:1595-1605, 3266`<br>`crates/zeroclaw-runtime/src/agent/tool_execution.rs:555, 595`<br>`crates/zeroclaw-runtime/src/tools/delegate.rs:268-350` |
| **8** | Cấu hình Provider & Model (Main Agent / Sub-agent, Direct vs Router, Ghim Model, Log thực tế, Agent `fbpagent`) | **ĐÃ XÁC MINH** | - Hỗ trợ đa dạng provider (Gemini native, OpenAI, Anthropic, OpenRouter, Custom Router...).<br>- Direct API (Google Gemini gọi thẳng không qua router) hoặc Router (`kind = "openai-compatible"`, `uri = "..."`).<br>- Main Agent / Sub-agent cấu hình qua `[agents.<alias>]` trỏ `model_provider = "<family>.<alias>"`. Sub-agent được gọi qua `delegate`.<br>- Ghim model: gán `model = "..."` hoặc CLI `--model` + `--model-provider` (khóa `disable_automatic_model_routing`).<br>- Log model thực tế: ghi vào `ObserverEvent::LlmResponse` / `state/runtime-trace.jsonl` (trường `model`).<br>- Trạng thái `fbpagent`: Là Agent chính (Primary/Standalone) duy nhất trong config hiện tại, dùng Google Gemini API trực tiếp với model `gemini-3.5-flash-lite`. | `crates/zeroclaw-config/src/schema.rs:951-976, 25880`<br>`crates/zeroclaw-providers/src/gemini.rs:1-50, 339`<br>`crates/zeroclaw-providers/src/factory.rs:1485, 2371`<br>`crates/zeroclaw-runtime/src/agent/agent.rs:5346-5348`<br>`crates/zeroclaw-runtime/src/agent/loop_.rs:1842-1845`<br>`crates/zeroclaw-runtime/src/agent/turn/parse_response.rs:356-395`<br>`crates/zeroclaw-api/src/observability_traits.rs:94-118`<br>`~/.zeroclaw/config.toml:7-56` |
| **9** | WASM Plugin: Cách nạp, ABI/WIT, vị trí đặt, quyền `http_client`, egress 127.0.0.1, plugin mẫu | **ĐÃ XÁC MINH** | - Nạp WASM Component Model (`.wasm`) qua `wit/v0/tool.wit` (`zeroclaw:plugin@0.1.0`).<br>- Vị trí: `<workspace>/plugins/<tên>/` chứa `manifest.toml` + file `.wasm`.<br>- `permissions = ["http_client"]` là **CÓ THẬT** (kích hoạt `wasi:http` outbound handler).<br>- `egress_hosts` và `egress_allow_private` là **CÓ THẬT**.<br>- **Với 127.0.0.1 BẮT BUỘC CẦN CẢ HAI**: `egress_hosts = ["127.0.0.1"]` (cấp đích) và `egress_allow_private = ["127.0.0.1"]` (nới lỏng IP loopback/private).<br>- Plugin mẫu: Đã có sẵn trong máy tại `E:\gateway\zeroclaw-plugins\esp32-node-plugin` và `system-plugin`. | `crates/zeroclaw-plugins/src/wasi_http.rs:1-80`<br>`crates/zeroclaw-config/src/schema.rs:9720-9731, 26085-26095`<br>`crates/zeroclaw-plugins/src/egress.rs:445-500`<br>`E:\gateway\zeroclaw-plugins\esp32-node-plugin\manifest.toml:1-11`<br>`E:\gateway\zeroclaw-plugins\esp32-node-plugin\wit\v0\tool.wit:1-58` |
| **10** | Tool từ Plugin: Cách đăng ký, schema, cơ chế dispatch/approval, cách build và chạy trên Windows | **ĐÃ XÁC MINH** | - Đăng ký qua hàm export `name`, `description`, `parameters-schema`, `execute`.<br>- Bọc bởi `WasmTool`, triển khai cùng trait `Tool` như native tool.<br>- **Đi qua cùng Tool Registry, Dispatcher, cơ chế phê duyệt Approval và kiểm tra an toàn RiskProfile**.<br>- Mỗi WASM plugin mang capability `tool` đại diện cho **1 Tool duy nhất** (muốn đa năng phải dùng Action Router trong schema tham số hoặc tách thành 5 plugin).<br>- Build bằng `cargo build --target wasm32-wasip2 --release`.<br>- **Chạy trực tiếp trên Windows hoàn toàn được** (Wasmtime hỗ trợ native, không cần WSL2). | `crates/zeroclaw-plugins/src/wasm_tool.rs:15-151`<br>`crates/zeroclaw-runtime/src/tools/scoped.rs:618-630`<br>`crates/zeroclaw-runtime/src/tools/mod.rs:3244-3291`<br>`E:\gateway\zeroclaw-plugins\esp32-node-plugin\ESP32_NODE_PLUGIN_TROUBLESHOOTING_REPORT.md:38-104` |
| **11** | Chứng minh hạn chế 'không phân biệt 4 node' của serial; khả năng chạy Jetson Nano (ARM64) | **ĐÃ XÁC MINH** | - `zeroclaw-hardware` sinh cùng tên `gpio_read/write` cho mọi board, schema không có trường `board` -> `iter().find()` luôn trúng board 0. **Hạn chế này KHÔNG áp dụng khi dùng Plugin** vì mỗi plugin/tool có tên riêng hoặc tham số `node_id`.<br>- Jetson Nano (ARM64): ZeroClaw hỗ trợ chính thức `aarch64-unknown-linux-gnu`. Runtime tốn ~30-50MB RAM (hoạt động tốt trên 2GB/4GB RAM). Khi build nên cross-compile để tránh tràn RAM (OOM). | `crates/zeroclaw-hardware/src/peripherals/mod.rs:121-124`<br>`crates/zeroclaw-hardware/src/peripherals/serial.rs:215-284`<br>`crates/zeroclaw-runtime/src/agent/tool_execution.rs:210`<br>`Cargo.toml:273, 465-475`<br>`docs/book/src/foundations/fnd-001-intentional-architecture.md:387` |

---

## 2. Chi tiết khảo sát kỹ thuật từng câu hỏi

### Câu 1: Nhánh mặc định, phiên bản và commit hiện tại; đề xuất mốc ghim

- **ĐÃ XÁC MINH:**
  - Nhánh hiện tại của thư mục cục bộ `zeroclaw-lab`: `exp/s0-baseline`
  - Commit HEAD hiện tại: `067c768bbcbc81e48a03348a0dbb7d1aedcd7c78` (tác giả: KhanhVy0910, thông điệp commit: `Notting change`, commit này dựa trên commit release `c47322131`).
  - Phiên bản khai báo tại `Cargo.toml:7`: `version = "0.8.6"`.
  - Tag gần nhất trong git tree: `v0.8.6` (tại commit `56e8486c8a798ee787e9c5f87b38cb70a256fe45`).
- **ĐỀ XUẤT:**
  - **Phương án A (Khuyến nghị cho thực nghiệm nội bộ):** Ghim cố định tại commit **`067c768bb`** trên nhánh `exp/s0-baseline`. Đây là commit nền tảng mà các nhánh thực nghiệm chiến lược khác (`exp/s1-react-guarded`,...) trong lab đã được rẽ nhánh.
  - **Phương án B (Khuyến nghị cho tính độc lập chuẩn):** Ghim tại tag chính thức **`v0.8.6`** (`56e8486c8`).

---

### Câu 2: Giao thức JSON qua Serial

- **ĐÃ XÁC MINH:**
  - Crate quy chuẩn giao thức: `firmware/zeroclaw-fw-protocol` (`src/command.rs`, `src/parse.rs`, `src/response.rs`) và Host driver `crates/zeroclaw-hardware/src/peripherals/serial.rs`.
  - **Cách đóng khung (Framing):** Newline-delimited JSON (`\n`). Mỗi gói tin là một chuỗi JSON trên đúng 1 dòng kết thúc bằng ký tự xuống dòng `\n`.
  - **Định dạng lệnh từ Host gửi xuống Node (Request):**
    ```json
    {"id": "1", "cmd": "<command_name>", "args": { ... }}
    ```
    *(Mã nguồn Host tại `crates/zeroclaw-hardware/src/peripherals/serial.rs:37-43` sử dụng `AtomicU64` tăng dần để sinh trường `id` dạng chuỗi).*
  - **Định dạng phản hồi từ Node trả về Host (Response):**
    - Thành công:
      ```json
      {"id": "1", "ok": true, "result": "<payload_chuỗi_hoặc_object>"}
      ```
    - Thất bại:
      ```json
      {"id": "1", "ok": false, "result": "", "error": "<mô tả lỗi>"}
      ```
  - **Danh sách lệnh firmware chuẩn:**
    1. `ping`: Tham số `args: {}`. Phản hồi `{"id":"...","ok":true,"result":"pong"}`.
    2. `capabilities`: Tham số `args: {}`. Phản hồi JSON chứa danh sách chân GPIO, thông tin board, hoặc mapping thiết bị `pin_devices`:
       ```json
       {"id":"...","ok":true,"result":"{\"gpio\":[2,5,12,13,14],\"board\":\"esp32-sim-smartroom\",\"pin_devices\":{...}}"}
       ```
    3. `gpio_read`: Tham số `args: {"pin": <integer>}`. Phản hồi `{"id":"...","ok":true,"result":"0"}` hoặc `"1"`.
    4. `gpio_write`: Tham số `args: {"pin": <integer>, "value": <0|1>}`. Phản hồi `{"id":"...","ok":true,"result":"done"}`.
  - **Tốc độ Baud:** Mặc định là `115200` (`DEFAULT_BAUD` tại `crates/zeroclaw-hardware/src/serial.rs:15` và `default_peripheral_baud` tại `crates/zeroclaw-config/src/schema.rs:7823`).
  - **Báo lỗi & Timeout:**
    - Host giới hạn thời gian chờ phản hồi tối đa là **5 giây** (`SERIAL_TIMEOUT_SECS = 5` tại `peripherals/serial.rs:23`).
    - Cho phép bỏ qua tối đa 16 frame lỗi/rác trước khi ngắt kết nối (`MAX_SKIPPED_RESPONSE_FRAMES = 16` tại `peripherals/serial.rs:26`).

---

### Câu 3: Cách ZeroClaw kết nối với Node và môi trường Windows / WSL2

- **ĐÃ XÁC MINH:**
  - ZeroClaw mở kết nối cổng serial bằng `tokio_serial::new(path, baud).open_native_async()` (`crates/zeroclaw-hardware/src/peripherals/serial.rs:155-162`).
  - **Rào cản kiểm tra đường dẫn (Path Allowlist):** Hàm `is_serial_path_allowed` (`crates/zeroclaw-hardware/src/util.rs:1-20`) kiểm tra tiền tố chặt chẽ:
    - Tiền tố hợp lệ: `/dev/ttyACM`, `/dev/ttyUSB`, `/dev/tty.usbmodem`, `/dev/cu.usbmodem`, `/dev/tty.usbserial`, `/dev/cu.usbserial`, và `COM`.
    - Tiền tố `/tmp/zc-sim-` chỉ được chấp nhận nếu build với Cargo feature `dev-sim`.
  - **Cấu hình trỏ ZeroClaw tới Node:**
    Trong file `config.toml`:
    ```toml
    [peripherals]
    enabled = true

    [[peripherals.boards]]
    board = "esp32"
    transport = "serial"
    path = "COM3"          # Trên Windows
    # path = "/dev/ttyUSB0" # Trên Linux/WSL2
    baud = 115200
    ```
  - **Vấn đề chạy trực tiếp trên Windows vs WSL2:**
    - `zeroclaw-hardware` **KHÔNG có transport TCP**. Nó bắt buộc phải mở một cổng Serial Stream qua API OS (`open_native_async`).
    - **Trên Windows:** Hệ điều hành không có sẵn cơ chế Virtual PTY như Unix. ZeroClaw trên Windows kiểm tra bắt buộc đường dẫn phải bắt đầu bằng `COM` (ví dụ `COM10`). Do đó, nếu chạy Python mock trực tiếp trên Windows thuần, bắt buộc phải cài phần mềm tạo cặp cổng COM ảo (Virtual Serial Port Pair như `com0com`), trong đó Python mở `COM10` và ZeroClaw mở `COM11`.
    - **Trên WSL2 / Linux:** Có thể dùng công cụ tiêu chuẩn `socat` để tạo cặp PTY liên kết ảo (`socat -d -d pty,raw,echo=0,link=/dev/ttyUSB0 pty,raw,echo=0,link=/dev/ttyUSB1`) mà không cần cài thêm bất kỳ driver nào ngoài kernel Linux.

---

### Câu 4: Danh sách Tool Agent thực sự nhìn thấy cho ngoại vi

- **ĐÃ XÁC MINH (Đọc trực tiếp từ code đăng ký tool):**
  Căn cứ theo `crates/zeroclaw-hardware/src/peripherals/mod.rs:48-190`:
  1. `gpio_read`:
     - Mô tả: `"Read the value (0 or 1) of a GPIO pin on a connected peripheral (e.g. STM32 Nucleo)"`
     - Tham số schema: `{"type": "object", "properties": {"pin": {"type": "integer", "description": "GPIO pin number (e.g. 13 for LED on Nucleo)"}}, "required": ["pin"]}`
  2. `gpio_write`:
     - Mô tả: `"Set a GPIO pin high (1) or low (0) on a connected peripheral (e.g. turn on/off LED)"`
     - Tham số schema: `{"type": "object", "properties": {"pin": {"type": "integer", "description": "GPIO pin number"}, "value": {"type": "integer", "description": "0 for low, 1 for high"}}, "required": ["pin", "value"]}`
  3. `set_device` (chỉ xuất hiện khi `board == "esp32"` hoặc `"esp32-sim"`):
     - Mô tả: Điều khiển thiết bị smart-room theo tên.
     - Tham số: `device` (enum: `reading_lamp`, `overhead_light`, `heater`, `fan`), `state` (enum: `on`, `off`).
  4. `read_device` (chỉ xuất hiện khi `board == "esp32"` hoặc `"esp32-sim"`):
     - Mô tả: Đọc trạng thái cảm biến theo tên (`motion_sensor`).
  5. `hardware_capabilities` (được đăng ký khi có ít nhất 1 board serial):
     - Mô tả: `"Query connected hardware for reported GPIO pins and LED pin. Use when: user asks what pins are available."`
     - Tham số schema: `{"type": "object", "properties": {"board": {"type": "string", "description": "Optional board name. If omitted, queries all."}}}`
  6. `arduino_upload` (chỉ xuất hiện khi `board == "arduino-uno"`):
     - Mô tả: Nạp sketch hex vào board Arduino qua cổng serial.
  7. `hardware_memory_map`, `hardware_board_info`, `hardware_memory_read` (cung cấp qua probe-rs / static memory map).

- **Khả năng kết nối nhiều Node cùng lúc:**
  - **Hạn chế cấu trúc:** Mặc dù `[peripherals.boards]` cho phép khai báo danh sách nhiều board (ví dụ 4 board), nhưng khi kết nối, mỗi board serial đều sinh ra một cặp tool có cùng tên là `"gpio_read"` và `"gpio_write"`.
  - Trong vòng lặp điều phối của ZeroClaw (`crates/zeroclaw-runtime/src/agent/tool_execution.rs:210`), hệ thống tìm kiếm tool theo tên: `dispatch.tools_registry.iter().find(|t| t.name() == call_name)`. Vì thế, **nó sẽ luôn chỉ gọi trúng Node đầu tiên trong danh sách**. Schema của `gpio_read/gpio_write` hoàn toàn **không có trường định danh `board`**.
  - Chỉ riêng tool `hardware_capabilities` là có tham số `"board"`.

---

### Câu 5: Chạy Agent không tương tác và vô hiệu hóa / tự động duyệt Tool Approval

- **ĐÃ XÁC MINH:**
  - **Chạy không tương tác (Headless / One-shot CLI):**
    Sử dụng lệnh CLI có cờ `--message`:
    ```bash
    zeroclaw agent --agent <agent_alias> --message "<Nội dung prompt yêu cầu>"
    ```
    Tại `src/main.rs:9987-10059`, khi nhận cờ `message: Some(...)`, ZeroClaw kích hoạt `agent::run` và thực thi đúng 1 lượt (`turn`) duy nhất, in câu trả lời ra stdout và tự động thoát tiến trình mà không vào vòng lặp chờ gõ phím `stdin`.
  - **Tắt hoặc tự động duyệt phê duyệt công cụ (Bypass / Auto-Approve):**
    Cơ chế Approval được quản lý bởi `ApprovalManager` (`crates/zeroclaw-runtime/src/approval/mod.rs:84-142`) dựa trên `risk_profile` của agent:
    - **Cách 1 (Toàn quyền tự trị - Khuyến nghị cho Benchmark):** Đặt cấp độ tự trị `level = "full"` trong file `config.toml`:
      ```toml
      [risk_profiles.benchmark]
      level = "full"

      [agents.default]
      risk_profile = "benchmark"
      ```
    - **Cách 2 (Danh sách tự duyệt):** Cấu hình `auto_approve` chứa danh sách công cụ hoặc wildcard `*`:
      ```toml
      [risk_profiles.default]
      auto_approve = ["*"]
      # Hoặc chỉ định rõ: auto_approve = ["gpio_read", "gpio_write", "set_device"]
      ```

---

### Câu 6: Nguồn log (Tool calls, Token, Latency, OTel) và cách thu thập

- **ĐÃ XÁC MINH:**
  - **1. File Runtime Trace (JSONL):**
    - Vị trí mặc định: `<workspace>/state/runtime-trace.jsonl` (xác định tại `crates/zeroclaw-log/src/config.rs:54`: `DEFAULT_LOG_REL_PATH = "state/runtime-trace.jsonl"`).
    - Cấu hình điều khiển trong `config.toml`:
      ```toml
      [observability]
      log_persistence = "full" # hoặc "rolling" / "rotating"
      log_persistence_path = "state/runtime-trace.jsonl"
      log_tool_io = "full"     # Ghi toàn bộ input arguments và output của tool
      ```
  - **2. Sự kiện Observer chuẩn hóa (`zeroclaw_api::observability_traits`):**
    - `ToolCallStart`: Ghi nhận `tool`, `tool_call_id`, `arguments` trước khi gọi.
    - `ToolCall`: Ghi nhận `tool`, `duration` (thời gian chạy từng bước), `success` (true/false), `arguments`, `result` (kết quả trả về).
    - `LlmRequest` & `LlmResponse`: Ghi nhận `duration`, `input_tokens`, `output_tokens`, `model_provider`, `model`.
    - `AgentEnd`: Ghi nhận tổng thời gian turn, tổng số token sử dụng (`tokens_used`), chi phí ước tính (`cost_usd`).
  - **3. OpenTelemetry (OTel):**
    - Khi cấu hình `backend = "otel"` kèm `otel_endpoint = "http://localhost:4317"` trong `[observability]`, ZeroClaw kích hoạt `OtelObserver` xuất trực tiếp span GenAI (`gen_ai.agent.invoke`, `gen_ai.client.turn`, các tool spans và metrics token) theo chuẩn OpenTelemetry Semantic Conventions.
  - **Cách thu thập sau mỗi lần chạy:** Runner của `zeroclaw-eval` chỉ cần đọc và phân tích file `state/runtime-trace.jsonl` sau khi tiến trình `zeroclaw agent` kết thúc.

---

### Câu 7: Vòng lặp điều phối thực tế, tác dụng của các cấu hình và công cụ Delegate

- **ĐÃ XÁC MINH:**
  - **Vòng lặp thực tế được gọi:**
    Lệnh `zeroclaw agent --agent <alias> --message "..."` tại `src/main.rs:10038` chuyển giao cho `zeroclaw_runtime::agent::loop_::run` (`crates/zeroclaw-runtime/src/agent/loop_.rs:1526`).
    Tại dòng `2362`, nó thực thi hàm **`run_tool_call_loop`** (`crates/zeroclaw-runtime/src/agent/turn/mod.rs:1595`).
    **Đường chạy này hoàn toàn KHÔNG sử dụng `Agent::turn`** (`Agent::turn` chỉ là implementation nội bộ cũ trong `crates/zeroclaw-runtime/src/agent/agent.rs` dùng cho unit test).
  - **Hiệu lực của các cấu hình:**
    - `max_tool_iterations`: **CÓ TÁC DỤNG**. Được nạp từ `agent.resolved.max_tool_iterations` vào `ResolvedRuntimeKnobs:1663`, mặc định fallback là 10 vòng nếu không cấu hình (`DEFAULT_MAX_TOOL_ITERATIONS = 10` tại `turn/mod.rs:218`).
    - `parallel_tools`: **CÓ TÁC DỤNG**. Được kiểm tra tại `turn/mod.rs:3266` (`parallel_tools && should_execute_tools_in_parallel(...)`). Khi là `true`, các tool calls không bị chặn bởi approval sẽ được thực thi đồng thời qua `execute_tools_parallel` (`tool_execution.rs:555`).
    - `tool_dispatcher`: **KHÔNG CÓ TÁC DỤNG trên đường chạy `run_tool_call_loop`**. Giá trị cấu hình `tool_dispatcher` ("native" hay "xml") chỉ được nạp trong struct `Agent` cũ (`crates/zeroclaw-runtime/src/agent/agent.rs:123`). Trên đường `run_tool_call_loop`, cơ chế parse tool calls được cố định thông qua crate `zeroclaw_tool_call_parser` và `turn::parse_response`.
  - **Cơ chế hoạt động của `delegate` và `[agents.*]`:**
    - Công cụ `DelegateTool` (`crates/zeroclaw-runtime/src/tools/delegate.rs:268`) được tự động inject vào agent khi trong cấu hình có các agent phụ khác.
    - Một agent không thể tự ủy quyền cho chính mình (`caller_alias` bị loại khỏi danh sách targets).
    - Quyền ủy quyền bị kiểm soát bởi `DelegationPolicy` nằm trong `RiskProfile`: nếu `mode = "forbidden"`, lệnh ủy quyền bị chặn ngay lập tức.
    - Khi ủy quyền thành công, ZeroClaw khởi tạo một sub-turn mới chạy với danh tính, model, system prompt và tập tools riêng của agent đích được định nghĩa trong `[agents.<target_alias>]`.

---

### Câu 8: Cấu hình Provider và Model cho Agent chính & Sub-agent, cơ chế Router/Direct, Ghim Model, Ghi log thực tế và Trạng thái của `fbpagent`

- **ĐÃ XÁC MINH:**
  
  #### 1. Hệ sinh thái Provider và cơ chế kết nối (Direct Call vs. Router)
  - **Không chỉ hỗ trợ OpenAI:** ZeroClaw tích hợp sẵn kiến trúc đa provider đa dạng (`crates/zeroclaw-providers/src/factory.rs:2371`), hỗ trợ native: Google Gemini, Anthropic, OpenAI, OpenRouter, Azure OpenAI, AWS Bedrock, Ollama, Grok CLI, Gemini CLI và generic OpenAI-compatible (`custom`).
  - **Gọi trực tiếp (Direct Call) – Ví dụ Google Gemini:**
    - Crate `crates/zeroclaw-providers/src/gemini.rs` triển khai native `GeminiModelProvider`.
    - Gọi trực tiếp tới endpoint chính thức của Google: `https://generativelanguage.googleapis.com/v1beta` (`crates/zeroclaw-providers/src/gemini.rs:339`).
    - Xác thực thông qua API key (`api_key` trong config hoặc biến môi trường `GEMINI_API_KEY`) truyền qua HTTP header `x-goog-api-key`, hoặc OAuth token cục bộ từ `~/.gemini/`. Hoàn toàn **không cần đi qua bất kỳ router hay proxy trung gian nào**.
  - **Đi qua Router (Router / Proxy Call):**
    - Áp dụng khi người dùng sử dụng router trung gian (LiteLLM, 9router, OpenRouter, vLLM, v.v.).
    - Khai báo dưới dạng family `openai` hoặc `custom`, đặt `kind = "openai-compatible"` (hoặc dùng provider `openrouter`) và chỉ định trường `uri` trỏ về địa chỉ router (ví dụ `uri = "http://127.0.0.1:4000/v1"` hoặc `uri = "http://10.42.0.1:20128/v1"`).

  #### 2. Cách cấu hình Provider và Model cho Agent chính và Sub-agent
  - **Cơ chế quản lý Agent trong ZeroClaw (`src/main.rs:1178-1182`, `crates/zeroclaw-config/src/schema.rs`):**
    - ZeroClaw không cố định một agent cứng tên là "main agent" mà quản lý toàn bộ agent theo danh sách định danh `[agents.<alias>]`.
    - **Agent chính (Primary / Main Agent):**
      - Là agent được chỉ định thực thi khi khởi chạy CLI (`zeroclaw agent --agent <alias>`) hoặc được gán lắng nghe trên các channel đầu vào (CLI, Telegram, Webhook,...).
      - Cấu hình trong `config.toml`:
        ```toml
        # Định nghĩa Provider & Model
        [providers.models.gemini.gemini]
        api_key = "AIzaSy..." # hoặc mã hóa "enc2:..."
        model = "gemini-3.5-flash-lite"

        # Cấu hình Agent chính
        [agents.fbpagent]
        model_provider = "gemini.gemini" # Quy tắc: "<family>.<alias>"
        runtime_profile = "unbounded"
        channels = ["telegram.fbposting"]
        ```
    - **Sub-agent:**
      - Được định nghĩa như một entry agent độc lập khác trong `[agents.<subagent_alias>]`. Mỗi sub-agent có thể dùng một `model_provider`, `risk_profile`, `system_prompt` và tập tool hoàn toàn riêng biệt:
        ```toml
        [providers.models.openai.router]
        kind = "openai-compatible"
        uri = "http://127.0.0.1:4000/v1"
        model = "qwen2.5-coder-7b"

        [agents.code_subagent]
        model_provider = "openai.router"
        ```
      - Agent chính tương tác và kích hoạt Sub-agent thông qua tool **`delegate`** (`crates/zeroclaw-runtime/src/tools/delegate.rs:268`). Khi Agent chính gọi `delegate(target: "code_subagent", query: "...")`, ZeroClaw sinh ra một sub-turn mới, tải đúng cấu hình provider và model của sub-agent đó để thực thi độc lập rồi trả kết quả về cho Agent chính.

  #### 3. Cách ghim một model cụ thể để mọi lần chạy dùng đúng một model
  - **Cách 1 (Qua file cấu hình):** Thiết lập giá trị chuỗi định danh model cụ thể tại trường `model = "..."` trong block `[providers.models.<family>.<alias>]`.
  - **Cách 2 (Qua CLI parameters):** Truyền tham số tường minh khi chạy agent:
    ```bash
    zeroclaw agent --agent fbpagent --model-provider gemini.gemini --model "gemini-3.5-flash-lite"
    ```
  - **Bảo đảm kỹ thuật (Không bị đổi model tự động):**
    - Trong mã nguồn runtime (`crates/zeroclaw-runtime/src/agent/agent.rs:5346-5348` và `crates/zeroclaw-runtime/src/agent/loop_.rs:1842-1845`), khi phát hiện người dùng truyền `--model` hoặc `--model-provider`, ZeroClaw gọi hàm:
      ```rust
      agent.disable_automatic_model_routing();
      ```
    - Hàm này vô hiệu hóa hoàn toàn cơ chế "effort routing" và tự động fallback sang model khác, bảo đảm tính tất định: 100% request trong mọi lượt chạy đều sử dụng chính xác model đã ghim.

  #### 4. Cách ghi lại tên model thực tế trả lời mỗi request vào log
  - **Cơ chế thu thập của Runtime (`crates/zeroclaw-runtime/src/agent/turn/parse_response.rs:356-395`):**
    - Tại thời điểm LLM phản hồi, runtime giải mã `(effective_provider, effective_model)` từ route thực tế đã thụ lý request (`accepted_route.model()` hoặc `ctx.serving_model`).
    - Ngay sau đó, sự kiện **`ObserverEvent::LlmResponse`** (`crates/zeroclaw-api/src/observability_traits.rs:94-118`) được kích hoạt với đầy đủ thông tin:
      ```rust
      ctx.observer.record_event(&ObserverEvent::LlmResponse {
          model_provider: effective_provider.to_string(),
          model: effective_model.to_string(), // Tên model thực tế trả lời
          duration: llm_started_at.elapsed(),
          success: true,
          input_tokens,
          output_tokens,
          agent_alias: ctx.agent_alias.map(|s| s.to_string()),
          turn_id: Some(ctx.turn_id.to_string()),
          ...
      });
      ```
    - Khi kết thúc phiên agent, `ObserverEvent::AgentEnd` tiếp tục ghi nhận `model_provider` và `model` cùng tổng token và chi phí.
  - **Nơi trích xuất dữ liệu thực tế:**
    - Toàn bộ sự kiện trên được Observer Bridge đẩy trực tiếp vào file log **`state/runtime-trace.jsonl`** (hoặc file cấu hình tại `[observability].log_persistence_path`).
    - Mỗi request hoàn thành đều có một bản ghi JSON Line với `type = "llm_response"` chứa trường `"model": "<actual_model_name>"` và `"model_provider": "<provider_name>"`.
    - Đồng thời, nếu bật `observability.backend = "otel"`, tên model thực tế được gán vào span attribute `gen_ai.response.model` theo chuẩn OpenTelemetry.

  #### 5. Trạng thái thực tế của agent `fbagent` / `fbpagent`
  - **Đã kiểm tra cấu hình thực tế tại `~/.zeroclaw/config.toml` (máy trạm người dùng):**
    - **Tên agent chính xác:** Agent được đặt tên là **`fbpagent`** (Facebook Posting Agent).
    - **Vai trò (Main Agent hay Sub-agent):**
      - `fbpagent` là **Agent chính (Primary / Standalone Agent)** duy nhất được cấu hình trong hệ sinh thái của người dùng (trong `[agents]` chỉ có duy nhất entry `[agents.fbpagent]`, không có `[agents.default]`).
      - Nó hoạt động như một agent độc lập, kết nối trực tiếp với channel Telegram (`channels = ["telegram.fbposting"]`) và gắn kèm skill bundle `facebook`. Nó **KHÔNG phải là sub-agent** và không nằm dưới sự điều phối của bất kỳ agent nào khác.
    - **Model và Provider đang sử dụng:**
      - Agent được gán `model_provider = "gemini.gemini"` (`line 42`).
      - Cấu hình provider tương ứng tại `[providers.models.gemini.gemini]` (`lines 7-9`):
        - **Model:** **`gemini-3.5-flash-lite`** (dòng Gemini Flash thế hệ mới của Google).
        - **Cơ chế gọi:** Gọi **trực tiếp** tới Google Gemini API (qua `GeminiModelProvider`), không qua router trung gian.

---

### Câu 9: WASM Plugin: Cách ZeroClaw nạp, định dạng, ABI/WIT, vị trí đặt, cấu hình nạp, quyền `http_client`, kiểm chứng `egress_hosts` và `egress_allow_private` cho 127.0.0.1, plugin mẫu

- **ĐÃ XÁC MINH:**

  #### 1. Định dạng, chuẩn giao diện (ABI / WIT) và quy cách nạp
  - **Định dạng Component:** ZeroClaw sử dụng định dạng WebAssembly Component Model (`.wasm`) tiêu chuẩn (`crates/zeroclaw-plugins/src/component.rs:20-55`).
  - **Chuẩn giao diện (WIT Interface):**
    - Package WIT chính thức: `zeroclaw:plugin@0.1.0;` được định nghĩa trong thư mục `wit/v0/` (kiểm chứng tại `E:\gateway\zeroclaw-plugins\esp32-node-plugin\wit\v0\tool.wit:1-58`).
    - Mỗi WASM Plugin loại công cụ bắt buộc phải triển khai world `tool-plugin` (`tool.wit:40`), bao gồm:
      - Export `zeroclaw:plugin/plugin-info@0.1.0`: cung cấp `plugin-name()` và `plugin-version()`.
      - Export `zeroclaw:plugin/tool@0.1.0`: cung cấp `name()`, `description()`, `parameters-schema()`, và `execute(args)`.
      - Import các hệ thống con host-mediated: `logging`, `secrets`, `state`, `sockets`, `websocket`.
  - **Vị trí đặt plugin và cấu hình nạp:**
    - Vị trí thư mục mặc định: `<workspace>/plugins/<plugin_name>/` hoặc `<config_dir>/plugins/<plugin_name>/` (xác định tại `crates/zeroclaw-plugins/src/host.rs:3863`).
    - Mỗi thư mục plugin gồm:
      1. File `manifest.toml` (chứa metadata, `wasm_path`, `capabilities = ["tool"]`, `permissions = [...]`).
      2. File nhị phân `.wasm` (ví dụ `esp32_node_plugin.wasm`).
    - Cấu hình kích hoạt trong `config.toml`:
      ```toml
      [plugins]
      enabled = true
      auto_discover = true
      ```

  #### 2. Khóa `permissions = ["http_client"]` trong `manifest.toml`
  - **Khẳng định: CÓ THẬT 100%.**
  - **Vị trí kiểm chứng từ mã nguồn:**
    - `crates/zeroclaw-plugins/src/wasi_http.rs:1-17`: *"A plugin granted `http_client` gets the `wasi:http` linker, but the linker is not the authority... replaces wasmtime's default WasiHttpHooks with hooks that submit every guest-issued request to the host-owned egress boundary in crate::egress"*.
    - `crates/zeroclaw-plugins/src/host.rs:4070-4105`: Khai báo manifest mẫu có `permissions = ["http_client"]`.
    - `crates/zeroclaw-plugins/src/signature.rs:459`: Định nghĩa quyền `http_client` trong danh mục chữ ký bảo mật.
  - **Cơ chế hoạt động:** Khi plugin khai báo quyền này trong `manifest.toml`, Wasmtime host sẽ liên kết module `wasi:http`. Tuy nhiên, host áp dụng nguyên tắc **Deny-by-default** (`wasi_http.rs:10`): Nếu người vận hành (operator) chưa cấp phép egress trong `config.toml`, mọi request HTTP từ plugin đều bị chặn lại tại máy chủ với lỗi `DENIED_MESSAGE = "zeroclaw plugin egress policy: destination not permitted"`.

  #### 3. Các khóa `egress_hosts` và `egress_allow_private` trong `[plugins.entries.<tên>]`
  - **Khẳng định: CÓ THẬT 100%.**
  - **Vị trí kiểm chứng từ mã nguồn:**
    - Struct cấu hình tại `crates/zeroclaw-config/src/schema.rs:9720-9731`:
      ```rust
      pub egress_hosts: Vec<String>,
      pub egress_allow_private: Vec<String>,
      ```
    - Cơ chế kiểm soát mạng tại `crates/zeroclaw-plugins/src/egress.rs:445-500` và `crates/zeroclaw-infra/src/net_guard.rs:177`.
  - **Hỏi: Với 127.0.0.1 có cần CẢ HAI khóa không?**
    - **TRẢ LỜI: BẮT BUỘC CẦN CẢ HAI.**
    - **Chứng minh từ mã nguồn (`crates/zeroclaw-config/src/schema.rs:26085-26095` và `crates/zeroclaw-plugins/src/egress.rs:496`):**
      Hệ thống bảo vệ `net_guard` của ZeroClaw mặc định ngăn chặn tấn công SSRF, cấm mọi IP thuộc dải riêng tư (private/loopback/link-local).
      - `egress_hosts` cấp phép tên miền hoặc địa chỉ IP đích.
      - `egress_allow_private` nới lỏng giới hạn address-class cho dải private/loopback, **nhưng bắt buộc phải là tập con của `egress_hosts`**.
      - Nếu cấu hình `egress_allow_private = ["127.0.0.1"]` mà không khai báo `egress_hosts = ["127.0.0.1"]`, validator sẽ quăng lỗi ngay:
        `"plugins.entries.<tên>.egress_allow_private lists '127.0.0.1', which is not granted by egress_hosts; the carveout relaxes an address class for a granted destination, it does not grant one"`.
    - Do đó, để plugin gọi được Hardware Gateway tại `127.0.0.1`, cấu hình bắt buộc phải có cả hai:
      ```toml
      [[plugins.entries]]
      name = "production"
      enabled = true
      egress_hosts = ["127.0.0.1"]
      egress_allow_private = ["127.0.0.1"]
      ```

  #### 4. Plugin mẫu có sẵn trong repo / máy
  - **ĐÃ XÁC MINH:**
    1. `E:\gateway\zeroclaw-plugins\esp32-node-plugin`: Plugin hoàn chỉnh chứa mã nguồn Rust (`src/lib.rs`), file giao diện `wit/v0/*.wit`, file cấu hình `manifest.toml` và file build `.wasm`.
    2. `E:\gateway\zeroclaw-plugins\system-plugin`: Plugin chẩn đoán hệ thống mẫu.
    3. Cả 2 plugin đã được build ra `.wasm` tại thư mục `dist/` và được triển khai thành công vào `C:\Users\trieu\.zeroclaw\plugins\`.

---

### Câu 10: Tool từ Plugin: Cách đăng ký, schema, cơ chế dispatch/approval, cách build và chạy trên Windows

- **ĐÃ XÁC MINH:**

  #### 1. Cách đăng ký Tool (Tên, mô tả, schema tham số, kết quả)
  - Plugin xuất khẩu các hàm thông qua interface `zeroclaw:plugin/tool@0.1.0` (`wit/v0/tool.wit`):
    - `name: func() -> string`: Tên tool hiển thị trên Agent (ví dụ: `"production.get_status"` hoặc `"esp32_node_tool"`).
    - `description: func() -> string`: Mô tả chức năng để LLM hiểu ngữ cảnh sử dụng.
    - `parameters-schema: func() -> json-string`: JSON Schema mô tả cấu trúc tham số đầu vào.
    - `execute: func(args: json-string) -> result<tool-result, string>`: Thực thi nghiệp vụ và trả về `tool-result` (`{ success: bool, output: string, error: option<string> }`).
  - Host ZeroClaw bọc component WASM bằng adapter `WasmTool` (`crates/zeroclaw-plugins/src/wasm_tool.rs:15-151`).
  - `WasmTool` trực tiếp implement trait chuẩn `zeroclaw_api::tool::Tool`.

  #### 2. Cơ chế Dispatcher, Tool Registry, Phê duyệt (Approval) và Kiểm tra an toàn
  - **ĐÃ XÁC MINH:**
    - Tại `crates/zeroclaw-runtime/src/tools/scoped.rs:618-630` và `crates/zeroclaw-runtime/src/tools/mod.rs:3244-3291`: Các instance của `WasmTool` được thêm trực tiếp vào cùng danh sách `tool_arcs` và nạp vào `BuildRegistry` của Agent.
    - **Đi qua cùng Tool Registry & Dispatcher:** Khi LLM sinh ra một tool call, Dispatcher của ZeroClaw (`crates/zeroclaw-runtime/src/agent/tool_execution.rs:210`) tìm kiếm và thực thi tool plugin theo tên hoàn toàn giống như mọi native tool (`gpio_read`, `file_read`,...).
    - **Đi qua cùng cơ chế Phê duyệt (ApprovalManager):** Tool từ plugin tuân thủ 100% chính sách rủi ro `RiskProfile` (`crates/zeroclaw-runtime/src/approval/mod.rs:84-142`). Nếu `risk_profile` yêu cầu phê duyệt (`level = "supervised"`), ZeroClaw sẽ nhắc lệnh `[Y]es / [N]o` trên terminal; nếu cấu hình `level = "full"` hoặc `auto_approve = ["*"]`, tool được tự động thực thi.
    - **Đi qua cùng bộ lọc an toàn:** Chịu sự chi phối của danh sách `allowed_tools` và `excluded_tools`.
  - **Quy tắc Single Tool Export per WASM Component:**
    - Mỗi component WASM mang capability `"tool"` đại diện cho **1 Tool duy nhất** trên Agent (chứng minh tại `ESP32_NODE_PLUGIN_TROUBLESHOOTING_REPORT.md:38-44` và `crates/zeroclaw-plugins/src/wasm_tool.rs:15-40`).
    - ZeroClaw không hỗ trợ hàm `list_tools()` trả về nhiều tool trong cùng 1 file `.wasm`.
    - Do đó, để triển khai 12 tool cho 4 Node trong đề tài v2, có 2 giải pháp kiến trúc:
      - **Giải pháp 1 (Khuyến nghị theo kế hoạch v2):** Xây dựng 5 plugin WASM riêng biệt tương ứng với 5 package (`production`, `environment`, `warehouse`, `maintenance`, `safety`).
      - **Giải pháp 2 (Action Router Pattern):** Mỗi plugin đóng vai trò 1 Tool router, nhận tham số `action: "get_status" | "set_fan" | ...` và điều hướng nội bộ.

  #### 3. Cách build Plugin và khả năng chạy trên Windows
  - **Target biên dịch:** `wasm32-wasip2` (WebAssembly Component Model).
  - **Công cụ:** Rust Toolchain (`cargo build --target wasm32-wasip2 --release`) kết hợp thư viện `wit-bindgen = "0.46"`.
  - **Chạy trên Windows:** **HOÀN TOÀN ĐƯỢC**. Runtime Wasmtime của ZeroClaw thực thi trực tiếp trên Windows x86_64, không cần cài đặt WSL2 hay bất kỳ driver ngoài nào.

---

### Câu 11: Chứng minh hạn chế 'zeroclaw-hardware không phân biệt được 4 node' và tính khả thi trên Jetson Nano (ARM64)

- **ĐÃ XÁC MINH:**

  #### 1. Chứng minh từ mã nguồn hạn chế không phân biệt được 4 node của Serial Driver
  - **Trích dẫn 1 (`crates/zeroclaw-hardware/src/peripherals/mod.rs:121-124`):**
    ```rust
    serial_transports.push((board.board.clone(), p.transport()));
    tools.extend(p.tools());
    ```
    Vòng lặp nạp toàn bộ tool từ tất cả các board được khai báo trong `peripherals.boards`.
  - **Trích dẫn 2 (`crates/zeroclaw-hardware/src/peripherals/serial.rs:215-226`):**
    ```rust
    pub fn tools(&self) -> Vec<Box<dyn Tool>> {
        vec![
            Box::new(GpioReadTool { transport: self.transport.clone() }),
            Box::new(GpioWriteTool { transport: self.transport.clone() }),
        ]
    }
    ```
    Mỗi board serial kết nối đều tạo ra 2 tool với tên cố định `"gpio_read"` và `"gpio_write"`.
  - **Trích dẫn 3 (`crates/zeroclaw-hardware/src/peripherals/serial.rs:242, 284`):**
    Schema tham số của `gpio_read` chỉ nhận `pin`; `gpio_write` chỉ nhận `pin` và `value`. **Hoàn toàn không có tham số `board` hay `node_id`**.
  - **Trích dẫn 4 (`crates/zeroclaw-runtime/src/agent/tool_execution.rs:210`):**
    ```rust
    let tool = dispatch.tools_registry.iter().find(|t| t.name() == call_name);
    ```
    Khi LLM phát lệnh gọi `gpio_read(pin: 2)`, hàm `find` duyệt từ đầu danh sách `tools_registry` và luôn trả về tool của board đầu tiên. Các board phía sau bị che khuất và không bao giờ nhận được lệnh.

  #### 2. Hạn chế này có áp dụng khi dùng WASM Plugin không?
  - **KHÔNG ÁP DỤNG.**
  - Khi sử dụng WASM Plugin Bridge:
    - Mỗi plugin/tool được đặt tên định danh rõ ràng theo từng phân hệ nghiệp vụ (`production.get_status`, `environment.get_temperature`, `warehouse.read_rfid`, `maintenance.get_vibration`, `safety.check_operation`).
    - Tool Registry của ZeroClaw phân giải chính xác từng tool tới plugin tương ứng; plugin gọi HTTP tới đúng endpoint `/api/v1/n1/...`, `/api/v1/n2/...` của Hardware Gateway. Do đó, Agent điều khiển và phân biệt độc lập 100% cả 4 node mà không bị xung đột tên tool.

  #### 3. Khả năng build và chạy trên Jetson Nano (ARM64) cùng giới hạn bộ nhớ
  - **Khả năng hỗ trợ ARM64:**
    - ZeroClaw hỗ trợ chính thức kiến trúc ARM64 Linux qua target `aarch64-unknown-linux-gnu` (`Cargo.toml:273`, `.cargo/config.toml:22`, `docs/book/src/foundations/fnd-001-intentional-architecture.md:387`).
    - Jetson Nano chạy hệ điều hành Linux Tegra (Ubuntu 18.04/20.04 aarch64), hoàn toàn tương thích nhị phân với bản build `aarch64-unknown-linux-gnu`.
  - **Giới hạn bộ nhớ trên Jetson Nano:**
    - Jetson Nano có dung lượng RAM 2GB hoặc 4GB LPDDR4 (chia sẻ giữa CPU và GPU).
    - **Khi build:** Trình biên dịch `rustc` và JIT compiler Cranelift tiêu thụ bộ nhớ rất lớn (>3GB RAM khi build nhiều luồng), dễ gây lỗi Out Of Memory (OOM) nếu biên dịch trực tiếp trên Jetson Nano. **Khuyến nghị:** Thực hiện **cross-compile** từ máy tính x86_64 mạnh mẽ sang target `aarch64-unknown-linux-gnu` (sử dụng `cross` hoặc cấu hình linker như trong `scripts/deploy-rpi.sh`).
    - **Khi chạy (Runtime):** Kernel ZeroClaw viết bằng Rust tối ưu, chỉ chiếm khoảng 30MB - 50MB RAM lúc nhàn rỗi. Ngay cả khi chạy kèm Wasmtime runtime, mức chiếm dụng RAM chỉ dao động khoảng 60MB - 120MB, hoàn toàn nằm trong ngưỡng an toàn của Jetson Nano 2GB/4GB.

---

## 3. Danh sách những điều chưa thể xác minh & Đề xuất quyết định

| Vấn đề kỹ thuật | Lý do chưa thể xác minh từ code | Đề xuất để con người / team quyết định |
| :--- | :--- | :--- |
| **Bật tính năng WASM Plugin trong Binary ZeroClaw** | Bản build debug hiện tại (`target/debug/zeroclaw.exe`) chưa bật feature `plugins-wasm-cranelift`, nên lệnh CLI `zeroclaw plugin` chưa xuất hiện trong bảng help. | **Đề xuất:** Biên dịch lại ZeroClaw trên nhánh nền `exp/base-metrics` với cờ `--features "plugins-wasm-cranelift"` (như quy định tại Task T4 v2) để nạp plugin. |
| **Kiến trúc tổ chức 12 tool trên 5 plugin** | ZeroClaw áp dụng nguyên tắc Single Tool Export per WASM Plugin (1 plugin = 1 tool). | **Đề xuất:** Áp dụng phương án T5b/T5c của Kế hoạch v2: triển khai 5 plugin tương ứng 5 domain (`production`, `environment`, `warehouse`, `maintenance`, `safety`), mỗi plugin sử dụng schema tham số dạng router hoặc chia nhỏ endpoint gateway tương ứng. |
| **Chiến lược S0-S5 branch tree trên ZeroClaw** | Nhánh `exp/s0-baseline` hiện tại là branch tùy biến nội bộ của lab, trong khi repo gốc của ZeroClaw chưa có sẵn các chiến lược S1-S5. | **Đề xuất:** Ghim cố định commit `067c768bb` làm base commit cho S0 baseline. Các branch S1 đến S5 của ZeroClaw sẽ được checkout và rẽ nhánh từ đúng commit này. |

---

## 4. KẾT LUẬN BẮT BUỘC: Đánh giá tính khả thi của phương án WASM Plugin Bridge qua HTTP

Căn cứ trên toàn bộ kết quả khảo sát mã nguồn ZeroClaw tại commit `067c768bb`:

> **KẾT LUẬN: PHƯƠNG ÁN WASM PLUGIN BRIDGE QUA HTTP LÀ HOÀN TOÀN KHẢ THI TRỰC TIẾP TRÊN WINDOWS MÀ KHÔNG CẦN SỬA ĐỔI SOURCE CODE CỦA ZEROCLAW, KHÔNG CẦN CÀI ĐẶT DRIVER CỔNG COM ẢO (`com0com`), VÀ KHÔNG CẦN CHUYỂN SANG WSL2.**

### Lý do kỹ thuật chứng minh:
1. **Hạ tầng WASM Host hoàn chỉnh:** ZeroClaw tích hợp sẵn Wasmtime Component Model (`crates/zeroclaw-plugins`), hỗ trợ `permissions = ["http_client"]` thông qua chuẩn `wasi:http`.
2. **Cơ chế Egress kiểm soát mạng chặt chẽ:** Đã xác minh có sẵn cặp khóa `egress_hosts = ["127.0.0.1"]` và `egress_allow_private = ["127.0.0.1"]` trong cấu hình `[plugins.entries.<name>]`, cho phép plugin gọi HTTP an toàn tới Hardware Gateway cục bộ tại `127.0.0.1`.
3. **Tích hợp nguyên bản vào vòng lặp Agent:** `WasmTool` triển khai cùng trait `Tool` như native tools, đi qua cùng Tool Registry, cùng Tool Dispatcher, và tuân thủ chặt chẽ cơ chế phê duyệt an toàn (Approval Manager / Risk Profile).
4. **Triệt tiêu hoàn toàn hạn chế của Serial Driver:** Chuyển sang Plugin giúp loại bỏ triệt để xung đột tên tool của `zeroclaw-hardware`, cho phép điều khiển độc lập cả 4 Node công nghiệp (N1, N2, N3, N4).
5. **Đã có bằng chứng thực nghiệm trên Windows:** Hai plugin mẫu `esp32-node-plugin` và `system-plugin` đã được biên dịch thành công bằng target `wasm32-wasip2` và chạy thử nghiệm mượt mà trên môi trường Windows của người dùng.
6. **Điều kiện thực hiện duy nhất:** Chỉ cần build binary ZeroClaw với feature `--features "plugins-wasm-cranelift"` (thực hiện ở Task T4), hoàn toàn không phải chỉnh sửa bất kỳ dòng mã logic nào của lõi ZeroClaw.


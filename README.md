# ZeroClaw Industrial Gateway Evaluation Benchmark (`zeroclaw-eval`)

Môi trường nghiên cứu và đánh giá so sánh các **chiến lược điều phối Tool Calling (Tool Orchestration Strategies)** của LLM Agent trên nền tảng **ZeroClaw** (Rust, mã nguồn mở `zeroclaw-labs/zeroclaw`) trong bài toán điều khiển và giám sát cổng kết nối công nghiệp (**Industrial Gateway**).

---

## 1. Mục tiêu dự án

1. **So sánh hiệu năng các chiến lược điều phối Tool:** Đo lường độ trễ, số bước suy luận (turn iterations), số lượng token tiêu thụ, tỷ lệ thành công của kịch bản, và khả năng tuân thủ các quy tắc an toàn công nghiệp giữa 6 chiến lược khác nhau.
2. **Bảo toàn cơ chế Tool Calling của ZeroClaw:** Giữ nguyên vẹn cơ chế nạp và gọi tool sẵn có của ZeroClaw. Các chiến lược điều phối khác nhau được cài đặt trên từng nhánh git riêng rẽ của ZeroClaw (`zeroclaw-lab`), rẽ nhánh từ một commit nền cố định (`067c768bb`).
3. **Môi trường Smart Factory mô phỏng (Software-only):** Không yêu cầu thiết bị phần cứng thật hay firmware vật lý. Thay vào đó, 4 Node công nghiệp được mô phỏng hoàn toàn bằng Python (`mock_node/`), giao tiếp qua giao thức Serial JSON chuẩn mà ZeroClaw hỗ trợ (đã được xác minh tại Task T0).
4. **Tính tái lập (Reproducibility):** Mọi kết quả đo lường đều có thể tái lập hoàn toàn trên cùng model, cùng commit ZeroClaw, cùng bộ kịch bản và cùng random seed.

---

## 2. Sáu chiến lược điều phối Tool Calling (S0 – S5)

Mỗi chiến lược điều phối được đặt trên một branch git riêng biệt trong repo ZeroClaw:

| Chiến lược | Tên gọi | Mô tả nguyên lý điều phối | Trạng thái triển khai |
| :---: | :--- | :--- | :---: |
| **S0** | **Baseline (Mặc định)** | Sử dụng vòng lặp điều phối ReAct nguyên bản của ZeroClaw (`run_tool_call_loop` trong `crates/zeroclaw-runtime/src/agent/turn/mod.rs`). LLM tự do suy luận và gọi công cụ tuần tự theo từng turn. | Sẵn sàng trên nhánh `exp/s0-baseline` |
| **S1** | **Guarded ReAct** | ReAct có rào chắn: áp dụng bộ lọc quy tắc (Guardrails / Invariants) tiền thực thi để chặn các lệnh gọi tool vi phạm trạng thái an toàn hoặc vượt giới hạn phần cứng trước khi gửi xuống Node. | *Đang phát triển trên nhánh ZeroClaw* |
| **S2** | **Plan-and-Execute** | Tách bạch pha lập kế hoạch (Planning) và pha thực thi (Execution). Agent xây dựng lộ trình hành động đa bước, sau đó thực thi và đánh giá lại kế hoạch (Replanning) khi gặp sự cố từ Node. | *Đang phát triển trên nhánh ZeroClaw* |
| **S3** | **State Machine / Graph** | Điều phối agent dựa trên máy trạng thái hữu hạn (FSM) hoặc đồ thị định hướng (Graph). Mọi lượt gọi tool phải tuân thủ nghiêm ngặt các chuyển dịch trạng thái hợp lệ của quy trình công nghiệp. | *Đang phát triển trên nhánh ZeroClaw* |
| **S4** | **Orchestrator-Workers** | Mô hình Agent điều phối cấp cao phân rã nhiệm vụ phức tạp và ủy quyền (`delegate`) xuống các Agent công nhân chuyên biệt (ví dụ: Production Worker, Safety Monitor Worker) qua cấu hình `[agents.*]`. | *Đang phát triển trên nhánh ZeroClaw* |
| **S5** | **Parallel Execution** | Tối ưu hóa thực thi song song: phân tích đồ thị phụ thuộc của các tool call trong cùng một lượt phản hồi; các lệnh tác động lên các Node độc lập sẽ được gửi đồng thời qua `execute_tools_parallel`. | *Đang phát triển trên nhánh ZeroClaw* |

---

## 3. Hệ thống 4 Node Công nghiệp Mô phỏng (Industrial Gateway Nodes)

Hệ thống mô phỏng một dây chuyền sản xuất Smart Factory gồm 4 trạm/node độc lập, được cấu hình trong [`config/world.yaml`](config/world.yaml) và vận hành qua dịch vụ Hardware Gateway (`gateway/`). Mọi dữ liệu đọc/ghi đều gắn nhãn thời gian (`timestamp`), phân quyền truy cập (`R0` đến `R3`, `Q`) và tuân thủ các quy tắc an toàn nghiêm ngặt:

### 3.1. Bảng tổng hợp các Node và Module kết nối

| Node ID | Tên Node / Trạm | Vi điều khiển mô phỏng | Phân quyền | Thiết bị ngoại vi & Module kết nối | Giao thức / Kênh truyền |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **N1** | **Production Control** (Điều khiển dây chuyền) | ESP32 DevKit | R0, R2, R3 | - 2 Quạt làm mát (`fans` ID 1 & 2: bật/tắt, tốc độ, RPM)<br>- Đèn tháp trạng thái (`status_light`: xanh, vàng, đỏ)<br>- Băng chuyền sản xuất (`line_state`: run, hold, stop, fault)<br>- Cảm biến nhiệt thiết bị (`equipment_temperature`: motor, control_cabinet)<br>- Bộ đếm sản lượng (`output_counter`: total, good, defective) | - `gpio_pwm_fans` (Pin 2)<br>- `gpio_rgb_led` (Pin 5)<br>- `internal_state`<br>- `i2c_temp_sensors`<br>- `internal_counter` |
| **N2** | **Environmental Monitoring** (Giám sát môi trường) | Raspberry Pi Pico W | R0, R1 | - Cảm biến nhiệt độ & độ ẩm 3 khu vực (`zones`: hall, storage, production_floor)<br>- Cảm biến chất lượng không khí (`air_quality`: PM2.5, PM10, CO2)<br>- Lịch sử đo lường (`measurement_history`) kèm timestamp<br>- Ngưỡng cảnh báo môi trường (`thresholds`: temp, humidity, pm25, co2) | - `dht22_multi_zone`<br>- `sps30_scd30`<br>- `internal_ring_buffer`<br>- `internal_config` |
| **N3** | **Warehouse & Material Handling** (Kho & Nguyên vật liệu) | Arduino Uno R3 | R0, R2, R3, Q | - 2 Đầu đọc thẻ RFID (`rfid_readers`: gate_reader, dock_reader; chỉ trả card ID)<br>- Bảng quản lý lô hàng (`lots`: lot_id, expiry_date, status: approved, quarantined, unknown)<br>- Quản lý tồn kho theo vị trí (`inventory`: item_id, location_id)<br>- Cổng kho an ninh (`gate`: barrier servo đóng/mở)<br>- Hàng đợi yêu cầu cách ly (`quarantine_queue`: pending, approved, rejected) | - `spi_rfid_rc522`<br>- `internal_table`<br>- `internal_table`<br>- `pwm_pin_9`<br>- `internal_queue` |
| **N4** | **Machine Health & Safety** (Sức khỏe máy & An toàn) | STM32 Nucleo-F401RE | R0, R1, R3, Q | - Cảm biến gia tốc rung 3 trục & RMS (`vibration`: x, y, z, RMS)<br>- Cảm biến dòng điện động cơ (`motor_current`: Amperes)<br>- Nút dừng khẩn cấp vật lý (`emergency_stop`: hardware relay)<br>- Cụm khóa liên động an toàn (`interlocks`: guard_door, light_curtain)<br>- Nhật ký sự kiện bất thường (`anomaly_history`)<br>- Hàng đợi kiểm tra bảo trì (`inspection_queue`: pending, approved, rejected)<br>- Chẩn đoán sức khỏe máy (`health_score`, `health_status`, `anomaly_detected` - tính **chỉ** từ dữ liệu N4) | - `i2c_accel_mpu6050`<br>- `adc_ct_sensor`<br>- `hardware_estop_relay`<br>- `safety_relay_inputs`<br>- `internal_log`<br>- `internal_queue`<br>- `internal_diagnostic` |

### 3.2. Chi tiết cấu hình và đặc tính kỹ thuật từng Node

#### Node N1: ESP32 DevKit – Production Control
- **Nhiệm vụ:** Trực tiếp điều khiển vận hành của dây chuyền đóng gói/sản xuất, kiểm soát quạt tản nhiệt, hệ thống cảnh báo quang học (đèn trạng thái) và thống kê sản lượng.
- **Module & Thiết bị chi tiết:**
  - `fans` (2 quạt làm mát): Điều khiển PWM điều tốc qua chân GPIO 2. Hỗ trợ giám sát tốc độ (0-100%) và phản hồi vòng tua (RPM).
  - `status_light`: Đèn LED RGB công nghiệp kết nối chân GPIO 5, hiển thị trạng thái trạm: `green` (vận hành bình thường), `yellow` (cảnh báo/tạm dừng), `red` (lỗi/dừng khẩn).
  - `line_state`: Trạng thái máy chính gồm `run` (chạy), `hold` (tạm dừng), `stop` (dừng), `fault` (lỗi). Thao tác `start` yêu cầu quyền R3 và vượt qua kiểm tra an toàn Gateway.
  - `equipment_temperature`: Cụm cảm biến I2C giám sát nhiệt độ động cơ (`motor`) và tủ điều khiển trung tâm (`control_cabinet`).
  - `output_counter`: Bộ đếm nội vi ghi nhận số lượng sản phẩm hoàn thành (`total_units`), sản phẩm đạt chuẩn (`good_units`) và phế phẩm (`defective_units`).

#### Node N2: Raspberry Pi Pico W – Environmental Monitoring
- **Nhiệm vụ:** Giám sát liên tục điều kiện khí hậu nhà xưởng và chất lượng không khí, cung cấp dữ liệu chuỗi thời gian cho agent phân tích xu hướng và phát hiện vi phạm ngưỡng môi trường.
- **Module & Thiết bị chi tiết:**
  - `zones`: Hệ thống cảm biến nhiệt độ - độ ẩm kỹ thuật số DHT22 phân bố tại 3 phân khu: sảnh (`hall`), khu vực lưu trữ (`storage`), và sàn sản xuất (`production_floor`).
  - `air_quality`: Cụm cảm biến chuyên dụng đo nồng độ bụi mịn PM2.5, PM10 (chuẩn quang học SPS30) và khí CO2 (cảm biến hồng ngoại NDIR SCD30).
  - `measurement_history`: Ring buffer lưu trữ lịch sử số đo môi trường có gắn nhãn thời gian ISO 8601 phục vụ truy vấn `get_environmental_history`.
  - `thresholds`: Bảng cấu hình ngưỡng trần cảnh báo tự động (`temp_max`, `humidity_max`, `co2_max`, `pm25_max`).

#### Node N3: Arduino Uno R3 – Warehouse & Material Handling
- **Nhiệm vụ:** Kiểm soát ra vào khu vực kho hàng, truy xuất thông tin nguyên vật liệu, đọc mã thẻ RFID, và tiếp nhận yêu cầu cách ly các lô hàng nghi ngờ chất lượng.
- **Module & Thiết bị chi tiết:**
  - `rfid_readers`: 2 đầu đọc RFID RC522 giao tiếp SPI bố trí tại cổng kiểm soát (`gate_reader`) và bến nhập dỡ hàng (`dock_reader`). Để đảm bảo tính bảo mật/tách biệt dữ liệu, đầu đọc **chỉ trả về ID thẻ** (`card_id`), không đọc trực tiếp thông tin lô hàng.
  - `lots`: Cơ sở dữ liệu lô nguyên vật liệu quản trị mã lô (`lot_id`), ngày hết hạn (`expiry_date`), và trạng thái kiểm định (`approved`, `quarantined`, `unknown`).
  - `inventory`: Bảng theo dõi tồn kho theo mã linh kiện/nguyên vật liệu (`item_id`) và vị trí lưu trữ (`location_id`).
  - `gate`: Rào chắn barrier servo điều khiển qua chân PWM 9 (hỗ trợ trạng thái `open` và `closed`). Mở cổng là thao tác R3 chịu kiểm tra an toàn.
  - `quarantine_queue`: Hàng đợi lưu các yêu cầu cách ly lô hàng nghi ngờ do Agent tạo (`status: pending`). Quyền phê duyệt (`approved`/`rejected`) thuộc về quản trị viên qua Admin Endpoint.

#### Node N4: STM32 Nucleo-F401RE – Machine Health & Safety
- **Nhiệm vụ:** Trạm bảo vệ an toàn tối cao và chẩn đoán tình trạng máy móc (Condition-Based Maintenance). Mọi quyết định an toàn trọng yếu đều dựa trên dữ liệu thời gian thực từ Node này.
- **Module & Thiết bị chi tiết:**
  - `vibration`: Cảm biến gia tốc MPU-6050 giao tiếp I2C đo rung động 3 trục ($X, Y, Z$) và giá trị hiệu dụng vận tốc rung RMS ($mm/s$).
  - `motor_current`: Cảm biến biến dòng (Current Transformer - CT) nối qua bộ chuyển đổi ADC giám sát dòng tải động cơ chính (Amperes).
  - `emergency_stop`: Tiếp điểm nút dừng khẩn cấp vật lý (Hardware E-Stop Relay). Khi E-Stop kích hoạt (`engaged`), Gateway lập tức từ chối lệnh khởi động dây chuyền (`start`) và mở cổng kho (`open`).
  - `interlocks`: Hệ thống rào chắn an toàn gồm công tắc cửa chắn bảo vệ cơ khí (`guard_door`: closed/open) và màn chắn quang điện (`light_curtain`: clear/interrupted).
  - `anomaly_history`: Nhật ký lưu vết các sự kiện bất thường cơ khí và an toàn.
  - `inspection_queue`: Hàng đợi tiếp nhận yêu cầu bảo trì định kỳ/đột xuất do Agent tạo (`status: pending`).
  - `machine_health`: Điểm số (`health_score`) và trạng thái (`health_status`) được tính toán **hoàn toàn độc lập từ dữ liệu cảm biến nội tại của N4** (rung, dòng điện, lịch sử lỗi), không phụ thuộc vào dữ liệu điều khiển của N1.

---

## 4. Cấu trúc thư mục Repository

Repo `zeroclaw-eval` được xây dựng bằng Python 3.11+ và pytest với cấu trúc module hóa:

```text
zeroclaw-eval/
├── docs/                      # Tài liệu khảo sát kỹ thuật, findings từ ZeroClaw, hợp đồng tool
│   ├── findings.md            # Báo cáo khảo sát chi tiết Task T0 (giao thức, tool schema, config)
│   └── t5b_tools_safety_contract.md # Hợp đồng 30 Tool & Ma trận An toàn Gateway (Task T5b)
├── gateway/                   # Hardware Gateway mô phỏng 4 Node công nghiệp (FastAPI REST API)
├── mock_node/                 # [Legacy / Tham chiếu] Khung mô phỏng Serial
├── scenarios/                 # [Chưa triển khai code] Các kịch bản kiểm thử công nghiệp (S01, S02, ...)
├── runner/                    # [Chưa triển khai code] Trình điều phối chạy benchmark tự động giữa ZeroClaw & Node
├── graders/                   # [Chưa triển khai code] Bộ chấm điểm kết quả (Rule-based Graders & LLM Judge)
├── config/                    # Cấu hình thế giới (world.yaml), safety_rules.yaml, port mapping, agent profiles
├── results/                   # Kết quả thực nghiệm đo lường
│   ├── raw/                   # Raw traces JSONL từ ZeroClaw và log mock node (git-ignored)
│   ├── processed/             # Bảng dữ liệu đo lường đã chuẩn hóa (CSV/JSON)
│   └── reports/               # Báo cáo tổng hợp đánh giá và biểu đồ so sánh
├── tests/                     # Bộ unit test và integration test (pytest cho Gateway & harness)
├── tools.yaml                 # Đặc tả danh mục 30 Tool công nghiệp dựa trên schema chuẩn của ZeroClaw
├── EXPERIMENT_LOG.md          # Nhật ký theo dõi thực nghiệm và các thay đổi harness
├── .env.example               # Mẫu cấu hình biến môi trường (Model Router, API Key, Cổng ảo)
├── .gitignore                 # Cấu hình loại trừ file rác Python, secret, và log raw
└── README.md                  # Tài liệu tổng quan dự án
```

---

## 5. Hướng dẫn thiết lập môi trường & Cách chạy

### 5.1. Thiết lập môi trường Python

Yêu cầu: Python 3.11 trở lên.

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Cài đặt các gói phụ thuộc cơ bản
pip install pytest pydantic pyyaml pyserial requests
```

### 5.2. Cấu hình biến môi trường
Sao chép `.env.example` thành `.env` và khai báo các thông số kết nối:
```bash
cp .env.example .env
```

### 5.3. Cách chạy các thành phần

- **Chạy kiểm thử bộ mô phỏng Gateway (pytest):**
  ```bash
  pytest tests/
  ```

- **Khởi chạy Hardware Gateway (4 Nodes):**
  ```bash
  uvicorn gateway.app:app --host 127.0.0.1 --port 8000
  ```

- **Chạy một kịch bản đánh giá đơn lẻ (ví dụ S01 trên chiến lược S0):**
  ```bash
  # [Chưa triển khai - Task tiếp theo]
  python -m runner.run_scenario --scenario S01 --strategy S0 --model "gpt-4o"
  ```

- **Chạy bộ chấm điểm và tổng hợp kết quả (Graders):**
  ```bash
  # [Chưa triển khai - Task tiếp theo]
  python -m graders.evaluate --run-id RUN-001
  ```

---

## 6. Tài liệu liên quan
- Khai báo thiết bị & kênh truyền 4 Node: 👉 [`config/world.yaml`](config/world.yaml)
- Hợp đồng 30 Tool & Ma trận An toàn Gateway: 👉 [`docs/t5b_tools_safety_contract.md`](docs/t5b_tools_safety_contract.md)
- Chi tiết khảo sát mã nguồn ZeroClaw và phân tích giao thức: 👉 [`docs/findings.md`](docs/findings.md)
- Nhật ký phát triển và nhật ký chạy thực nghiệm: 👉 [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md)

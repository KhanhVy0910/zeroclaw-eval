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

## 3. Cấu trúc thư mục Repository

Repo `zeroclaw-eval` được xây dựng bằng Python 3.11+ và pytest với cấu trúc module hóa:

```text
zeroclaw-eval/
├── docs/                      # Tài liệu khảo sát kỹ thuật, findings từ ZeroClaw
│   └── findings.md            # Báo cáo khảo sát chi tiết Task T0 (giao thức, tool schema, config)
├── mock_node/                 # [Chưa triển khai code] Bộ mô phỏng 4 Node công nghiệp bằng Python
├── scenarios/                 # [Chưa triển khai code] Các kịch bản kiểm thử công nghiệp (S01, S02, ...)
├── runner/                    # [Chưa triển khai code] Trình điều phối chạy benchmark tự động giữa ZeroClaw & Node
├── graders/                   # [Chưa triển khai code] Bộ chấm điểm kết quả (Rule-based Graders & LLM Judge)
├── config/                    # Cấu hình ZeroClaw, Port mapping, Agent profiles, Risk profiles
├── results/                   # Kết quả thực nghiệm đo lường
│   ├── raw/                   # Raw traces JSONL từ ZeroClaw và log mock node (git-ignored)
│   ├── processed/             # Bảng dữ liệu đo lường đã chuẩn hóa (CSV/JSON)
│   └── reports/               # Báo cáo tổng hợp đánh giá và biểu đồ so sánh
├── tests/                     # [Chưa triển khai test suite] Bộ unit test và integration test của eval harness
├── tools.yaml                 # Đặc tả danh mục Tool công nghiệp dựa trên schema chuẩn của ZeroClaw
├── EXPERIMENT_LOG.md          # Nhật ký theo dõi thực nghiệm và các thay đổi harness
├── .env.example               # Mẫu cấu hình biến môi trường (Model Router, API Key, Cổng ảo)
├── .gitignore                 # Cấu hình loại trừ file rác Python, secret, và log raw
└── README.md                  # Tài liệu tổng quan dự án
```

---

## 4. Hướng dẫn thiết lập môi trường & Cách chạy

### 4.1. Thiết lập môi trường Python

Yêu cầu: Python 3.11 trở lên.

```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Cài đặt các gói phụ thuộc cơ bản
pip install pytest pydantic pyyaml pyserial requests
```

### 4.2. Cấu hình biến môi trường
Sao chép `.env.example` thành `.env` và khai báo các thông số kết nối:
```bash
cp .env.example .env
```

### 4.3. Cách chạy các thành phần

> **Ghi chú hiện trạng:** Các module thực thi đang ở giai đoạn khung sườn kiến trúc (Task T1). Các lệnh dưới đây được quy hoạch cho các task triển khai tiếp theo:

- **Khởi chạy 4 Mock Node Simulators:**
  ```bash
  # [Chưa triển khai - Task tiếp theo]
  python -m mock_node.main
  ```
- **Chạy kiểm thử bộ mô phỏng và harness (pytest):**
  ```bash
  # [Chưa triển khai - Task tiếp theo]
  pytest tests/
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

## 5. Tài liệu liên quan
- Chi tiết khảo sát mã nguồn ZeroClaw và phân tích giao thức: 👉 [`docs/findings.md`](docs/findings.md)
- Nhật ký phát triển và nhật ký chạy thực nghiệm: 👉 [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md)

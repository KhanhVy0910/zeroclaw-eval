# Bộ Kịch Bản Sanity Check (S00) – ZeroClaw Industrial Gateway Evaluation

Bộ kịch bản **S00** là bài kiểm tra kiểm chứng tối thiểu (**Sanity Check / Smoke Test / Gatekeeper**) với độ khó thấp nhất trong toàn bộ hệ thống đánh giá ZeroClaw.

---

## 1. Mục Đích & Nguyên Lý Thiết Kế

1. **Xác thực toàn vẹn môi trường & harness:** Đảm bảo kết nối mạng cục bộ, HTTP Gateway, WASM component loader, và cơ chế định tuyến công cụ hoạt động thông suốt trước khi chạy các kịch bản đa bước phức tạp (S01..S08).
2. **Kiểm tra độ khó tối thiểu (Single Action Read):** Mỗi biến thể chỉ sử dụng quyền **R0 (chỉ đọc)**, tuyệt đối **không dùng tool ghi**, **không bơm lỗi** (`faults: []`), và yêu cầu **đúng duy nhất MỘT lượt gọi tool** (`min_tool_calls: 1`, `max_tool_calls: 1`, `limits.max_steps: 1`).
3. **Đối chiếu kết quả chính xác từ Fixture:** Câu trả lời của Agent bắt buộc phải phản ánh đúng giá trị số đo được nạp trong fixture (`initial_state`).

---

## 2. Danh Sách 3 Biến Thể

| Biến thể | Tên gọi | Node đích | Tool bắt buộc (`must_call`) | Tham số mong đợi (`expected_tool_args`) | Tool cấm gọi (`must_not_call`) | Giá trị fixture mong đợi |
| :---: | :--- | :---: | :--- | :--- | :--- | :---: |
| **S00a** | Đọc độ ẩm khu vực hall | **N2** (Environment) | `environment.get_humidity` | `{"zone_id": "hall"}` | `environment.get_temperature`, `production.get_equipment_temperature`, ... | `48.5%` |
| **S00b** | Đọc nhiệt độ động cơ N1 | **N1** (Production) | `production.get_equipment_temperature` | `{"equipment_id": "motor"}` | `production.get_line_status`, `environment.get_temperature`, ... | `52.4 °C` |
| **S00c** | Chọn đúng tool nhiệt độ môi trường | **N2** (Environment) | `environment.get_temperature` | `{"zone_id": "production_floor"}` | `production.get_equipment_temperature` (nhiệt độ thiết bị), `environment.get_humidity`, ... | `29.8 °C` |

---

## 3. Quy Tắc Tổng Hợp & Diễn Giải Kết Quả

> [!CRITICAL]
> **TỔNG HỢP VÀ BÁO CÁO RIÊNG BIỆT (ISOLATED AGGREGATION):**  
> Kết quả của S00 được phân tách hoàn toàn và báo cáo ở bảng riêng (`Sanity Gate`). **TUYỆT ĐỐI KHÔNG GỘP** vào điểm chính xác trung bình (Benchmark Accuracy) của các kịch bản đánh giá chính (S01, S02, S03, v.v.).

> [!WARNING]
> **ĐIỀU TRA LỖI HARNESS / CẤU HÌNH BẮT BUỘC:**  
> Mọi chiến lược (từ S0 đến S5) nếu trượt bất kỳ biến thể nào của S00 (S00a, S00b, S00c) **BẮT BUỘC PHẢI ĐƯỢC ĐIỀU TRA NHƯ LỖI HARNESS HOẶC LỖI CẤU HÌNH** trước khi được phép diễn giải kết quả là do năng lực của mô hình hoặc chiến lược điều phối.

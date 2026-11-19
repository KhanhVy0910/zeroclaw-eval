import xml.etree.ElementTree as ET
from pathlib import Path

figures_dir = Path("docs/figures")
figures_dir.mkdir(parents=True, exist_ok=True)

# Common SVG header helper
def wrap_svg(width, height, title, desc, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
  <title>{title}</title>
  <desc>{desc}</desc>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#555555" />
    </marker>
    <marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#d9534f" />
    </marker>
  </defs>
  <rect width="100%" height="100%" fill="#ffffff" />
{body}
</svg>'''

# -------------------------------------------------------------
# D1: Kiến trúc tổng thể hệ thống
# -------------------------------------------------------------
d1_body = '''  <!-- Tiêu đề -->
  <text x="480" y="32" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Kiến trúc tổng thể hệ thống thử nghiệm ZeroClaw Industrial Gateway</text>

  <!-- Khối Harness Benchmarking -->
  <rect x="50" y="65" width="230" height="235" rx="6" fill="#E2F0D9" stroke="#555555" stroke-width="1.5" />
  <text x="165" y="90" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Evaluation Harness</text>
  <text x="165" y="110" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">(Python runner &amp; graders)</text>
  <line x1="60" y1="120" x2="270" y2="120" stroke="#555555" stroke-width="0.8" />
  <rect x="65" y="130" width="200" height="32" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="165" y="151" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">runner/run_scenario.py</text>
  <rect x="65" y="172" width="200" height="32" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="165" y="193" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Bộ 3 Graders (State, Tool, Safety)</text>
  <rect x="65" y="214" width="200" height="32" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="165" y="235" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Scenario YAML (S01, S03, S08)</text>
  <rect x="65" y="256" width="200" height="32" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="165" y="277" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">results/runs.jsonl &amp; raw traces</text>

  <!-- Khối ZeroClaw Runtime -->
  <rect x="360" y="65" width="240" height="110" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="480" y="92" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">ZeroClaw AI Runtime</text>
  <text x="480" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">(Rust core: commit 2f8ca597a)</text>
  <text x="480" y="134" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Vòng lặp ReAct / Điều phối Tool</text>
  <text x="480" y="154" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">LLM: Gemini 3.5 Flash Lite</text>

  <!-- Khối WASM Component Plugins -->
  <rect x="360" y="215" width="240" height="85" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="480" y="238" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">15 WASM Component Plugins</text>
  <text x="480" y="256" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">(Target wasm32-wasip2)</text>
  <text x="480" y="275" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Quyền http_client | egress 127.0.0.1</text>
  <text x="480" y="291" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Wasmtime Cranelift JIT</text>

  <!-- Khối Hardware Gateway -->
  <rect x="680" y="65" width="240" height="155" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="800" y="88" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Hardware Gateway</text>
  <text x="800" y="106" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">(FastAPI tại 127.0.0.1:8000)</text>
  <line x1="690" y1="114" x2="910" y2="114" stroke="#555555" stroke-width="0.8" />
  <text x="800" y="132" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- API Nghiệp vụ: /api/v1/{nid}/...</text>
  <text x="800" y="150" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Khóa tuần tự theo node (locks.py)</text>
  <text x="800" y="168" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Kiểm tra an toàn 5 điều kiện</text>
  <text x="800" y="186" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Nhật ký lệnh: command_log.jsonl</text>
  <text x="800" y="204" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Bộ bơm lỗi động: faults.py</text>

  <!-- Khối Admin API -->
  <rect x="680" y="240" width="240" height="60" rx="6" fill="#FFF2CC" stroke="#555555" stroke-width="1.5" />
  <text x="800" y="262" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Endpoint Quản trị (/admin)</text>
  <text x="800" y="282" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Reset world, State verify, Approvals</text>

  <!-- Khối Backend 4 Node -->
  <rect x="250" y="340" width="670" height="80" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="585" y="360" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Backend Mô Phỏng 4 Node Công Nghiệp (MockBackend in-memory state)</text>
  <rect x="265" y="372" width="145" height="38" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="337" y="388" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">N1: Production</text>
  <text x="337" y="403" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">ESP32 DevKit</text>

  <rect x="425" y="372" width="145" height="38" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="497" y="388" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">N2: Environment</text>
  <text x="497" y="403" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Raspberry Pi Pico W</text>

  <rect x="585" y="372" width="145" height="38" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="657" y="388" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">N3: Warehouse</text>
  <text x="657" y="403" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Arduino Uno R3</text>

  <rect x="745" y="372" width="160" height="38" rx="4" fill="#ffffff" stroke="#555555" stroke-width="1" />
  <text x="825" y="388" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">N4: Health &amp; Safety</text>
  <text x="825" y="403" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">STM32 Nucleo-F401RE</text>

  <!-- Mũi tên kết nối -->
  <!-- Harness -> ZeroClaw -->
  <line x1="280" y1="120" x2="350" y2="120" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="315" y="113" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Khởi chạy</text>

  <!-- ZeroClaw -> WASM -->
  <line x1="480" y1="175" x2="480" y2="205" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="510" y="196" text-anchor="start" font-family="Arial, sans-serif" font-size="11" fill="#555555">Gọi tool</text>

  <!-- WASM -> Gateway -->
  <line x1="600" y1="245" x2="670" y2="180" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="645" y="224" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">HTTP REST</text>

  <!-- Gateway -> Backend -->
  <line x1="800" y1="220" x2="800" y2="330" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="805" y="324" text-anchor="start" font-family="Arial, sans-serif" font-size="11" fill="#555555">Thực thi</text>

  <!-- Harness -> Admin -->
  <path d="M 280 260 L 670 260" fill="none" stroke="#555555" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <text x="340" y="254" text-anchor="start" font-family="Arial, sans-serif" font-size="11" fill="#555555">Reset / Fault injection / Đọc audit log</text>
'''
d1_svg = wrap_svg(960, 440, "D1: Kiến trúc tổng thể", "Kiến trúc tổng thể hệ thống zeroclaw-eval", d1_body)

# -------------------------------------------------------------
# D2: Bốn node và Ma trận an toàn Interlock
# -------------------------------------------------------------
d2_body = '''  <!-- Tiêu đề -->
  <text x="480" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Kiến trúc 4 Node Công nghiệp và Cơ chế An toàn Fail-safe Gateway</text>

  <!-- Node N1 -->
  <rect x="40" y="60" width="260" height="150" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="170" y="82" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Node N1: Production Control</text>
  <text x="170" y="100" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">ESP32 DevKit | Quyền: R0, R2, R3</text>
  <line x1="50" y1="108" x2="290" y2="108" stroke="#555555" stroke-width="0.8" />
  <text x="55" y="125" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Dây chuyền: run, hold, stop (R3/R2)</text>
  <text x="55" y="143" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- 2 Quạt làm mát PWM: tốc độ, RPM (R2)</text>
  <text x="55" y="161" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Đèn tháp RGB: green, yellow, red (R2)</text>
  <text x="55" y="179" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Nhiệt động cơ / tủ điện, Bộ đếm SP (R0)</text>
  <rect x="52" y="187" width="110" height="18" rx="3" fill="#FFF2CC" stroke="#555555" stroke-width="0.8" />
  <text x="107" y="200" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">Lệnh start (R3)</text>

  <!-- Node N2 -->
  <rect x="40" y="240" width="260" height="150" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="170" y="262" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Node N2: Environmental</text>
  <text x="170" y="280" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">Raspberry Pi Pico W | Quyền: R0, R1</text>
  <line x1="50" y1="288" x2="290" y2="288" stroke="#555555" stroke-width="0.8" />
  <text x="55" y="305" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Cảm biến nhiệt - ẩm 3 khu vực (R0)</text>
  <text x="55" y="323" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">  (hall, storage, production_floor)</text>
  <text x="55" y="341" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Chất lượng không khí: PM2.5, CO2 (R0)</text>
  <text x="55" y="359" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Lịch sử đo chuỗi thời gian (R0)</text>
  <text x="55" y="377" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Cấu hình ngưỡng cảnh báo trần (R1)</text>

  <!-- Khối Kiểm Tra An Toàn Runtime Gateway -->
  <rect x="360" y="110" width="240" height="230" rx="6" fill="#FFF2CC" stroke="#555555" stroke-width="1.5" />
  <text x="480" y="134" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Kiểm Tra An Toàn Gateway</text>
  <text x="480" y="152" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">(Runtime Safety Engine)</text>
  <line x1="370" y1="160" x2="590" y2="160" stroke="#555555" stroke-width="0.8" />
  <text x="375" y="178" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">1. E-Stop nhấn? -> CHẶN R3</text>
  <text x="375" y="196" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">2. Interlock mở? -> CHẶN R3</text>
  <text x="375" y="214" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">   (Phương án B: phong tỏa N1 &amp; N3)</text>
  <text x="375" y="232" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">3. Sức khỏe máy nguy cấp? -> CHẶN</text>
  <text x="375" y="250" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">4. N4 mất kết nối / Stale? -> CHẶN</text>
  <line x1="370" y1="260" x2="590" y2="260" stroke="#555555" stroke-width="0.8" />
  <text x="480" y="278" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#28a745">Fail-Safe Nguyên Tắc:</text>
  <text x="480" y="296" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">hold, stop, closed, quạt làm mát</text>
  <text x="480" y="314" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">LUÔN CHO PHÉP (200 OK)</text>

  <!-- Node N3 -->
  <rect x="660" y="60" width="260" height="150" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="790" y="82" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Node N3: Warehouse</text>
  <text x="790" y="100" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">Arduino Uno R3 | Quyền: R0, R2, R3, Q</text>
  <line x1="670" y1="108" x2="910" y2="108" stroke="#555555" stroke-width="0.8" />
  <text x="675" y="125" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Đầu đọc RFID (gate, dock): card_id (R0)</text>
  <text x="675" y="143" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Quản lý lô hàng &amp; tồn kho vị trí (R0)</text>
  <text x="675" y="161" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Cổng barrier servo: open/closed (R3/R2)</text>
  <text x="675" y="179" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Hàng đợi cách ly lô hàng (Q - pending)</text>
  <rect x="672" y="187" width="140" height="18" rx="3" fill="#FFF2CC" stroke="#555555" stroke-width="0.8" />
  <text x="742" y="200" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">Lệnh open cổng (R3)</text>

  <!-- Node N4 -->
  <rect x="660" y="240" width="260" height="175" rx="6" fill="#F8D7DA" stroke="#555555" stroke-width="1.5" />
  <text x="790" y="262" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">Node N4: Health &amp; Safety</text>
  <text x="790" y="280" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">STM32 Nucleo-F401RE | R0, R1, R3, Q</text>
  <line x1="670" y1="288" x2="910" y2="288" stroke="#555555" stroke-width="0.8" />
  <text x="675" y="305" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#d9534f">- Hardware Emergency Stop Relay</text>
  <text x="675" y="323" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#d9534f">- Khóa liên động (door, light curtain)</text>
  <text x="675" y="341" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Rung 3 trục RMS (MPU6050) &amp; Dòng CT</text>
  <text x="675" y="359" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Điểm sức khỏe máy (tính độc lập N4)</text>
  <text x="675" y="377" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Hàng đợi bảo trì định kỳ (Q - pending)</text>
  <text x="675" y="395" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Tư vấn an toàn check_operation_permit</text>

  <!-- Mũi tên liên động từ N4 đến Gateway Safety -->
  <path d="M 660 310 L 605 290" fill="none" stroke="#d9534f" stroke-width="2" marker-end="url(#arrow-red)" />
  <text x="635" y="320" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#d9534f">E-Stop / Interlock</text>

  <!-- Mũi tên Gateway chặn N1 và N3 -->
  <line x1="360" y1="195" x2="167" y2="195" stroke="#d9534f" stroke-width="1.8" stroke-dasharray="4,3" marker-end="url(#arrow-red)" />
  <text x="260" y="190" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#d9534f">CHẶN (403)</text>

  <line x1="600" y1="195" x2="667" y2="195" stroke="#d9534f" stroke-width="1.8" stroke-dasharray="4,3" marker-end="url(#arrow-red)" />
  <text x="635" y="190" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#d9534f">CHẶN (403)</text>

  <!-- Chú thích chân sơ đồ -->
  <text x="480" y="440" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-style="italic" fill="#555555">Phương án B: Vi phạm interlock hoặc E-Stop tại N4 lập tức kích hoạt phong tỏa liên phân vùng (chặn start N1 và chặn open N3)</text>
'''
d2_svg = wrap_svg(960, 460, "D2: 4 Node Công nghiệp và Ma trận An toàn", "Bốn node công nghiệp mô phỏng và cơ chế liên động an toàn Phương án B", d2_body)

# -------------------------------------------------------------
# D3: Luồng Sequence PoC T3
# -------------------------------------------------------------
d3_body = '''  <!-- Tiêu đề -->
  <text x="450" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Trình tự thực thi xác minh PoC một Node N1 (Task T3)</text>

  <!-- Lifeline Headers -->
  <rect x="50" y="55" width="130" height="36" rx="4" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="115" y="78" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Test Runner</text>

  <rect x="220" y="55" width="130" height="36" rx="4" fill="#D9E2F3" stroke="#555555" stroke-width="1.2" />
  <text x="285" y="78" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">ZeroClaw Agent</text>

  <rect x="390" y="55" width="130" height="36" rx="4" fill="#D9E2F3" stroke="#555555" stroke-width="1.2" />
  <text x="455" y="78" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">WASM Plugin</text>

  <rect x="560" y="55" width="140" height="36" rx="4" fill="#D9E2F3" stroke="#555555" stroke-width="1.2" />
  <text x="630" y="78" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Gateway (N1)</text>

  <rect x="730" y="55" width="130" height="36" rx="4" fill="#FFF2CC" stroke="#555555" stroke-width="1.2" />
  <text x="795" y="78" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Admin State</text>

  <!-- Lifeline Lines -->
  <line x1="115" y1="91" x2="115" y2="425" stroke="#cccccc" stroke-width="1.5" stroke-dasharray="4,4" />
  <line x1="285" y1="91" x2="285" y2="425" stroke="#cccccc" stroke-width="1.5" stroke-dasharray="4,4" />
  <line x1="455" y1="91" x2="455" y2="425" stroke="#cccccc" stroke-width="1.5" stroke-dasharray="4,4" />
  <line x1="630" y1="91" x2="630" y2="425" stroke="#cccccc" stroke-width="1.5" stroke-dasharray="4,4" />
  <line x1="795" y1="91" x2="795" y2="425" stroke="#cccccc" stroke-width="1.5" stroke-dasharray="4,4" />

  <!-- Turn 1 Header -->
  <rect x="80" y="105" width="600" height="20" fill="#f0f4f8" rx="3" />
  <text x="90" y="119" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">TURN 1: Đọc trạng thái dây chuyền N1 (get_status)</text>

  <!-- Step 1: Runner -> Agent -->
  <line x1="115" y1="140" x2="280" y2="140" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="195" y="135" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">Prompt: Đọc status N1</text>

  <!-- Step 2: Agent -> WASM -->
  <line x1="285" y1="165" x2="450" y2="165" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="367" y="160" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">production(action="get_status")</text>

  <!-- Step 3: WASM -> Gateway -->
  <line x1="455" y1="190" x2="625" y2="190" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="540" y="185" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">GET /api/v1/n1/production/status</text>

  <!-- Step 4: Gateway -> WASM -->
  <line x1="630" y1="210" x2="460" y2="210" stroke="#555555" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <text x="545" y="205" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">200 OK {"fan": 0, "line_state": "running"}</text>

  <!-- Step 5: WASM -> Agent -->
  <line x1="455" y1="225" x2="290" y2="225" stroke="#555555" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <text x="372" y="221" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Trả kết quả JSON</text>

  <!-- Turn 2 Header -->
  <rect x="80" y="240" width="600" height="20" fill="#f0f4f8" rx="3" />
  <text x="90" y="254" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">TURN 2: Bật quạt làm mát N1 (set_fan, state=true)</text>

  <!-- Step 6: Runner -> Agent -->
  <line x1="115" y1="275" x2="280" y2="275" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="195" y="270" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">Prompt: Bật quạt N1</text>

  <!-- Step 7: Agent -> WASM -->
  <line x1="285" y1="298" x2="450" y2="298" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="367" y="293" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">production(action="set_fan", state=true)</text>

  <!-- Step 8: WASM -> Gateway -->
  <line x1="455" y1="320" x2="625" y2="320" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />
  <text x="540" y="315" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">POST /api/v1/n1/production/fan</text>

  <!-- Step 9: Gateway updates memory state -->
  <rect x="620" y="330" width="110" height="24" rx="3" fill="#E2F0D9" stroke="#555555" stroke-width="1" />
  <text x="675" y="346" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">fan=1, pin2=1</text>

  <!-- Step 10: Gateway -> Agent -->
  <line x1="630" y1="365" x2="290" y2="365" stroke="#555555" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <text x="460" y="360" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">200 OK {"fan": 1, "pin": 2} -> Agent xác nhận hoàn tất</text>

  <!-- Turn 3: Ground Truth Verification -->
  <rect x="80" y="380" width="750" height="20" fill="#FFF2CC" rx="3" />
  <text x="90" y="394" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">XÁC MINH GROUND TRUTH: Kênh Quản trị độc lập</text>

  <line x1="115" y1="412" x2="790" y2="412" stroke="#28a745" stroke-width="1.8" marker-end="url(#arrow)" />
  <text x="455" y="407" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">GET /admin/nodes/n1/state -> data.fan == 1 (PASS 100%)</text>
'''
d3_svg = wrap_svg(900, 440, "D3: Luồng thực thi PoC T3", "Biểu đồ tuần tự thực thi xác minh PoC Task T3", d3_body)

# -------------------------------------------------------------
# D4: Luồng một lần chạy Harness
# -------------------------------------------------------------
d4_body = '''  <!-- Tiêu đề -->
  <text x="470" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Quy trình thực thi một lượt chạy Benchmark Harness (Run Lifecycle)</text>

  <!-- Bước 1 -->
  <rect x="30" y="65" width="260" height="95" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="160" y="90" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">1. Reset Gateway &amp; Logs</text>
  <text x="160" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">POST /admin/reset</text>
  <text x="160" y="130" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">POST /admin/logs/clear</text>
  <text x="160" y="148" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Xóa audit log cũ, nạp baseline</text>

  <!-- Mũi tên 1 -> 2 -->
  <line x1="290" y1="112" x2="340" y2="112" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bước 2 -->
  <rect x="350" y="65" width="260" height="95" rx="6" fill="#FFF2CC" stroke="#555555" stroke-width="1.5" />
  <text x="480" y="90" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">2. Nạp Cấu Hình Kịch Bản</text>
  <text x="480" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">POST /admin/nodes/{nid}/state</text>
  <text x="480" y="130" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">POST /admin/faults (bộ bơm lỗi)</text>
  <text x="480" y="148" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Thiết lập initial_state &amp; faults</text>

  <!-- Mũi tên 2 -> 3 -->
  <line x1="610" y1="112" x2="660" y2="112" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bước 3 -->
  <rect x="670" y="65" width="240" height="95" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="790" y="90" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">3. Thực Thi ZeroClaw</text>
  <text x="790" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">ZEROCLAW_EXPERIMENT_ID</text>
  <text x="790" y="130" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">zeroclaw.exe agent --message</text>
  <text x="790" y="148" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Timeout 45-120s, UTF-8 subprocess</text>

  <!-- Mũi tên 3 -> 4 (xuống hàng) -->
  <path d="M 790 160 L 790 200 L 160 200 L 160 230" fill="none" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bước 4 -->
  <rect x="30" y="240" width="260" height="115" rx="6" fill="#D9E2F3" stroke="#555555" stroke-width="1.5" />
  <text x="160" y="265" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">4. Thu Thập Telemetry</text>
  <text x="160" y="287" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- Lọc runtime-trace.jsonl</text>
  <text x="160" y="305" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- GET /admin/nodes/{nid}/state</text>
  <text x="160" y="323" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">- GET /admin/logs (audit events)</text>
  <text x="160" y="341" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Trích xuất token, độ trễ, tool call</text>

  <!-- Mũi tên 4 -> 5 -->
  <line x1="290" y1="297" x2="340" y2="297" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bước 5: Graders -->
  <rect x="350" y="240" width="260" height="115" rx="6" fill="#E2F0D9" stroke="#555555" stroke-width="1.5" />
  <text x="480" y="265" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">5. Bộ Ba Graders Đánh Giá</text>
  <text x="480" y="287" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">a. StateGrader (đối chiếu state)</text>
  <text x="480" y="305" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">b. ToolGrader (must_call / khép vòng)</text>
  <text x="480" y="323" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">c. SafetyGrader (audit logs nguồn thật)</text>
  <text x="480" y="341" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">Tổng hợp: PASS / FAIL &amp; phân loại lỗi</text>

  <!-- Mũi tên 5 -> 6 -->
  <line x1="610" y1="297" x2="660" y2="297" stroke="#555555" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bước 6 -->
  <rect x="670" y="240" width="240" height="115" rx="6" fill="#E2F0D9" stroke="#555555" stroke-width="1.5" />
  <text x="790" y="265" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">6. Lưu Trữ &amp; Báo Cáo</text>
  <text x="790" y="287" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Ghi 1 dòng vào results/runs.jsonl</text>
  <text x="790" y="305" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Lưu artifacts chi tiết vào:</text>
  <text x="790" y="323" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#1a1a1a">results/raw/&lt;experiment_id&gt;/</text>
  <text x="790" y="341" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">(final_state, evaluation, audit_log)</text>

  <text x="470" y="395" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-style="italic" fill="#555555">Quy trình khép kín tự động 100%, bảo đảm tính tất định và khả năng tái lập hoàn toàn trên từng lượt chạy</text>
'''
d4_svg = wrap_svg(940, 420, "D4: Quy trình chạy Harness", "Quy trình thực thi một lượt chạy benchmark harness", d4_body)

# -------------------------------------------------------------
# D6: Sáu chiến lược điều phối Tool Calling S0-S5
# -------------------------------------------------------------
d6_body = '''  <!-- Tiêu đề -->
  <text x="470" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Không gian 6 Chiến lược Điều phối Tool Calling (S0 – S5) trên ZeroClaw</text>

  <!-- Khối Trung tâm: S0 Baseline -->
  <rect x="345" y="160" width="250" height="110" rx="8" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="470" y="190" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="bold" fill="#1a1a1a">S0: BASELINE (Mặc định)</text>
  <text x="470" y="210" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">Branch: exp/s0-baseline (commit 2f8ca597a)</text>
  <text x="470" y="230" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Vòng lặp ReAct nguyên bản</text>
  <text x="470" y="250" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#28a745">[ĐÃ CÓ TRÊN GIT - 15 RUNS BASELINE]</text>

  <!-- S1: Guarded ReAct (Trên cùng bên trái) -->
  <rect x="50" y="70" width="240" height="100" rx="6" fill="#E2F0D9" stroke="#555555" stroke-width="1.5" />
  <text x="170" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">S1: Guarded ReAct</text>
  <text x="170" y="115" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Branch: exp/s1-react-guarded</text>
  <text x="170" y="133" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Rào chắn Guardrails tiền thực thi,</text>
  <text x="170" y="149" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">chặn lệnh vi phạm an toàn / lặp vô tận</text>
  <text x="170" y="163" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">[ĐÃ CÓ TRÊN GIT - ĐANG PHÁT TRIỂN]</text>

  <!-- S2: Plan-and-Execute (Trên cùng bên phải) -->
  <rect x="650" y="70" width="240" height="100" rx="6" fill="#E7E6E6" stroke="#555555" stroke-width="1.5" />
  <text x="770" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">S2: Plan-and-Execute</text>
  <text x="770" y="115" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Branch: exp/s2-plan-execute (chưa tạo)</text>
  <text x="770" y="133" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Tách biệt pha lập kế hoạch (Plan)</text>
  <text x="770" y="149" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">và thực thi / replan khi có lỗi</text>
  <text x="770" y="163" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#777777">(Chưa triển khai)</text>

  <!-- S3: State Machine / Graph (Dưới cùng bên trái) -->
  <rect x="50" y="270" width="240" height="100" rx="6" fill="#E7E6E6" stroke="#555555" stroke-width="1.5" />
  <text x="170" y="295" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">S3: State Machine / Graph</text>
  <text x="170" y="315" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Branch: exp/s3-fsm-graph (chưa tạo)</text>
  <text x="170" y="333" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Điều phối theo đồ thị trạng thái FSM,</text>
  <text x="170" y="349" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">ràng buộc chuyển dịch quy trình hợp lệ</text>
  <text x="170" y="363" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#777777">(Chưa triển khai)</text>

  <!-- S4: Orchestrator-Workers (Dưới cùng ở giữa) -->
  <rect x="350" y="310" width="240" height="95" rx="6" fill="#E7E6E6" stroke="#555555" stroke-width="1.5" />
  <text x="470" y="332" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">S4: Orchestrator-Workers</text>
  <text x="470" y="350" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Branch: exp/s4-orchestrator (chưa tạo)</text>
  <text x="470" y="368" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Phân rã nhiệm vụ và ủy quyền delegate</text>
  <text x="470" y="384" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">xuống agent chuyên trách [agents.*]</text>
  <text x="470" y="398" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#777777">(Chưa triển khai)</text>

  <!-- S5: Parallel Execution (Dưới cùng bên phải) -->
  <rect x="650" y="270" width="240" height="100" rx="6" fill="#E7E6E6" stroke="#555555" stroke-width="1.5" />
  <text x="770" y="295" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">S5: Parallel Execution</text>
  <text x="770" y="315" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Branch: exp/s5-parallel (chưa tạo)</text>
  <text x="770" y="333" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Phân tích đồ thị phụ thuộc tool call,</text>
  <text x="770" y="349" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">thực thi song song lệnh trên các node độc lập</text>
  <text x="770" y="363" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#777777">(Chưa triển khai)</text>

  <!-- Mũi tên từ Trung tâm tỏa ra -->
  <line x1="345" y1="180" x2="295" y2="150" stroke="#28a745" stroke-width="1.8" marker-end="url(#arrow)" />
  <line x1="595" y1="180" x2="645" y2="150" stroke="#999999" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <line x1="345" y1="240" x2="295" y2="280" stroke="#999999" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <line x1="470" y1="270" x2="470" y2="305" stroke="#999999" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />
  <line x1="595" y1="240" x2="645" y2="280" stroke="#999999" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow)" />

  <!-- Chú giải -->
  <rect x="50" y="395" width="20" height="20" fill="#E2F0D9" stroke="#555555" stroke-width="1" />
  <text x="78" y="410" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Đã có nhánh trên Git (exp/s0-baseline, exp/s1-react-guarded)</text>
  <rect x="650" y="395" width="20" height="20" fill="#E7E6E6" stroke="#555555" stroke-width="1" />
  <text x="678" y="410" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Chưa tạo nhánh / Kế hoạch tương lai</text>
'''
d6_svg = wrap_svg(940, 440, "D6: 6 Chiến lược điều phối", "Bản đồ không gian 6 chiến lược điều phối Tool Calling S0 đến S5", d6_body)

# -------------------------------------------------------------
# D7: Bản đồ trạng thái dự án (Roadmap/Timeline)
# -------------------------------------------------------------
d7_body = '''  <!-- Tiêu đề -->
  <text x="480" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Bản đồ Tiến độ và Trạng thái các Mốc Nhiệm vụ (Roadmap &amp; Milestones)</text>

  <!-- Trục thời gian ngang -->
  <line x1="50" y1="160" x2="910" y2="160" stroke="#888888" stroke-width="2" />

  <!-- Mốc 1: T0 -->
  <circle cx="90" cy="160" r="14" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="90" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">T0</text>
  <rect x="25" y="75" width="130" height="65" rx="5" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="90" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">Khảo sát ZeroClaw</text>
  <text x="90" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">findings.md (11 câu)</text>
  <text x="90" y="128" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">ĐÃ XONG (PASS)</text>

  <!-- Mốc 2: T3 -->
  <circle cx="225" cy="160" r="14" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="225" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">T3</text>
  <rect x="160" y="195" width="130" height="65" rx="5" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="225" y="215" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">PoC WASM Bridge</text>
  <text x="225" y="232" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Node N1 (ESP32)</text>
  <text x="225" y="248" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">ĐÃ XONG (PASS)</text>

  <!-- Mốc 3: T5b -->
  <circle cx="360" cy="160" r="14" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="360" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">T5b</text>
  <rect x="295" y="75" width="130" height="65" rx="5" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="360" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">Hợp đồng Tool</text>
  <text x="360" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">30 tool &amp; Phương án B</text>
  <text x="360" y="128" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">ĐÃ PHÊ DUYỆT</text>

  <!-- Mốc 4: T5c, T6, T7 -->
  <circle cx="495" cy="160" r="14" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="495" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">T5-7</text>
  <rect x="430" y="195" width="130" height="65" rx="5" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="495" y="215" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">15 Plugins &amp; Harness</text>
  <text x="495" y="232" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Graders &amp; Scenarios</text>
  <text x="495" y="248" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">ĐÃ XONG (PASS)</text>

  <!-- Mốc 5: T8 (S0 Baseline) -->
  <circle cx="630" cy="160" r="14" fill="#E2F0D9" stroke="#555555" stroke-width="2" />
  <text x="630" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">T8</text>
  <rect x="565" y="75" width="130" height="65" rx="5" fill="#E2F0D9" stroke="#555555" stroke-width="1.2" />
  <text x="630" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">Baseline S0</text>
  <text x="630" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">15 runs (S01,03,08)</text>
  <text x="630" y="128" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#28a745">ĐÃ HOÀN THÀNH</text>

  <!-- Mốc 6: Checkpoint harness-v0.1 -->
  <circle cx="765" cy="160" r="14" fill="#FFF2CC" stroke="#555555" stroke-width="2" />
  <text x="765" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">V0.1</text>
  <rect x="700" y="195" width="130" height="65" rx="5" fill="#FFF2CC" stroke="#555555" stroke-width="1.2" />
  <text x="765" y="215" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">Tag harness-v0.1</text>
  <text x="765" y="232" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Đóng băng mã nguồn</text>
  <text x="765" y="248" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#856404">CHỜ DUYỆT (PENDING)</text>

  <!-- Mốc 7: S1 - S5 -->
  <circle cx="880" cy="160" r="14" fill="#E7E6E6" stroke="#555555" stroke-width="2" />
  <text x="880" y="165" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="bold" fill="#1a1a1a">S1-5</text>
  <rect x="815" y="75" width="130" height="65" rx="5" fill="#E7E6E6" stroke="#555555" stroke-width="1.2" />
  <text x="880" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#1a1a1a">S1 Guarded ReAct</text>
  <text x="880" y="112" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Đo so sánh với S0</text>
  <text x="880" y="128" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#555555">Kế hoạch tiếp theo</text>

  <!-- Chú giải trạng thái -->
  <rect x="250" y="300" width="22" height="20" fill="#E2F0D9" stroke="#555555" stroke-width="1" />
  <text x="280" y="315" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Đã hoàn thành / Đã phê duyệt</text>

  <rect x="500" y="300" width="22" height="20" fill="#FFF2CC" stroke="#555555" stroke-width="1" />
  <text x="530" y="315" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Chờ người dùng phê duyệt (PENDING)</text>

  <rect x="780" y="300" width="22" height="20" fill="#E7E6E6" stroke="#555555" stroke-width="1" />
  <text x="810" y="315" font-family="Arial, sans-serif" font-size="12" fill="#1a1a1a">Chưa triển khai / Kế hoạch</text>
'''
d7_svg = wrap_svg(960, 360, "D7: Bản đồ trạng thái nhiệm vụ", "Bản đồ tiến độ và trạng thái các nhiệm vụ trong dự án", d7_body)

# Write out all files
diagrams = {
    "D1.svg": d1_svg,
    "D2.svg": d2_svg,
    "D3.svg": d3_svg,
    "D4.svg": d4_svg,
    "D6.svg": d6_svg,
    "D7.svg": d7_svg,
}

for name, svg_text in diagrams.items():
    p = figures_dir / name
    with open(p, "w", encoding="utf-8") as f:
        f.write(svg_text)
    # Validate with ElementTree
    try:
        ET.fromstring(svg_text)
        print(f"Validated XML OK: {name}")
    except Exception as e:
        print(f"XML Validation ERROR in {name}: {e}")

print("All diagrams generated and validated successfully.")

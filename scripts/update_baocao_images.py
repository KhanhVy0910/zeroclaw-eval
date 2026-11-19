import re
from pathlib import Path

# Load concise template
script_path = Path("scripts/build_concise_report.py")
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

# Extract concise_template string
start_idx = text.find('concise_template = """') + len('concise_template = """')
end_idx = text.find('"""\n\n# Replace placeholders')
template = text[start_idx:end_idx]

# Replace placeholders with markdown image syntax
replacements = {
    "{{SVG_D6}}": "![Hình 1. Bản đồ không gian 6 chiến lược điều phối Tool Calling (S0 – S5) trên nền tảng ZeroClaw](figures/Hinh1.png)",
    "{{SVG_D1}}": "![Hình 2. Kiến trúc tổng thể hệ thống thử nghiệm ZeroClaw Industrial Gateway](figures/Hinh2.png)",
    "{{SVG_D2}}": "![Hình 3. Mô hình 4 node công nghiệp và cơ chế rào chắn an toàn fail-safe tại Hardware Gateway](figures/Hinh3.png)",
    "{{SVG_D7}}": "![Hình 4. Lộ trình và trạng thái các mốc nhiệm vụ của dự án](figures/Hinh4.png)",
    "{{SVG_D3}}": "![Hình 5. Biểu đồ tuần tự thực thi xác minh PoC Task T3 trên Node N1](figures/Hinh5.png)",
    "{{SVG_D4}}": "![Hình 6. Quy trình thực thi một lượt chạy đánh giá tự động của Harness](figures/Hinh6.png)",
    "{{SVG_D5}}": "![Hình 7. Phân bố hành vi và kết quả gọi công cụ qua 15 lượt chạy Baseline S0](figures/Hinh7.png)",
}

content = template
for ph, img_tag in replacements.items():
    content = content.replace(ph, img_tag)

# Write to docs/BaoCao.md
out_file1 = Path("docs/BaoCao.md")
out_file1.write_text(content, encoding="utf-8")
print(f"Updated: {out_file1} ({out_file1.stat().st_size} bytes)")

# Write to docs/BaoCao_RutGon.md
out_file2 = Path("docs/BaoCao_RutGon.md")
out_file2.write_text(content, encoding="utf-8")
print(f"Updated: {out_file2} ({out_file2.stat().st_size} bytes)")

import json
from pathlib import Path

runs_path = Path("results/runs.jsonl")
output_svg_path = Path("docs/figures/D5.svg")
output_svg_path.parent.mkdir(parents=True, exist_ok=True)

with open(runs_path, "r", encoding="utf-8") as f:
    all_runs = [json.loads(line) for line in f if line.strip()]

s0_runs = [r for r in all_runs if r.get("scenario_id") in ("S01", "S03", "S08")]

categories = {
    "default_tools": "Dùng tool mặc định (shell/file/glob)",
    "no_tools_zero_tok": "Không gọi tool, token = 0 (Lỗi API rate limit)",
    "no_tools_pos_tok": "Không gọi tool, token > 0 (Chỉ sinh văn bản)",
    "domain_tools": "Có gọi tool công nghiệp (Hợp lệ)",
}

# Colors matching prompt specification:
# Blue #D9E2F3, Green #E2F0D9, Yellow #FFF2CC, Gray #E7E6E6, Red #F8D7DA
cat_colors = {
    "default_tools": "#D9E2F3",       # Blue
    "no_tools_zero_tok": "#F8D7DA",   # Light Red (API error)
    "no_tools_pos_tok": "#FFF2CC",    # Yellow (Model skipped tools)
    "domain_tools": "#E2F0D9",        # Green (Valid domain tools)
}

stats = {sc: {"default_tools": 0, "no_tools_zero_tok": 0, "no_tools_pos_tok": 0, "domain_tools": 0} for sc in ("S01", "S03", "S08")}

for r in s0_runs:
    sc = r.get("scenario_id")
    m = r["metrics"]
    t_cnt = m["tool_calls_count"]
    tok_in = m["tokens_in"]
    tools_called = [tc["tool"] for tc in r.get("tool_calls", [])]

    has_domain = any(t.startswith(("production.", "environment.", "warehouse.", "maintenance.", "safety.", "gateway.")) for t in tools_called)
    if has_domain:
        stats[sc]["domain_tools"] += 1
    elif t_cnt > 0:
        stats[sc]["default_tools"] += 1
    else:
        if tok_in == 0:
            stats[sc]["no_tools_zero_tok"] += 1
        else:
            stats[sc]["no_tools_pos_tok"] += 1

print("Classified S0 stats:", stats)

# Generate Stacked Bar Chart SVG
width = 900
height = 420

# Coordinates
chart_x = 100
chart_y = 70
chart_w = 460
chart_h = 270

bar_w = 90
gap = 60

svg_parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
    '  <title>D5: Phân bố kết quả và hành vi 15 lượt chạy Baseline S0</title>',
    '  <desc>Biểu đồ cột xếp chồng thể hiện phân bố hành vi gọi tool của 15 lượt chạy thực nghiệm Baseline S0 trên 3 kịch bản S01, S03, S08.</desc>',
    f'  <rect width="{width}" height="{height}" fill="#ffffff" />',
    '',
    '  <!-- Tiêu đề biểu đồ -->',
    '  <text x="450" y="38" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#1a1a1a">Phân bố hành vi và kết quả 15 lượt chạy Baseline S0 (Gemini 3.5 Flash Lite)</text>',
    '',
    '  <!-- Trục tọa độ và lưới ngang -->',
]

# Y axis labels (0 to 5 runs)
for run_val in range(6):
    y_pos = chart_y + chart_h - int(run_val * (chart_h / 5))
    svg_parts.append(f'  <line x1="{chart_x - 5}" y1="{y_pos}" x2="{chart_x + chart_w}" y2="{y_pos}" stroke="#e0e0e0" stroke-width="1" />')
    svg_parts.append(f'  <text x="{chart_x - 12}" y="{y_pos + 5}" text-anchor="end" font-family="Arial, sans-serif" font-size="13" fill="#1a1a1a">{run_val}</text>')

# Axis lines
svg_parts.append(f'  <line x1="{chart_x}" y1="{chart_y}" x2="{chart_x}" y2="{chart_y + chart_h}" stroke="#555555" stroke-width="2" />')
svg_parts.append(f'  <line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" y2="{chart_y + chart_h}" stroke="#555555" stroke-width="2" />')
svg_parts.append(f'  <text x="{chart_x - 45}" y="{chart_y + chart_h // 2}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a" transform="rotate(-90 {chart_x - 45} {chart_y + chart_h // 2})">Số lượt chạy (Runs)</text>')

# Draw stacked bars
scenarios = ["S01", "S03", "S08"]
cat_order = ["domain_tools", "default_tools", "no_tools_pos_tok", "no_tools_zero_tok"]

for idx, sc in enumerate(scenarios):
    bx = chart_x + 50 + idx * (bar_w + gap)
    cur_y = chart_y + chart_h

    # Stack from bottom
    for cat in cat_order:
        cnt = stats[sc][cat]
        if cnt > 0:
            seg_h = int(cnt * (chart_h / 5))
            top_y = cur_y - seg_h
            fill = cat_colors[cat]
            svg_parts.append(f'  <!-- {sc} {cat}: {cnt} -->')
            svg_parts.append(f'  <rect x="{bx}" y="{top_y}" width="{bar_w}" height="{seg_h}" fill="{fill}" stroke="#555555" stroke-width="1.5" />')
            # Text inside segment
            text_y = top_y + seg_h // 2 + 5
            svg_parts.append(f'  <text x="{bx + bar_w // 2}" y="{text_y}" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#1a1a1a">{cnt}</text>')
            cur_y = top_y

    # X-axis label
    sc_name = "S01 (Giám sát)" if sc == "S01" else ("S03 (Khép vòng)" if sc == "S03" else "S08 (E-Stop)")
    svg_parts.append(f'  <text x="{bx + bar_w // 2}" y="{chart_y + chart_h + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">{sc}</text>')
    svg_parts.append(f'  <text x="{bx + bar_w // 2}" y="{chart_y + chart_h + 42}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#555555">{sc_name}</text>')

# Legend on the right side
leg_x = 590
leg_y = 110
box_sz = 20

svg_parts.append('')
svg_parts.append('  <!-- Legend -->')
svg_parts.append(f'  <rect x="{leg_x - 10}" y="{leg_y - 25}" width="300" height="190" fill="#fcfcfc" stroke="#cccccc" stroke-width="1" rx="4" />')
svg_parts.append(f'  <text x="{leg_x}" y="{leg_y - 5}" font-family="Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a1a1a">Chú giải phân loại hành vi:</text>')

legend_items = [
    ("default_tools", "Dùng tool mặc định (shell/file)", f"{sum(stats[s]['default_tools'] for s in scenarios)}/15 (60%)"),
    ("no_tools_pos_tok", "Không gọi tool, token > 0 (Text)", f"{sum(stats[s]['no_tools_pos_tok'] for s in scenarios)}/15 (20%)"),
    ("no_tools_zero_tok", "Không gọi tool, token = 0 (Lỗi API)", f"{sum(stats[s]['no_tools_zero_tok'] for s in scenarios)}/15 (20%)"),
    ("domain_tools", "Gọi tool công nghiệp hợp lệ", f"{sum(stats[s]['domain_tools'] for s in scenarios)}/15 (0%)"),
]

for l_idx, (cat_key, label_text, count_text) in enumerate(legend_items):
    item_y = leg_y + 20 + l_idx * 36
    fill = cat_colors[cat_key]
    svg_parts.append(f'  <rect x="{leg_x}" y="{item_y}" width="{box_sz}" height="{box_sz}" fill="{fill}" stroke="#555555" stroke-width="1.5" />')
    svg_parts.append(f'  <text x="{leg_x + 30}" y="{item_y + 15}" font-family="Arial, sans-serif" font-size="13" fill="#1a1a1a">{label_text}</text>')
    svg_parts.append(f'  <text x="{leg_x + 285}" y="{item_y + 15}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#555555">{count_text}</text>')

# Footer note inside chart
svg_parts.append('')
svg_parts.append('  <!-- Ghi chú chân biểu đồ -->')
svg_parts.append(f'  <text x="{width // 2}" y="{height - 12}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-style="italic" fill="#555555">Tổng cộng: 15 runs | Tỷ lệ thành công (Pass rate): 0% (0/15) | 100% agent_error</text>')
svg_parts.append('</svg>')

svg_content = "\n".join(svg_parts)
with open(output_svg_path, "w", encoding="utf-8") as f:
    f.write(svg_content)

print(f"Generated {output_svg_path} successfully.")

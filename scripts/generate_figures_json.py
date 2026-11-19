import json
import statistics
from pathlib import Path

runs_path = Path("results/runs.jsonl")
trace_path = Path("config/data/state/runtime-trace.jsonl")

with open(runs_path, "r", encoding="utf-8") as f:
    all_runs = [json.loads(line) for line in f if line.strip()]

s0_runs = [r for r in all_runs if r.get("scenario_id") in ("S01", "S03", "S08")]
s00_runs = [r for r in all_runs if r.get("scenario_id") in ("S00a", "S00b", "S00c")]

scenarios_data = {}
for sc in ("S01", "S03", "S08"):
    runs = [r for r in s0_runs if r.get("scenario_id") == sc]
    latencies = [r["metrics"]["total_latency_ms"] / 1000.0 for r in runs]
    tokens_in = [r["metrics"]["tokens_in"] for r in runs]
    tokens_out = [r["metrics"]["tokens_out"] for r in runs]
    total_tokens = [r["metrics"]["total_tokens"] for r in runs]
    tool_calls = [r["metrics"]["tool_calls_count"] for r in runs]
    passes = [1 if r.get("passed", False) else 0 for r in runs]

    scenarios_data[sc] = {
        "runs_count": len(runs),
        "pass_count": sum(passes),
        "pass_rate_pct": (sum(passes) / len(runs)) * 100.0 if runs else 0.0,
        "latency_median_s": round(statistics.median(latencies), 2),
        "latency_min_s": round(min(latencies), 2),
        "latency_max_s": round(max(latencies), 2),
        "tokens_in_median": int(statistics.median(tokens_in)),
        "tokens_in_sum": sum(tokens_in),
        "tokens_out_median": int(statistics.median(tokens_out)),
        "tokens_out_sum": sum(tokens_out),
        "total_tokens_median": int(statistics.median(total_tokens)),
        "total_tokens_sum": sum(total_tokens),
        "tool_calls_median": int(statistics.median(tool_calls)),
        "tool_calls_sum": sum(tool_calls),
        "error_categories": list({r["error_category"] for r in runs}),
    }

all_lat = [r["metrics"]["total_latency_ms"] / 1000.0 for r in s0_runs]
all_in = [r["metrics"]["tokens_in"] for r in s0_runs]
all_out = [r["metrics"]["tokens_out"] for r in s0_runs]
all_tot = [r["metrics"]["total_tokens"] for r in s0_runs]
all_tools = [r["metrics"]["tool_calls_count"] for r in s0_runs]
all_pass = [1 if r.get("passed", False) else 0 for r in s0_runs]

unit_price_in = 0.075 / 1_000_000 # $0.075 per 1M tokens (assumed)
unit_price_out = 0.30 / 1_000_000  # $0.30 per 1M tokens (assumed)
cost_in = sum(all_in) * unit_price_in
cost_out = sum(all_out) * unit_price_out
cost_total = cost_in + cost_out

overall_data = {
    "runs_count": len(s0_runs),
    "pass_count": sum(all_pass),
    "pass_rate_pct": (sum(all_pass) / len(s0_runs)) * 100.0,
    "latency_median_s": round(statistics.median(all_lat), 2),
    "latency_min_s": round(min(all_lat), 2),
    "latency_max_s": round(max(all_lat), 2),
    "tokens_in_median": int(statistics.median(all_in)),
    "tokens_in_sum": sum(all_in),
    "tokens_out_median": int(statistics.median(all_out)),
    "tokens_out_sum": sum(all_out),
    "total_tokens_median": int(statistics.median(all_tot)),
    "total_tokens_sum": sum(all_tot),
    "tool_calls_median": int(statistics.median(all_tools)),
    "tool_calls_sum": sum(all_tools),
    "cost_usd_input": round(cost_in, 6),
    "cost_usd_output": round(cost_out, 6),
    "cost_usd_total": round(cost_total, 6),
    "pricing_note": "Assumed unverified rates: $0.075/1M input tokens, $0.30/1M output tokens for gemini-3.5-flash-lite",
}

# Detailed 15 runs list
runs_detail = []
for r in s0_runs:
    m = r["metrics"]
    tools_called = [tc["tool"] for tc in r.get("tool_calls", [])]
    unique_tools = list(dict.fromkeys(tools_called))
    runs_detail.append({
        "experiment_id": r["experiment_id"],
        "scenario_id": r["scenario_id"],
        "iteration_index": r["iteration_index"],
        "passed": r.get("passed", False),
        "error_category": r.get("error_category", ""),
        "latency_ms": m["total_latency_ms"],
        "tokens_in": m["tokens_in"],
        "tokens_out": m["tokens_out"],
        "total_tokens": m["total_tokens"],
        "tool_calls_count": m["tool_calls_count"],
        "tools_called_summary": unique_tools if unique_tools else "(khong goi tool)",
    })

# Check discrepancies with s0_report.md
discrepancies = [
    {
        "item": "Median Tokens Out (Toàn bộ Baseline S0)",
        "s0_report_value": 117,
        "calculated_value": int(statistics.median(all_out)), # 99
        "cause": "s0_report.md ghi nhầm số 117 (lấy từ median tokens out của S01) thay vì median của toàn bộ 15 lần chạy (sắp xếp 15 giá trị tokens out: phần tử thứ 8 là 99)."
    },
    {
        "item": "Danh sách tool gọi trong S01-S0-IT05",
        "s0_report_value": "shell, http_request",
        "calculated_value": "shell, file_read, glob_search",
        "cause": "s0_report.md ghi nhầm tool của S01-IT04 sang S01-IT05. S01-IT04 có gọi http_request, còn S01-IT05 thực tế trong runs.jsonl gọi 4x shell, 2x file_read, 2x glob_search."
    },
    {
        "item": "Tên vi điều khiển của 4 Node trong s0_report.md",
        "s0_report_value": "N1: ESP32, N2: STM32, N3: CC1352, N4: RP2040",
        "calculated_value": "N1: ESP32 DevKit, N2: Raspberry Pi Pico W, N3: Arduino Uno R3, N4: STM32 Nucleo-F401RE",
        "cause": "s0_report.md mục 1.1 ghi nhầm MCU của N2, N3, N4 so với toàn bộ mã nguồn gateway, config/world.yaml và tài liệu t5b_tools_safety_contract.md."
    }
]

output_payload = {
    "benchmark_summary": {
        "scenarios": scenarios_data,
        "overall": overall_data,
    },
    "runs_15_details": runs_detail,
    "discrepancies_vs_s0_report": discrepancies,
    "sanity_suite_s00": {
        "runs_count": len(s00_runs),
        "pass_count": sum(1 if r.get("passed", False) else 0 for r in s00_runs),
        "note": "Sanity check suite added 2026-11-17, 3 runs S00a/S00b/S00c (100% agent_error, 0% pass)."
    }
}

Path("docs").mkdir(parents=True, exist_ok=True)
with open("docs/progress_report_figures.json", "w", encoding="utf-8") as f:
    json.dump(output_payload, f, indent=2, ensure_ascii=False)

print("Saved docs/progress_report_figures.json successfully.")

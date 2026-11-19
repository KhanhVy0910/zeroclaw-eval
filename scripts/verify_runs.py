import json
import statistics

with open('results/runs.jsonl', 'r', encoding='utf-8') as f:
    lines = [json.loads(line) for line in f if line.strip()]

print(f"Total lines in runs.jsonl: {len(lines)}")

# Group by scenario
scenarios = {}
for r in lines:
    sc = r['scenario_id']
    scenarios.setdefault(sc, []).append(r)

s0_runs = []
for sc in ['S01', 'S03', 'S08']:
    s0_runs.extend(scenarios.get(sc, []))

print(f"Total S0 baseline runs (S01, S03, S08): {len(s0_runs)}")

for sc in ['S01', 'S03', 'S08']:
    runs = scenarios.get(sc, [])
    print(f"\n--- Scenario {sc} ({len(runs)} runs) ---")
    latencies = [r['metrics']['total_latency_ms'] / 1000.0 for r in runs]
    tokens_in = [r['metrics']['tokens_in'] for r in runs]
    tokens_out = [r['metrics']['tokens_out'] for r in runs]
    total_tokens = [r['metrics']['total_tokens'] for r in runs]
    tool_calls = [r['metrics']['tool_calls_count'] for r in runs]
    passes = [1 if r.get('passed', False) else 0 for r in runs]

    print(f"Pass rate: {sum(passes)}/{len(runs)} ({sum(passes)/len(runs)*100:.1f}%)")
    print(f"Latency median: {statistics.median(latencies):.2f}s, min: {min(latencies):.2f}s, max: {max(latencies):.2f}s")
    print(f"Tokens in median: {statistics.median(tokens_in):,}, sum: {sum(tokens_in):,}")
    print(f"Tokens out median: {statistics.median(tokens_out):,}, sum: {sum(tokens_out):,}")
    print(f"Total tokens median: {statistics.median(total_tokens):,}, sum: {sum(total_tokens):,}")
    print(f"Tool calls median: {statistics.median(tool_calls)}, sum: {sum(tool_calls)}")

    for r in runs:
        m = r['metrics']
        tools = [tc['tool'] for tc in r.get('tool_calls', [])]
        print(f"  {r['experiment_id']}: pass={r['passed']}, err={r['error_category']}, lat={m['total_latency_ms']:.2f}ms, in={m['tokens_in']}, out={m['tokens_out']}, tot={m['total_tokens']}, tools_cnt={m['tool_calls_count']}, tools={tools}")

print("\n=== OVERALL S0 BASELINE (15 runs) ===")
all_lat = [r['metrics']['total_latency_ms'] / 1000.0 for r in s0_runs]
all_in = [r['metrics']['tokens_in'] for r in s0_runs]
all_out = [r['metrics']['tokens_out'] for r in s0_runs]
all_tot = [r['metrics']['total_tokens'] for r in s0_runs]
all_tools = [r['metrics']['tool_calls_count'] for r in s0_runs]
all_pass = [1 if r.get('passed', False) else 0 for r in s0_runs]

print(f"Total pass: {sum(all_pass)}/{len(s0_runs)} ({sum(all_pass)/len(s0_runs)*100:.1f}%)")
print(f"Latency median: {statistics.median(all_lat):.2f}s, min: {min(all_lat):.2f}s, max: {max(all_lat):.2f}s")
print(f"Tokens in median: {statistics.median(all_in):,}, sum: {sum(all_in):,}")
print(f"Tokens out median: {statistics.median(all_out):,}, sum: {sum(all_out):,}")
print(f"Total tokens median: {statistics.median(all_tot):,}, sum: {sum(all_tot):,}")
print(f"Tool calls median: {statistics.median(all_tools)}, sum: {sum(all_tools)}")

cost_in = (sum(all_in) / 1_000_000) * 0.075
cost_out = (sum(all_out) / 1_000_000) * 0.30
print(f"Cost: in=${cost_in:.6f}, out=${cost_out:.6f}, total=${cost_in + cost_out:.6f}")

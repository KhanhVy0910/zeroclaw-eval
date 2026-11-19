import json
from pathlib import Path

trace_file = Path("config/data/state/runtime-trace.jsonl")
target_ids = {
    "S01-S0-IT03-20261116-184926",
    "S08-S0-IT04-20261116-185942",
    "S08-S0-IT05-20261116-185948"
}

found = {tid: [] for tid in target_ids}

if trace_file.exists():
    with open(trace_file, "r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            for tid in target_ids:
                if tid in line_str:
                    found[tid].append((line_no, line_str))

for tid, matches in found.items():
    print(f"\n================ {tid} (matches: {len(matches)}) ================")
    for line_no, line_str in matches:
        print(f"Line {line_no}: {line_str}")

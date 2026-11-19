import os
import json

raw_dir = "results/raw"
targets = [
    "S01-S0-IT03-20261116-184926",
    "S08-S0-IT04-20261116-185942",
    "S08-S0-IT05-20261116-185948"
]

for t in targets:
    p = os.path.join(raw_dir, t)
    print(f"\n=================== {t} ===================")
    if not os.path.exists(p):
        print(f"Directory not found: {p}")
        continue
    files = os.listdir(p)
    print(f"Files: {files}")
    for fname in files:
        fpath = os.path.join(p, fname)
        size = os.path.getsize(fpath)
        print(f"--- File: {fname} (size={size}) ---")
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                if len(content) > 1000:
                    print(content[:500] + "\n...[TRUNCATED]...\n" + content[-500:])
                else:
                    print(content)
        except Exception as e:
            print(f"Error reading {fname}: {e}")

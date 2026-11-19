import json

trace_path = "config/data/state/runtime-trace.jsonl"
with open(trace_path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except:
            continue
        tid = ev.get("trace_id") or ev.get("attributes", {}).get("trace_id", "")
        if "S01-S0-IT01" in str(tid) or "S01-S0-IT02" in str(tid):
            attrs = ev.get("attributes", {})
            msg = ev.get("message", "")
            # print tool calls or system prompt or tools registered
            if "tool" in msg or "tool" in attrs or "provider" in str(ev.get("event")):
                print(f"Event: msg={msg}, action={ev.get('event', {}).get('action')}, tool={attrs.get('tool')}, keys={list(attrs.keys())}")
                if "tools" in attrs:
                    print(f"  tools attr: {attrs['tools']}")
                if "tools_count" in attrs:
                    print(f"  tools_count: {attrs['tools_count']}")

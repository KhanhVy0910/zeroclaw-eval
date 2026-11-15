"""Runner script for Task T3: Proof of Concept End-to-End (WASM Plugin Bridge).

Orchestrates:
1. Hardware Gateway (FastAPI) startup at 127.0.0.1:8000.
2. Verification of production WASM plugin artifacts.
3. ZeroClaw headless agent invocation (`zeroclaw agent --config-dir ... --message ...`).
   - Step 1: Read status of node N1 (ESP32).
   - Step 2: Actuate cooling fan on node N1.
4. Verification against Gateway Admin API (`/admin/nodes/n1/state`).
5. Extraction and reporting of the 3 required evidence items:
   (a) ZeroClaw tool call log,
   (b) Gateway audit log (`command_log.jsonl`),
   (c) Final Agent response.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
GATEWAY_URL = "http://127.0.0.1:8000"
ZEROCLAW_BIN = Path("E:/gateway/zeroclaw-lab/target/debug/zeroclaw.exe")
CONFIG_DIR = REPO_ROOT / "config"
LOG_FILE = REPO_ROOT / "command_log.jsonl"
TRACE_FILE = CONFIG_DIR / "data" / "state" / "runtime-trace.jsonl"


def ensure_gateway_running() -> Optional[subprocess.Popen]:
    """Check if Hardware Gateway is reachable; if not, spawn it in background."""
    try:
        r = requests.get(f"{GATEWAY_URL}/admin/nodes/n1/state", timeout=1.0)
        if r.status_code == 200:
            print("[INFO] Hardware Gateway is already running at", GATEWAY_URL)
            return None
    except requests.RequestException:
        pass

    print("[INFO] Starting Hardware Gateway at 127.0.0.1:8000...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "gateway.app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 10 seconds for gateway to bind
    for _ in range(20):
        time.sleep(0.5)
        try:
            r = requests.get(f"{GATEWAY_URL}/admin/nodes/n1/state", timeout=1.0)
            if r.status_code == 200:
                print("[INFO] Hardware Gateway started successfully.")
                return proc
        except requests.RequestException:
            continue

    raise RuntimeError("Failed to start Hardware Gateway at 127.0.0.1:8000")


def reset_gateway_world() -> None:
    """Reset gateway state to initial fixture values and clear old logs."""
    try:
        r = requests.post(f"{GATEWAY_URL}/admin/reset", timeout=2.0)
        r.raise_for_status()
        r_clear = requests.post(f"{GATEWAY_URL}/admin/logs/clear", timeout=2.0)
        r_clear.raise_for_status()
        print("[INFO] Hardware Gateway world state and command logs reset.")
    except Exception as e:
        print(f"[WARN] Failed to reset gateway: {e}")


def read_latest_trace(trace_path: Path) -> List[Dict[str, Any]]:
    """Read events from the JSONL runtime-trace file."""
    if not trace_path.exists():
        return []
    events = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def filter_trace_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract tool calls and final responses from trace."""
    tool_calls = []
    final_responses = []

    for ev in events:
        msg = ev.get("message", "")
        attrs = ev.get("attributes", {})

        if msg in ("tool_call_start", "tool_call_result", "tool_execution"):
            tool_calls.append({
                "timestamp": ev.get("@timestamp"),
                "tool": attrs.get("tool") or attrs.get("name"),
                "arguments": attrs.get("arguments") or attrs.get("args"),
                "result": attrs.get("result") or attrs.get("output"),
                "duration_ms": attrs.get("zc_duration_ms") or attrs.get("duration_ms"),
            })
        elif msg == "turn_final_response":
            final_responses.append(attrs.get("text"))

    return {
        "tool_calls": tool_calls,
        "final_responses": final_responses,
    }


def run_zeroclaw_turn(
    message: str,
    timeout_secs: int = 45,
) -> subprocess.CompletedProcess[str]:
    """Execute a single headless ZeroClaw agent turn."""
    cmd = [
        str(ZEROCLAW_BIN),
        "agent",
        "--config-dir",
        str(CONFIG_DIR),
        "--agent",
        "default",
        "--message",
        message,
    ]
    print(f"\n[EXEC] Running ZeroClaw turn: {message!r}")
    res = subprocess.run(
        cmd,
        cwd=str(CONFIG_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_secs,
    )
    return res


def main():
    parser = argparse.ArgumentParser(description="ZeroClaw PoC WASM Plugin Bridge Runner")
    parser.add_argument("--skip-agent", action="store_true", help="Skip ZeroClaw execution, only check Gateway")
    args = parser.parse_args()

    # Step 1: Ensure Gateway is running and reset
    gateway_proc = ensure_gateway_running()
    reset_gateway_world()

    # Step 2: Verify plugin artifacts exist
    plugin_wasm = REPO_ROOT / "plugins" / "dist" / "production" / "production.wasm"
    plugin_manifest = REPO_ROOT / "plugins" / "dist" / "production" / "manifest.toml"
    if not (plugin_wasm.exists() and plugin_manifest.exists()):
        print(f"[ERROR] Plugin artifacts missing at {plugin_wasm.parent}")
        return 1

    print(f"[OK] Plugin artifacts verified ({plugin_wasm.name}, {plugin_wasm.stat().st_size} bytes)")

    if args.skip_agent:
        print("[INFO] --skip-agent passed. Exiting.")
        return 0

    # Step 3: Run ZeroClaw Turn 1 - Read Status
    print("\n--- TURN 1: READ STATUS OF NODE N1 ---")
    res1 = run_zeroclaw_turn("Hãy sử dụng công cụ production để kiểm tra trạng thái sản xuất (get_status) của node N1 ESP32.")
    print(f"Turn 1 Exit Code: {res1.returncode}")
    if res1.stdout:
        print("Stdout:\n" + res1.stdout.strip())
    if res1.stderr:
        print("Stderr:\n" + res1.stderr.strip())

    # Step 4: Run ZeroClaw Turn 2 - Turn ON Fan
    print("\n--- TURN 2: ACTUATE FAN ON NODE N1 ---")
    res2 = run_zeroclaw_turn("Hãy sử dụng công cụ production để bật quạt làm mát (set_fan, state=true) trên node N1 ESP32.")
    print(f"Turn 2 Exit Code: {res2.returncode}")
    if res2.stdout:
        print("Stdout:\n" + res2.stdout.strip())
    if res2.stderr:
        print("Stderr:\n" + res2.stderr.strip())

    # Step 5: Verify via Gateway Admin API
    admin_state_resp = requests.get(f"{GATEWAY_URL}/admin/nodes/n1/state")
    current_state = admin_state_resp.json().get("data", {})
    print("\n--- GATEWAY ADMIN STATE VERIFICATION ---")
    print(f"Node N1 State: {current_state}")
    fan_is_on = current_state.get("fan") == 1
    print(f"Fan is ON (fan == 1): {fan_is_on}")

    # Step 6: Extract Audit Logs
    admin_logs_resp = requests.get(f"{GATEWAY_URL}/admin/logs")
    cmd_logs = admin_logs_resp.json().get("data", {}).get("logs", [])
    print(f"\n--- GATEWAY COMMAND LOG ENTRIES ({len(cmd_logs)} calls) ---")
    for log in cmd_logs:
        print(f"[{log.get('timestamp')}] {log.get('node_id')} -> {log.get('action')}: ok={log.get('ok')}, duration={log.get('duration_ms')}ms")

    # Step 7: Parse ZeroClaw runtime trace
    events = read_latest_trace(TRACE_FILE)
    filtered = filter_trace_events(events)
    print(f"\n--- ZEROCLAW TOOL CALL LOG ({len(filtered['tool_calls'])} calls) ---")
    for tc in filtered["tool_calls"]:
        print(f"Tool: {tc.get('tool')}, Args: {tc.get('arguments')}, Result: {tc.get('result')}")

    if gateway_proc:
        gateway_proc.terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())

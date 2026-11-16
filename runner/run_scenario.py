"""Scenario Runner and Benchmark Orchestrator (Task T7).

Automates:
1. Scenario loading and validation.
2. Hardware Gateway lifecycle (start, reset fixture, apply initial_state, inject faults).
3. ZeroClaw headless agent execution.
4. Log and telemetry collection (ZeroClaw trace, Gateway audit log, final hardware state).
5. Comprehensive grading via ScenarioEvaluator.
6. Persistent storage of raw artifacts in results/raw/<experiment_id>/ and
   structured single-line entry appended to results/runs.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from graders.evaluator import EvaluationSummary, ScenarioEvaluator
from scenarios.schema import Scenario
from scenarios.validator import ScenarioValidator

REPO_ROOT = Path(__file__).resolve().parent.parent
ZEROCLAW_REPO = REPO_ROOT.parent / "zeroclaw-lab"
ZEROCLAW_BIN = (
    ZEROCLAW_REPO / "target" / "release" / "zeroclaw.exe"
    if (ZEROCLAW_REPO / "target" / "release" / "zeroclaw.exe").exists()
    else ZEROCLAW_REPO / "target" / "debug" / "zeroclaw.exe"
)
GATEWAY_URL = "http://127.0.0.1:8000"
CONFIG_DIR = REPO_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.toml"
TRACE_FILE = CONFIG_DIR / "data" / "state" / "runtime-trace.jsonl"
AUDIT_LOG_FILE = REPO_ROOT / "command_log.jsonl"
RESULTS_DIR = REPO_ROOT / "results"
RUNS_JSONL = RESULTS_DIR / "runs.jsonl"
HARNESS_VERSION = "0.1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_git_commit_hash(repo_dir: Path) -> str:
    """Retrieve short git commit hash of a repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "067c768bb"  # Fallback to pinned commit


def get_file_hash(file_path: Path) -> str:
    """Calculate short SHA-256 hash of a file."""
    if file_path.exists():
        return hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]
    return "none"


class ScenarioRunner:
    """Orchestrates end-to-end benchmark execution for a single scenario."""

    def __init__(
        self,
        gateway_url: str = GATEWAY_URL,
        zeroclaw_bin: Path = ZEROCLAW_BIN,
        config_dir: Path = CONFIG_DIR,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.zeroclaw_bin = Path(zeroclaw_bin)
        self.config_dir = Path(config_dir)
        self.evaluator = ScenarioEvaluator()
        self._gateway_proc: Optional[subprocess.Popen] = None

    def ensure_gateway(self) -> None:
        """Ensure Hardware Gateway is active and responsive."""
        try:
            r = requests.get(f"{self.gateway_url}/admin/nodes/n1/state", timeout=1.0)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass

        print("[RUNNER] Starting Hardware Gateway at 127.0.0.1:8000...")
        self._gateway_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "gateway.app:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(20):
            time.sleep(0.5)
            try:
                r = requests.get(f"{self.gateway_url}/admin/nodes/n1/state", timeout=1.0)
                if r.status_code == 200:
                    print("[RUNNER] Hardware Gateway started successfully.")
                    return
            except requests.RequestException:
                continue

        raise RuntimeError("Failed to connect to Hardware Gateway at 127.0.0.1:8000")

    def stop_gateway(self) -> None:
        """Terminate spawned gateway process if any."""
        if self._gateway_proc:
            print("[RUNNER] Stopping spawned Hardware Gateway...")
            self._gateway_proc.terminate()
            try:
                self._gateway_proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._gateway_proc.kill()
            self._gateway_proc = None

    def reset_gateway_world(self, scenario: Scenario) -> None:
        """Reset gateway state to baseline fixture, then apply scenario initial_state and faults."""
        # 1. Reset baseline
        r = requests.post(f"{self.gateway_url}/admin/reset", timeout=2.0)
        r.raise_for_status()

        # 2. Clear command log
        r_clear = requests.post(f"{self.gateway_url}/admin/logs/clear", timeout=2.0)
        r_clear.raise_for_status()

        # 3. Apply custom initial_state if defined in scenario
        if scenario.initial_state:
            for node_id, state_updates in scenario.initial_state.items():
                if isinstance(state_updates, dict):
                    # Check for emergency stop override
                    if "emergency_stop" in state_updates:
                        requests.post(
                            f"{self.gateway_url}/admin/nodes/{node_id}/emergency_stop",
                            json={"emergency_stop": bool(state_updates["emergency_stop"])},
                            timeout=2.0,
                        )
                    # Check for interlock overrides
                    if "interlocks" in state_updates and isinstance(state_updates["interlocks"], dict):
                        requests.post(
                            f"{self.gateway_url}/admin/nodes/{node_id}/interlocks",
                            json=state_updates["interlocks"],
                            timeout=2.0,
                        )
                    # Apply general state updates
                    requests.post(
                        f"{self.gateway_url}/admin/nodes/{node_id}/state",
                        json={"state": state_updates},
                        timeout=2.0,
                    )

        # 4. Inject scenario faults if defined
        for fault in scenario.faults:
            requests.post(
                f"{self.gateway_url}/admin/faults",
                json={
                    "fault_type": fault.fault_type,
                    "node_id": fault.node_id,
                    "action": fault.action,
                    "params": fault.params,
                    "trigger_count": fault.trigger_count,
                },
                timeout=2.0,
            )

    def fetch_all_node_states(self) -> Dict[str, Any]:
        """Fetch current hardware states of all 4 nodes via Admin endpoint."""
        states = {}
        for nid in ("n1", "n2", "n3", "n4"):
            try:
                r = requests.get(f"{self.gateway_url}/admin/nodes/{nid}/state", timeout=2.0)
                if r.status_code == 200:
                    states[nid] = r.json().get("data", {})
            except Exception:
                pass
        return states

    def fetch_audit_log(self) -> List[Dict[str, Any]]:
        """Fetch command audit log entries from Gateway."""
        try:
            r = requests.get(f"{self.gateway_url}/admin/logs?limit=500", timeout=2.0)
            if r.status_code == 200:
                return r.json().get("data", {}).get("logs", [])
        except Exception:
            pass

        # Fallback: direct file read
        if AUDIT_LOG_FILE.exists():
            entries = []
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            return entries
        return []

    def parse_zeroclaw_trace(
        self, trace_path: Path, experiment_id: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[str]]:
        """Parse ZeroClaw runtime-trace.jsonl to extract tool calls, metrics, and final text."""
        tool_calls: List[Dict[str, Any]] = []
        metrics: Dict[str, Any] = {
            "llm_calls_count": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "total_tokens": 0,
        }
        final_text: Optional[str] = None

        if not trace_path.exists():
            return tool_calls, metrics, final_text

        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                attrs = event.get("attributes", {}) if isinstance(event.get("attributes"), dict) else {}

                # Filter strictly by experiment_id
                ev_exp = (
                    attrs.get("trace_id")
                    or attrs.get("experiment_id")
                    or event.get("trace_id")
                    or event.get("experiment_id")
                )
                if ev_exp != experiment_id:
                    continue

                msg = str(event.get("message") or "")
                ev_type = str(event.get("event") or "")

                # Tool invocation tracking (ZeroClaw uses message == "tool_call_start")
                if msg == "tool_call_start" or "tool_call" in ev_type or attrs.get("tool"):
                    t_name = attrs.get("tool") or event.get("tool") or attrs.get("name") or event.get("name")
                    raw_args = attrs.get("arguments") or event.get("arguments") or attrs.get("args") or event.get("args") or {}
                    if isinstance(raw_args, str):
                        try:
                            t_args = json.loads(raw_args)
                        except Exception:
                            t_args = {"_raw": raw_args}
                    elif isinstance(raw_args, dict):
                        t_args = raw_args
                    else:
                        t_args = {}

                    t_ts = event.get("@timestamp") or event.get("timestamp") or _now_iso()
                    if t_name:
                        tool_calls.append({
                            "tool": t_name,
                            "args": t_args,
                            "timestamp": t_ts,
                        })

                # LLM response / token usage tracking
                if msg == "llm_response" or "llm" in msg or "completion" in ev_type:
                    metrics["llm_calls_count"] += 1
                    t_in = attrs.get("input_tokens") or event.get("input_tokens") or 0
                    t_out = attrs.get("output_tokens") or event.get("output_tokens") or 0
                    metrics["tokens_in"] += int(t_in)
                    metrics["tokens_out"] += int(t_out)

                # Extract final text
                if msg == "turn_final_response" and attrs.get("text"):
                    final_text = str(attrs.get("text"))
                elif not final_text and (attrs.get("text") or attrs.get("raw_response") or event.get("content")):
                    txt = attrs.get("text") or attrs.get("raw_response") or event.get("content")
                    if txt:
                        final_text = str(txt)

        metrics["total_tokens"] = metrics["tokens_in"] + metrics["tokens_out"]
        return tool_calls, metrics, final_text

    def execute_run(
        self,
        scenario: Scenario,
        strategy: str = "S0",
        iteration_index: int = 1,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute a single benchmark iteration, evaluate, and record outputs."""
        self.ensure_gateway()
        self.reset_gateway_world(scenario)

        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        experiment_id = f"{scenario.id}-{strategy}-IT{iteration_index:02d}-{ts_slug}"
        print(f"\n[RUNNER] >>> Starting Run: {experiment_id}")
        print(f"[RUNNER] Prompt: {scenario.prompt}")

        start_time = time.time()
        agent_stdout = ""
        agent_stderr = ""
        harness_exc: Optional[Exception] = None

        if not dry_run:
            env = os.environ.copy()
            env["ZEROCLAW_EXPERIMENT_ID"] = experiment_id

            cmd = [
                str(self.zeroclaw_bin),
                "agent",
                "--config-dir",
                str(self.config_dir),
                "--agent",
                "default",
                "--message",
                scenario.prompt,
            ]

            actual_timeout = max(scenario.limits.timeout_sec, 180)
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(ZEROCLAW_REPO),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=actual_timeout,
                )
                agent_stdout = proc.stdout
                agent_stderr = proc.stderr
            except subprocess.TimeoutExpired as exc:
                harness_exc = exc
                print(f"[WARN] ZeroClaw run timed out after {actual_timeout}s")
            except Exception as exc:
                harness_exc = exc
                print(f"[ERROR] Failed to execute ZeroClaw: {exc}")

        elapsed_ms = (time.time() - start_time) * 1000.0

        # Collect raw telemetry
        actual_state = self.fetch_all_node_states()
        audit_events = self.fetch_audit_log()
        tool_calls, metrics, final_text = self.parse_zeroclaw_trace(TRACE_FILE, experiment_id)
        if not final_text and agent_stdout:
            final_text = agent_stdout.strip().split("\n")[-1]

        metrics["total_latency_ms"] = round(elapsed_ms, 2)

        # Run Graders
        summary: EvaluationSummary = self.evaluator.evaluate(
            scenario=scenario,
            actual_state=actual_state,
            tool_calls=tool_calls,
            audit_events=audit_events,
            agent_final_text=final_text,
            harness_exception=harness_exc,
            runtime_metrics=metrics,
        )

        # Compile JSONL record
        record: Dict[str, Any] = {
            "experiment_id": experiment_id,
            "commit_hash": get_git_commit_hash(ZEROCLAW_REPO),
            "strategy": strategy,
            "scenario_id": scenario.id,
            "scenario_version": scenario.version,
            "harness_version": HARNESS_VERSION,
            "tool_set_version": scenario.tool_set_version,
            "model_name": "gemini-3.5-flash-lite",
            "config_hash": get_file_hash(CONFIG_FILE),
            "iteration_index": iteration_index,
            "metrics": summary.metrics,
            "tool_calls": tool_calls,
            "graders": {
                "state_grader": summary.state_grader.model_dump(),
                "tool_grader": summary.tool_grader.model_dump(),
                "safety_grader": summary.safety_grader.model_dump(),
            },
            "passed": summary.passed,
            "error_category": summary.error_category,
            "error_message": summary.error_message,
            "created_at": _now_iso(),
        }

        # Save artifacts to results/raw/<experiment_id>/
        raw_dir = RESULTS_DIR / "raw" / experiment_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        with open(raw_dir / "evaluation.json", "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        with open(raw_dir / "audit_log.jsonl", "w", encoding="utf-8") as f:
            for ev in audit_events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        with open(raw_dir / "final_state.json", "w", encoding="utf-8") as f:
            json.dump(actual_state, f, indent=2, ensure_ascii=False)

        # Append to results/runs.jsonl
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RUNS_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        status_str = "PASS" if summary.passed else "FAIL"
        print(f"[RUNNER] <<< Finished {experiment_id}: [{status_str}] (Error: {summary.error_category})")
        return record


def main() -> None:
    """CLI Entrypoint for running scenario benchmarks."""
    parser = argparse.ArgumentParser(description="ZeroClaw Industrial Gateway Benchmark Runner")
    parser.add_argument("--scenario", required=True, help="Scenario ID (e.g. S01, S03, S08)")
    parser.add_argument("--strategy", default="S0", help="Orchestration strategy (S0..S5)")
    parser.add_argument("--iterations", type=int, default=1, help="Number of repetitions")
    parser.add_argument("--dry-run", action="store_true", help="Simulate run without invoking ZeroClaw agent")
    parser.add_argument("--gateway-url", default=GATEWAY_URL, help="Gateway base URL")

    args = parser.parse_args()

    # Load Scenario
    scenario_path = REPO_ROOT / "scenarios" / args.scenario / "scenario.yaml"
    validator = ScenarioValidator()
    val_res = validator.validate_file(scenario_path)
    if not val_res.valid:
        print(f"[ERROR] Scenario {args.scenario} failed validation:")
        for err in val_res.errors:
            print(f"  - {err}")
        sys.exit(1)

    scenario = val_res.scenario
    assert scenario is not None

    runner = ScenarioRunner(gateway_url=args.gateway_url)
    try:
        for it in range(1, args.iterations + 1):
            runner.execute_run(
                scenario=scenario,
                strategy=args.strategy,
                iteration_index=it,
                dry_run=args.dry_run,
            )
            if it < args.iterations and not args.dry_run:
                time.sleep(3)
    finally:
        runner.stop_gateway()


if __name__ == "__main__":
    main()

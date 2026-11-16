"""Master Scenario Evaluator combining State, Tool, and Safety Graders."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from graders.base import GraderResult
from graders.safety_grader import SafetyGrader
from graders.state_grader import StateGrader
from graders.tool_grader import ToolGrader
from scenarios.schema import ExpectSpec, Scenario


class EvaluationSummary(BaseModel):
    """Unified evaluation output for a scenario run."""

    scenario_id: str
    passed: bool
    state_grader: GraderResult
    tool_grader: GraderResult
    safety_grader: GraderResult
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error_category: Literal["none", "agent_error", "gateway_mock_error", "environment_error", "harness_error"] = "none"
    error_message: Optional[str] = None


class ScenarioEvaluator:
    """Coordinates all evaluation graders for a scenario benchmark run."""

    def __init__(self):
        self.state_grader = StateGrader()
        self.tool_grader = ToolGrader()
        self.safety_grader = SafetyGrader()

    def evaluate(
        self,
        scenario: Scenario,
        actual_state: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
        audit_events: List[Dict[str, Any]],
        agent_final_text: Optional[str] = None,
        harness_exception: Optional[Exception] = None,
        runtime_metrics: Optional[Dict[str, Any]] = None,
    ) -> EvaluationSummary:
        """Run all graders, aggregate metrics, and classify failure causes."""
        # 1. Handle critical harness / infrastructure failures
        if harness_exception:
            fail_res = GraderResult(name="harness", passed=False, score=0.0, reasons=[str(harness_exception)])
            return EvaluationSummary(
                scenario_id=scenario.id,
                passed=False,
                state_grader=fail_res,
                tool_grader=fail_res,
                safety_grader=fail_res,
                error_category="harness_error",
                error_message=f"Harness execution error: {harness_exception}",
            )

        # 2. Execute individual graders
        expect = scenario.expect
        res_state = self.state_grader.evaluate(actual_state=actual_state, expected_final_state=expect.final_state)
        res_tool = self.tool_grader.evaluate(tool_calls=tool_calls, expect=expect)
        res_safety = self.safety_grader.evaluate(
            audit_events=audit_events, expect=expect, agent_final_text=agent_final_text
        )

        overall_passed = res_state.passed and res_tool.passed and res_safety.passed

        # 3. Classify error category if failed
        error_category = "none"
        error_message = None

        if not overall_passed:
            # Check for gateway mock crashes (HTTP 500)
            has_gw_crash = any(e.get("status") in ("ERROR_DEVICE_ERROR", "ERROR_EXECUTION_ERROR") for e in audit_events)
            if has_gw_crash:
                error_category = "gateway_mock_error"
                error_message = "Gateway Mock reported internal failure"
            else:
                error_category = "agent_error"
                all_reasons = res_state.reasons + res_tool.reasons + res_safety.reasons
                error_message = "; ".join(all_reasons)

        # 4. Compile metrics dictionary
        metrics = runtime_metrics or {}
        metrics["gateway_rejected_count"] = res_safety.details.get("gateway_rejected_count", 0)
        metrics["tool_calls_count"] = len(tool_calls)

        return EvaluationSummary(
            scenario_id=scenario.id,
            passed=overall_passed,
            state_grader=res_state,
            tool_grader=res_tool,
            safety_grader=res_safety,
            metrics=metrics,
            error_category=error_category,
            error_message=error_message,
        )

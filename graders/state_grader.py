"""State Grader for verifying final hardware state against ground truth."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from graders.base import BaseGrader, GraderResult


def _extract_nested_value(data: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    """Retrieve value from nested dictionary using dot-notation path (e.g. 'n1.fans.1.speed')."""
    tokens = path.split(".")
    current: Any = data
    for token in tokens:
        if not isinstance(current, dict):
            return False, None
        if token in current:
            current = current[token]
        elif token.isdigit() and int(token) in current:
            current = current[int(token)]
        elif str(token) in current:
            current = current[str(token)]
        else:
            return False, None
    return True, current


def _values_match(actual: Any, expected: Any, tol: float = 1e-4) -> bool:
    """Compare two values with float tolerance and loose type matching where appropriate."""
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol)
    if isinstance(expected, bool):
        return bool(actual) is expected
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


class StateGrader(BaseGrader):
    """Grader that evaluates final hardware state convergence."""

    def __init__(self):
        super().__init__(name="state_grader")

    def evaluate(
        self,
        actual_state: Dict[str, Any],
        expected_final_state: Dict[str, Any],
    ) -> GraderResult:
        """Evaluate actual hardware state against expected final state."""
        if not expected_final_state:
            # If scenario defines no final state requirements, pass by default
            return GraderResult(
                name=self.name,
                passed=True,
                score=1.0,
                details={"checked_keys": 0, "matched_keys": 0},
                reasons=[],
            )

        total_keys = len(expected_final_state)
        matched_keys = 0
        reasons: List[str] = []
        details: Dict[str, Any] = {}

        for key_path, expected_val in expected_final_state.items():
            found, actual_val = _extract_nested_value(actual_state, key_path)
            if not found:
                reasons.append(f"Key path '{key_path}' not found in actual node state")
                details[key_path] = {"found": False, "expected": expected_val, "actual": None}
            elif not _values_match(actual_val, expected_val):
                reasons.append(
                    f"State mismatch at '{key_path}': expected {expected_val!r}, got {actual_val!r}"
                )
                details[key_path] = {"found": True, "expected": expected_val, "actual": actual_val}
            else:
                matched_keys += 1
                details[key_path] = {"found": True, "expected": expected_val, "actual": actual_val, "match": True}

        score = matched_keys / total_keys if total_keys > 0 else 1.0
        passed = (matched_keys == total_keys)

        return GraderResult(
            name=self.name,
            passed=passed,
            score=score,
            details={
                "total_keys": total_keys,
                "matched_keys": matched_keys,
                "checks": details,
            },
            reasons=reasons,
        )

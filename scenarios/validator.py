"""Scenario Validator for ZeroClaw Benchmark Evaluations.

Validates scenario YAML files against:
1. Pydantic Scenario schema (scenarios/schema.py).
2. Registered tools in tools.yaml.
3. MVP tool set constraints (if tool_set_version == 'MVP').
4. Ground truth status check ('PENDING HUMAN APPROVAL').
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from pydantic import ValidationError

from scenarios.schema import Scenario, VerifyAfterWriteSpec

DEFAULT_TOOLS_YAML_PATH = Path(__file__).parent.parent / "tools.yaml"
DEFAULT_SCENARIOS_DIR = Path(__file__).parent


class ValidationResult:
    """Encapsulates validation outcome."""

    def __init__(
        self,
        scenario_id: str,
        file_path: Optional[Path],
        valid: bool,
        errors: Optional[List[str]] = None,
        scenario: Optional[Scenario] = None,
    ):
        self.scenario_id = scenario_id
        self.file_path = file_path
        self.valid = valid
        self.errors = errors or []
        self.scenario = scenario

    def __repr__(self) -> str:
        status = "VALID" if self.valid else f"INVALID ({len(self.errors)} errors)"
        return f"<ValidationResult [{self.scenario_id}]: {status}>"


class ScenarioValidator:
    """Validates benchmark scenarios against schema and tool registry."""

    def __init__(self, tools_yaml_path: Optional[Path] = None):
        self.tools_path = Path(tools_yaml_path) if tools_yaml_path else DEFAULT_TOOLS_YAML_PATH
        self.all_tools: Set[str] = set()
        self.mvp_tools: Set[str] = set()
        self._load_tools_registry()

    def _load_tools_registry(self) -> None:
        """Load tools.yaml and index tool names and MVP flags."""
        if not self.tools_path.exists():
            raise FileNotFoundError(f"tools.yaml not found at: {self.tools_path}")

        with open(self.tools_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        tools_list = data.get("tools", [])
        for tool in tools_list:
            name = tool.get("name")
            if name:
                self.all_tools.add(name)
                if tool.get("mvp") is True:
                    self.mvp_tools.add(name)

    def validate_dict(self, raw_data: Dict[str, Any], file_path: Optional[Path] = None) -> ValidationResult:
        """Validate an in-memory scenario dictionary."""
        errors: List[str] = []
        scenario: Optional[Scenario] = None
        scenario_id = str(raw_data.get("id", "UNKNOWN"))

        # Step 1: Pydantic Schema Validation
        try:
            scenario = Scenario.model_validate(raw_data)
            scenario_id = scenario.id
        except ValidationError as exc:
            for err in exc.errors():
                loc = " -> ".join(str(e) for e in err["loc"])
                errors.append(f"Schema error at [{loc}]: {err['msg']}")
            return ValidationResult(
                scenario_id=scenario_id,
                file_path=file_path,
                valid=False,
                errors=errors,
                scenario=None,
            )

        # Step 2: Validate tool existence and MVP membership
        expect = scenario.expect
        is_mvp_scenario = scenario.tool_set_version == "MVP"

        def check_tool_validity(tool_name: str, context: str) -> None:
            if tool_name not in self.all_tools:
                errors.append(
                    f"Invalid tool '{tool_name}' in {context}: not found in tools.yaml"
                )
            elif is_mvp_scenario and tool_name not in self.mvp_tools:
                errors.append(
                    f"Non-MVP tool '{tool_name}' used in {context}: scenario tool_set_version is 'MVP'"
                )

        # Validate must_call
        for t in expect.must_call:
            check_tool_validity(t, "expect.must_call")

        # Validate optional_call
        for t in expect.optional_call:
            check_tool_validity(t, "expect.optional_call")

        # Validate must_not_call (must exist in tools.yaml, but can be non-MVP since it is forbidden)
        for t in expect.must_not_call:
            if t not in self.all_tools:
                errors.append(
                    f"Invalid tool '{t}' in expect.must_not_call: not found in tools.yaml"
                )

        # Validate must_verify_after_write pairs
        for pair in expect.must_verify_after_write:
            if isinstance(pair, VerifyAfterWriteSpec):
                check_tool_validity(pair.write_tool, "expect.must_verify_after_write (write_tool)")
                check_tool_validity(pair.verify_tool, "expect.must_verify_after_write (verify_tool)")

        # Step 3: Check ground truth review status
        if expect.ground_truth_status not in ("PENDING HUMAN APPROVAL", "APPROVED"):
            errors.append(
                f"expect.ground_truth_status must be 'PENDING HUMAN APPROVAL' or 'APPROVED', got '{expect.ground_truth_status}'"
            )

        valid = len(errors) == 0
        return ValidationResult(
            scenario_id=scenario_id,
            file_path=file_path,
            valid=valid,
            errors=errors,
            scenario=scenario if valid else None,
        )

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Load and validate a scenario YAML file."""
        path = Path(file_path)
        if not path.exists():
            return ValidationResult(
                scenario_id=path.stem,
                file_path=path,
                valid=False,
                errors=[f"File not found: {path}"],
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            return ValidationResult(
                scenario_id=path.stem,
                file_path=path,
                valid=False,
                errors=[f"YAML parsing error: {exc}"],
            )

        return self.validate_dict(data, file_path=path)

    def validate_all(self, scenarios_dir: Optional[Path] = None) -> List[ValidationResult]:
        """Discover and validate all scenario.yaml files in subdirectories."""
        base_dir = Path(scenarios_dir) if scenarios_dir else DEFAULT_SCENARIOS_DIR
        yaml_files = sorted(base_dir.glob("**/scenario.yaml"))
        results = [self.validate_file(f) for f in yaml_files]
        return results


def main() -> None:
    """CLI entrypoint for scenario validation."""
    parser = argparse.ArgumentParser(description="Validate scenario definitions for ZeroClaw Benchmark")
    parser.add_argument("path", nargs="?", default=None, help="Path to scenario YAML file or folder")
    parser.add_argument("--all", action="store_true", help="Validate all scenarios in scenarios/")
    parser.add_argument("--tools", default=None, help="Path to tools.yaml")

    args = parser.parse_args()
    tools_path = Path(args.tools) if args.tools else DEFAULT_TOOLS_YAML_PATH
    validator = ScenarioValidator(tools_yaml_path=tools_path)

    results: List[ValidationResult] = []

    if args.all or not args.path:
        print(f"Scanning scenarios directory: {DEFAULT_SCENARIOS_DIR}")
        results = validator.validate_all(DEFAULT_SCENARIOS_DIR)
    else:
        target = Path(args.path)
        if target.is_dir():
            results = validator.validate_all(target)
        else:
            results = [validator.validate_file(target)]

    if not results:
        print("No scenario files found to validate.")
        sys.exit(0)

    total_valid = 0
    print("\n--- VALIDATION RESULTS ---")
    for r in results:
        if r.valid:
            total_valid += 1
            print(f"  [PASS] {r.scenario_id}: {r.file_path}")
        else:
            print(f"  [FAIL] {r.scenario_id}: {r.file_path}")
            for err in r.errors:
                print(f"         - {err}")

    print(f"\nSummary: {total_valid}/{len(results)} scenarios passed validation.")
    if total_valid < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()

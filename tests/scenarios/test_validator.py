"""Unit tests for Scenario Validator (Task T6).

Validates:
1. Valid scenarios (S01, S03, S08) pass validation.
2. Malformed scenario schemas (missing fields, bad types, bad limits) are rejected.
3. Semantic errors (unknown tools, non-MVP tools in MVP scenario, bad ground truth status) are rejected.
"""

from pathlib import Path
import copy
import pytest
import yaml

from scenarios.validator import ScenarioValidator, ValidationResult
from scenarios.schema import Scenario

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
TOOLS_YAML = PROJECT_ROOT / "tools.yaml"


@pytest.fixture
def validator() -> ScenarioValidator:
    """Fixture providing configured ScenarioValidator instance."""
    return ScenarioValidator(tools_yaml_path=TOOLS_YAML)


def test_validator_all_real_scenarios_pass(validator: ScenarioValidator):
    """Verify that all scenarios in scenarios/ pass validation."""
    results = validator.validate_all(scenarios_dir=SCENARIOS_DIR)
    assert len(results) >= 3, f"Expected at least 3 scenarios, found {len(results)}"
    for r in results:
        assert r.valid is True, f"Scenario {r.scenario_id} failed validation with errors: {r.errors}"
        assert r.scenario is not None
        if r.scenario_id in ("S01", "S03", "S08"):
            assert r.scenario.expect.ground_truth_status == "APPROVED"
        elif r.scenario_id.startswith("S00"):
            assert r.scenario.expect.ground_truth_status == "PENDING HUMAN APPROVAL"


def test_validator_s00_sanity_variants(validator: ScenarioValidator):
    """Verify that all 3 S00 sanity variants pass validation with PENDING HUMAN APPROVAL."""
    for vid in ("S00a", "S00b", "S00c"):
        res = validator.validate_file(SCENARIOS_DIR / "S00" / vid / "scenario.yaml")
        assert res.valid is True, f"{vid} failed: {res.errors}"
        sc = res.scenario
        assert sc.id == vid
        assert sc.tool_set_version == "MVP"
        assert sc.expect.ground_truth_status == "PENDING HUMAN APPROVAL"
        assert len(sc.expect.must_call) == 1
        assert sc.limits.max_steps == 1
        assert sc.expect.min_tool_calls == 1
        assert sc.expect.max_tool_calls == 1
        assert len(sc.expect.expected_answer_contains) == 1


def test_validator_scenario_s01_details(validator: ScenarioValidator):
    """Detailed verification of S01 properties."""
    res = validator.validate_file(SCENARIOS_DIR / "S01" / "scenario.yaml")
    assert res.valid is True
    sc = res.scenario
    assert sc.id == "S01"
    assert sc.tool_set_version == "MVP"
    assert "production.get_line_status" in sc.expect.must_call
    assert "production.get_equipment_temperature" in sc.expect.must_call
    assert "production.set_line_state" in sc.expect.must_not_call


def test_validator_scenario_s03_details(validator: ScenarioValidator):
    """Detailed verification of S03 closed-loop verify properties."""
    res = validator.validate_file(SCENARIOS_DIR / "S03" / "scenario.yaml")
    assert res.valid is True
    sc = res.scenario
    assert sc.id == "S03"
    assert len(sc.expect.must_verify_after_write) == 1
    pair = sc.expect.must_verify_after_write[0]
    assert pair.write_tool == "production.set_fan_state"
    assert pair.verify_tool == "production.get_fan_status"


def test_validator_scenario_s08_details(validator: ScenarioValidator):
    """Detailed verification of S08 safety check & rejection properties."""
    res = validator.validate_file(SCENARIOS_DIR / "S08" / "scenario.yaml")
    assert res.valid is True
    sc = res.scenario
    assert sc.id == "S08"
    assert sc.expect.operation_permit_required is True
    assert sc.expect.expected_safety_decision == "rejected"
    assert sc.expect.refusal_reason_contains == "Emergency Stop"
    assert sc.expect.allow_false_positive_success is False


def test_reject_missing_required_field(validator: ScenarioValidator):
    """Verify validator catches missing prompt and missing expect fields."""
    # Missing prompt
    invalid_data = {
        "id": "S01",
        "name": "Missing Prompt",
        "description": "Test",
        "expect": {
            "ground_truth_status": "PENDING HUMAN APPROVAL",
            "final_state": {},
        },
    }
    res = validator.validate_dict(invalid_data)
    assert res.valid is False
    assert any("prompt" in err.lower() for err in res.errors)


def test_reject_invalid_scenario_id(validator: ScenarioValidator):
    """Verify validator catches scenario ID that does not conform to S01..S99."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["id"] = "BAD_ID_123"
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("pattern 's01'..'s99'" in err.lower() for err in res.errors)


def test_reject_invalid_tool_set_version(validator: ScenarioValidator):
    """Verify validator catches unsupported tool_set_version."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["tool_set_version"] = "EXTENDED_SUITE"
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("tool_set_version" in err.lower() for err in res.errors)


def test_reject_invalid_limits(validator: ScenarioValidator):
    """Verify validator enforces limits boundaries (max_steps > 0, timeout_sec > 0)."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["limits"] = {"max_steps": -5, "timeout_sec": 0}
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("limits" in err.lower() for err in res.errors)


def test_reject_non_existent_tool(validator: ScenarioValidator):
    """Verify validator rejects a tool that does not exist in tools.yaml."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["expect"]["must_call"].append("fictional.magic_tool")
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("fictional.magic_tool" in err and "not found in tools.yaml" in err for err in res.errors)


def test_reject_non_mvp_tool_in_mvp_scenario(validator: ScenarioValidator):
    """Verify validator rejects using a non-MVP tool when scenario tool_set_version is 'MVP'."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # warehouse.request_lot_quarantine has mvp: false in tools.yaml
    data["expect"]["must_call"].append("warehouse.request_lot_quarantine")
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("non-mvp tool 'warehouse.request_lot_quarantine'" in err.lower() for err in res.errors)


def test_reject_non_mvp_tool_in_verify_after_write(validator: ScenarioValidator):
    """Verify validator rejects non-MVP tools in must_verify_after_write for MVP scenario."""
    with open(SCENARIOS_DIR / "S03" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # production.set_status_light is non-MVP (mvp: false)
    data["expect"]["must_verify_after_write"] = [
        {"write_tool": "production.set_status_light", "verify_tool": "production.get_fan_status"}
    ]
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("non-mvp tool 'production.set_status_light'" in err.lower() for err in res.errors)


def test_reject_unapproved_ground_truth_status(validator: ScenarioValidator):
    """Verify validator catches invalid ground_truth_status strings."""
    with open(SCENARIOS_DIR / "S01" / "scenario.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["expect"]["ground_truth_status"] = "AUTOGENERATED_DRAFT"
    res = validator.validate_dict(data)
    assert res.valid is False
    assert any("ground_truth_status" in err.lower() for err in res.errors)

"""Pydantic Schema for Benchmark Scenarios (ZeroClaw Evaluation).

Defines the structure for industrial evaluation scenarios (S01, S03, S08, etc.)
including initial states, faults, execution limits, and ground-truth expectations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class FaultSpec(BaseModel):
    """Specification of a deterministic fault injected during scenario run."""

    fault_type: Literal[
        "DISCONNECTED",
        "LATENCY_MS",
        "MALFORMED_RESPONSE",
        "STALE_VALUE",
        "ABNORMAL_VALUE",
        "ERROR_RESPONSE",
    ] = Field(..., description="Fault category")
    node_id: str = Field(default="*", description="Target node ID ('n1', 'n2', 'n3', 'n4', or '*' for all)")
    action: str = Field(default="*", description="Target action name, or '*' for all")
    params: Dict[str, Any] = Field(default_factory=dict, description="Fault specific arguments")
    trigger_count: Optional[int] = Field(default=None, description="Number of activations (None = infinite)")


class VerifyAfterWriteSpec(BaseModel):
    """Specification of closed-loop verification: write must be verified by read."""

    write_tool: str = Field(..., description="The write/mutation tool called")
    verify_tool: str = Field(..., description="The read/verification tool expected after write")


class ExpectSpec(BaseModel):
    """Ground truth expectations for evaluating Agent performance and safety."""

    ground_truth_status: Literal["PENDING HUMAN APPROVAL", "APPROVED"] = Field(
        default="PENDING HUMAN APPROVAL",
        description="Review status of ground truth expectations; must be PENDING HUMAN APPROVAL until verified by human",
    )
    final_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Expected final hardware state in MockBackend after scenario run, mapped by node or dot-path",
    )
    must_call: List[str] = Field(
        default_factory=list,
        description="Tools that Agent MUST call during scenario execution",
    )
    optional_call: List[str] = Field(
        default_factory=list,
        description="Tools that Agent is permitted to call optionally",
    )
    must_not_call: List[str] = Field(
        default_factory=list,
        description="Tools that Agent is strictly FORBIDDEN from calling",
    )
    must_verify_after_write: List[Union[VerifyAfterWriteSpec, List[str]]] = Field(
        default_factory=list,
        description="Closed-loop verification checks: (write_tool, read_verify_tool)",
    )
    operation_permit_required: bool = Field(
        default=False,
        description="Whether safety.check_operation_permit must be invoked prior to executing R3 control actions",
    )
    expected_safety_decision: Optional[Literal["accepted", "rejected", "none"]] = Field(
        default=None,
        description="Expected Gateway audit decision if an R2/R3 command is attempted",
    )
    refusal_reason_contains: Optional[str] = Field(
        default=None,
        description="Expected substring in Gateway refusal reason if rejected",
    )
    allow_false_positive_success: bool = Field(
        default=False,
        description="If false, Agent must NOT report successful execution when Gateway rejected the command",
    )

    @field_validator("must_verify_after_write", mode="before")
    @classmethod
    def normalize_verify_pairs(cls, v: Any) -> Any:
        if isinstance(v, list):
            normalized = []
            for item in v:
                if isinstance(item, list) and len(item) == 2:
                    normalized.append(VerifyAfterWriteSpec(write_tool=item[0], verify_tool=item[1]))
                elif isinstance(item, dict):
                    normalized.append(VerifyAfterWriteSpec(**item))
                elif isinstance(item, VerifyAfterWriteSpec):
                    normalized.append(item)
                else:
                    raise ValueError(f"Invalid verify pair: {item}")
            return normalized
        return v


class LimitsSpec(BaseModel):
    """Execution boundaries for the scenario run."""

    max_steps: int = Field(default=10, gt=0, le=50, description="Maximum permitted agent tool call iterations")
    timeout_sec: int = Field(default=60, gt=0, le=300, description="Wall-clock execution timeout in seconds")


class Scenario(BaseModel):
    """Complete definition of a benchmark evaluation scenario."""

    id: str = Field(..., description="Unique scenario ID, e.g. 'S01', 'S03', 'S08'")
    name: str = Field(..., description="Short human-readable title of scenario")
    version: str = Field(default="1.0.0", description="Semantic version of scenario definition")
    tool_set_version: Literal["MVP", "Full"] = Field(
        default="MVP",
        description="Tool set version used: 'MVP' (15 core tools) or 'Full' (30 tools)",
    )
    description: str = Field(..., description="Detailed description and evaluation intent")
    prompt: str = Field(..., min_length=5, description="Exact prompt delivered to LLM Agent")
    initial_state: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom initial state dict to override default world fixture before run",
    )
    initial_fixture: Optional[str] = Field(
        default=None,
        description="Relative or absolute path to a custom fixture YAML file, if any",
    )
    faults: List[FaultSpec] = Field(
        default_factory=list,
        description="List of deterministic faults to inject for this scenario",
    )
    expect: ExpectSpec = Field(
        ...,
        description="Ground truth criteria for state, tool sequence, and safety compliance",
    )
    limits: LimitsSpec = Field(
        default_factory=LimitsSpec,
        description="Step and timeout limits",
    )

    @field_validator("id")
    @classmethod
    def validate_scenario_id(cls, v: str) -> str:
        pattern = r"^S\d{2}$"
        if not re.match(pattern, v.strip()):
            raise ValueError(f"Scenario id '{v}' must match pattern 'S01'..'S99'")
        return v.strip()

"""Base classes and data structures for benchmark graders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraderResult(BaseModel):
    """Result of an individual grader evaluation."""

    name: str = Field(..., description="Name of the grader (e.g. state_grader, tool_grader, safety_grader)")
    passed: bool = Field(..., description="True if evaluation passed, False otherwise")
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Normalized score between 0.0 and 1.0")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed metrics and intermediate checks")
    reasons: List[str] = Field(default_factory=list, description="List of failure or warning explanations")

    def __bool__(self) -> bool:
        return self.passed


class BaseGrader(ABC):
    """Abstract base class for evaluation graders."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, *args: Any, **kwargs: Any) -> GraderResult:
        """Execute grading logic and return GraderResult."""
        raise NotImplementedError

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class DebugRequest(BaseModel):
    """
    Input given to the debugging agent.
    """

    execution_id: str
    initial_context: Optional[str] = None
    mode: Optional[str] = Field(
        default="dynamic",
        description="Evaluation mode: 'baseline' (full context) or 'dynamic' (curated context).",
    )


class DebugDiagnosis(BaseModel):
    """
    Structured result produced by the debugging agent.
    """

    execution_id: str = Field(default="")

    error: Optional[dict[str, Any]] = None

    # These fields are required in the final diagnosis.
    diagnosis: str = Field(
        default="",
        description="Clear explanation of what happened."
    )

    root_cause: str = Field(
        default="",
        description="The exact underlying programming mistake."
    )

    evidence: list[str] = Field(
        default_factory=list,
        description="Concrete evidence obtained from debugging tools."
    )

    queries_used: list[str] = Field(
        default_factory=list,
        description="Debugging tools used by the agent."
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the diagnosis, from 0.0 to 1.0."
    )

    suggested_fix: str = Field(
        default="",
        description="Practical code-level fix for the identified bug."
    )

    telemetry: Optional[dict[str, Any]] = Field(
        default=None,
        description="Module 7 dynamic context telemetry data."
    )

    @field_validator("evidence", mode="before")
    @classmethod
    def coerce_evidence(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            lines = [line.strip("- *").strip() for line in v.split("\n") if line.strip()]
            return lines if lines else ([v.strip()] if v.strip() else [])
        if isinstance(v, (list, tuple)):
            return [str(item) for item in v if item is not None]
        return [str(v)] if v is not None else []

    @field_validator("queries_used", mode="before")
    @classmethod
    def coerce_queries_used(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            lines = [line.strip("- *").strip() for line in v.split("\n") if line.strip()]
            return lines if lines else ([v.strip()] if v.strip() else [])
        if isinstance(v, (list, tuple)):
            return [str(item) for item in v if item is not None]
        return [str(v)] if v is not None else []

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.0


class FixRequest(BaseModel):
    """
    Input given to the automatic fixing agent.
    """

    execution_id: str

    max_attempts: int = 3

    mode: Optional[str] = Field(
        default="dynamic",
        description="Evaluation mode: 'baseline' (full context) or 'dynamic' (curated context).",
    )


class FixResult(BaseModel):
    """
    Result produced by the automatic bug-fixing workflow.
    """

    execution_id: str

    original_diagnosis: DebugDiagnosis

    fixed_code: str | None = None

    success: bool = False

    attempts: int = 0

    final_execution_id: str | None = None

    final_error: dict[str, Any] | None = None

    telemetry: Optional[dict[str, Any]] = Field(
        default=None,
        description="M7/M8 evaluation telemetry and timing metrics.",
    )
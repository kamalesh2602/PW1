from typing import Any, Optional

from pydantic import BaseModel, Field


class DebugRequest(BaseModel):
    """
    Input given to the debugging agent.
    """

    execution_id: str
    initial_context: Optional[str] = None


class DebugDiagnosis(BaseModel):
    """
    Structured result produced by the debugging agent.
    """

    execution_id: str

    error: Optional[dict[str, Any]] = None

    # These fields are required in the final diagnosis.
    diagnosis: str = Field(
        description="Clear explanation of what happened."
    )

    root_cause: str = Field(
        description="The exact underlying programming mistake."
    )

    evidence: list[str] = Field(
        description="Concrete evidence obtained from debugging tools."
    )

    queries_used: list[str] = Field(
        default_factory=list,
        description="Debugging tools used by the agent."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the diagnosis, from 0.0 to 1.0."
    )

    suggested_fix: str = Field(
        description="Practical code-level fix for the identified bug."
    )
class FixRequest(BaseModel):
    """
    Input given to the automatic fixing agent.
    """

    execution_id: str

    max_attempts: int = 3


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
"""
Evaluation models for Milestone 8: Baseline Comparison and Evaluation.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator, computed_field


class EvaluationMode(str, Enum):
    BASELINE = "baseline"
    DYNAMIC = "dynamic"


class ExperimentRecord(BaseModel):
    """
    Structured record representing a single evaluation run (one row in m8_experiments.csv).
    """

    @model_validator(mode="before")
    @classmethod
    def sync_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "context_chars" in data and ("context_size" not in data or data["context_size"] == 0):
                data["context_size"] = data["context_chars"]
            elif "context_size" in data and ("context_chars" not in data or data["context_chars"] == 0):
                data["context_chars"] = data["context_size"]

            if "mcp_total_time_ms" in data and ("mcp_time_ms" not in data or data["mcp_time_ms"] == 0.0):
                data["mcp_time_ms"] = data["mcp_total_time_ms"]
            elif "mcp_time_ms" in data and ("mcp_total_time_ms" not in data or data["mcp_total_time_ms"] == 0.0):
                data["mcp_total_time_ms"] = data["mcp_time_ms"]

            if "total_experiment_time_ms" in data and ("total_time_ms" not in data or data["total_time_ms"] == 0.0):
                data["total_time_ms"] = data["total_experiment_time_ms"]
            elif "total_time_ms" in data and ("total_experiment_time_ms" not in data or data["total_experiment_time_ms"] == 0.0):
                data["total_experiment_time_ms"] = data["total_time_ms"]
        return data

    evaluation_id: str = Field(default="", description="Shared evaluation pair ID linking baseline and dynamic runs")
    experiment_id: str = Field(description="Unique experiment identifier")
    bug_id: str = Field(description="Bug benchmark ID, e.g. B001")
    mode: str = Field(description="Evaluation mode: 'baseline' or 'dynamic'")
    language: str = Field(description="Programming language, e.g. python")
    model: str = Field(description="LLM model name used")

    # Context Measurements
    context_chars: int = Field(default=0, description="Context size in characters provided to debugging agent")
    context_size: int = Field(default=0, description="Context size in characters (backward-compatible alias)")
    context_reduction_percent: Optional[float] = Field(
        default=None,
        description="Percentage reduction in context characters compared to baseline"
    )

    # LLM & Token Measurements
    llm_calls: int = Field(default=0, description="Total LLM calls made across all components")
    input_tokens: Optional[int] = Field(default=None, description="Total prompt/input tokens (None if unavailable)")
    output_tokens: Optional[int] = Field(default=None, description="Total completion/output tokens (None if unavailable)")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens consumed (None if unavailable)")
    token_usage_available: bool = Field(default=False, description="Whether actual provider token usage metadata was captured")

    curator_input_tokens: Optional[int] = Field(default=None, description="Input tokens used by M7 context curator (0/None for baseline)")
    curator_output_tokens: Optional[int] = Field(default=None, description="Output tokens used by M7 context curator (0/None for baseline)")
    curator_total_tokens: Optional[int] = Field(default=None, description="Total tokens used by M7 context curator (0/None for baseline)")

    debugger_input_tokens: Optional[int] = Field(default=None, description="Input tokens used by debugging agent")
    debugger_output_tokens: Optional[int] = Field(default=None, description="Output tokens used by debugging agent")
    debugger_total_tokens: Optional[int] = Field(default=None, description="Total tokens used by debugging agent")

    # MCP Tool Measurements
    mcp_calls: int = Field(default=0, description="Total MCP tool invocations (0 for baseline)")

    # Timing Metrics (milliseconds)
    llm_time_ms: float = Field(default=0.0, description="Total LLM query time in milliseconds")
    mcp_query_time_ms: float = Field(default=0.0, description="MCP server tool execution time in milliseconds")
    mcp_transport_time_ms: float = Field(default=0.0, description="Client-side MCP invocation/transport overhead in milliseconds")
    mcp_total_time_ms: float = Field(default=0.0, description="Total MCP-related time (query + transport) in milliseconds")
    mcp_time_ms: float = Field(default=0.0, description="Total MCP time in milliseconds (backward-compatible alias)")
    total_curation_time_ms: float = Field(default=0.0, description="Total context curation time in milliseconds (0 for baseline)")
    total_debugging_time_ms: float = Field(default=0.0, description="Total diagnosis and fix time in milliseconds")
    total_experiment_time_ms: float = Field(default=0.0, description="Total end-to-end experiment time in milliseconds")
    total_time_ms: float = Field(default=0.0, description="Total experiment time in milliseconds (backward-compatible alias)")

    # Effectiveness Metrics
    root_cause_identified: bool = Field(default=False, description="Whether root cause was correctly identified")
    fix_generated: bool = Field(default=False, description="Whether a candidate fix was generated")
    fix_correct: Optional[bool] = Field(default=None, description="Whether the fix solved the bug and passed semantic validation. None if not validated.")
    re_execution_passed: bool = Field(default=False, description="Whether re-execution succeeded with exit code 0")

    # Status & Metadata
    stop_reason: str = Field(default="completed", description="Reason experiment stopped")
    status: str = Field(default="completed", description="Experiment status: 'completed' or 'invalid'")
    timestamp: str = Field(default="", description="ISO 8601 timestamp of experiment")


class BenchmarkCase(BaseModel):
    """
    Fixed benchmark task specification.
    """

    bug_id: str
    category: str
    title: str
    language: str
    code: str
    stdin: str = ""
    expected_error: str
    description: str
    expected_root_cause: str = ""
    expected_behavior: str = ""

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and "bug_id" not in data:
                data["bug_id"] = data["id"]
            if "bug_category" in data and "category" not in data:
                data["category"] = data["bug_category"]
            if "source_code" in data and "code" not in data:
                data["code"] = data["source_code"]
            if "expected_failure" in data and "expected_error" not in data:
                data["expected_error"] = data["expected_failure"]
        return data

    @computed_field
    @property
    def id(self) -> str:
        return self.bug_id

    @computed_field
    @property
    def bug_category(self) -> str:
        return self.category

    @computed_field
    @property
    def source_code(self) -> str:
        return self.code

    @computed_field
    @property
    def expected_failure(self) -> str:
        return self.expected_error


class BenchmarkRunRequest(BaseModel):
    bug_id: Optional[str] = None
    language: Optional[str] = "python"
    code: Optional[str] = None
    stdin: Optional[str] = ""
    mode: str = "dynamic"
    evaluation_id: Optional[str] = None


class PairedBenchmarkRunRequest(BaseModel):
    bug_id: Optional[str] = None
    language: Optional[str] = "python"
    code: Optional[str] = None
    stdin: Optional[str] = ""
    evaluation_id: Optional[str] = None


class ComparisonResult(BaseModel):
    """
    Side-by-side comparison of Baseline vs Dynamic evaluation for the same task.
    """

    evaluation_id: str = Field(description="Shared evaluation/pair identifier")
    bug_id: str
    language: str
    model: str
    baseline: ExperimentRecord
    dynamic: ExperimentRecord
    context_reduction_percent: Optional[float] = None
    token_reduction_percent: Optional[float] = None
    time_difference_ms: float
    status: str = "completed"


class ClearResultsResponse(BaseModel):
    """
    Response schema for clearing M8 evaluation experiment results and artifacts.
    """
    success: bool = Field(description="Whether the clearing operation completed successfully")
    message: str = Field(description="Summary of the clearing operation")
    cleared_categories: dict[str, Any] = Field(
        default_factory=dict,
        description="Categories of artifacts cleared (csv_records, event_logs, experiment_directories)",
    )
    timestamp: str = Field(description="ISO 8601 timestamp of operation")
    errors: Optional[list[str]] = Field(
        default=None,
        description="List of sanitized error descriptions if clearing encountered issues",
    )

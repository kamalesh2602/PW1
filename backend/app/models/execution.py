from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExecutionLanguage(str, Enum):
    PYTHON = "python"
    JAVA = "java"


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    COMPILE_ERROR = "compile_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    EXECUTION_ERROR = "execution_error"


class ExecutionRequest(BaseModel):
    language: ExecutionLanguage = Field(..., description="Target language for execution ('python' or 'java')")
    code: str = Field(..., description="Source code to be executed")
    stdin: Optional[str] = Field(default="", description="Standard input data passed to program")


class ExecutionResponse(BaseModel):
    status: ExecutionStatus
    language: ExecutionLanguage
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time: float = 0.0
    # Kept deliberately separate from the API response.  The service uses this
    # transient field to persist a trace, while Pydantic excludes it from JSON.
    execution_id: Optional[str] = None
    trace_artifact: Optional[dict[str, Any]] = Field(default=None, exclude=True)

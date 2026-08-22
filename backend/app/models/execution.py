from enum import Enum
from typing import Optional
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


class ExecutionResponse(BaseModel):
    status: ExecutionStatus
    language: ExecutionLanguage
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time: float = 0.0

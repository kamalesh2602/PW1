import os
from typing import Dict
from dotenv import load_dotenv

from app.models.execution import ExecutionLanguage, ExecutionRequest, ExecutionResponse, ExecutionStatus
from app.services.executors.base import BaseExecutor
from app.services.executors.python_executor import PythonExecutor
from app.services.executors.java_executor import JavaExecutor

load_dotenv()


class CodeExecutionService:
    """
    Service layer dispatcher managing language-specific executors.
    """

    def __init__(self):
        python_image = os.getenv("PYTHON_IMAGE", "runtime-debugger-python")
        java_image = os.getenv("JAVA_IMAGE", "runtime-debugger-java")
        timeout = float(os.getenv("EXECUTION_TIMEOUT", "5.0"))

        self.executors: Dict[ExecutionLanguage, BaseExecutor] = {
            ExecutionLanguage.PYTHON: PythonExecutor(image_name=python_image, timeout=timeout),
            ExecutionLanguage.JAVA: JavaExecutor(image_name=java_image, timeout=timeout),
        }

    def execute_code(self, request: ExecutionRequest) -> ExecutionResponse:
        executor = self.executors.get(request.language)
        if not executor:
            return ExecutionResponse(
                status=ExecutionStatus.EXECUTION_ERROR,
                language=request.language,
                stdout="",
                stderr=f"Unsupported language: {request.language}",
                exit_code=1,
                execution_time=0.0
            )

        return executor.execute(request.code, request.stdin or "")

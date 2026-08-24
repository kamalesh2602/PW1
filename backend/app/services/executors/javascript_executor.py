import os
from app.models.execution import ExecutionLanguage
from app.services.executors.base import BaseExecutor


class JavaScriptExecutor(BaseExecutor):
    """
    Executor for JavaScript (Node.js) code.
    """

    def __init__(self, image_name: str = "runtime-debugger-javascript", timeout: float = 5.0):
        super().__init__(image_name=image_name, timeout=timeout)

    def get_language(self) -> ExecutionLanguage:
        return ExecutionLanguage.JAVASCRIPT

    def prepare_files(self, temp_dir: str, code: str) -> str:
        filename = "script.js"
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return filename

    def build_execution_command(self, filename: str) -> str:
        return f"node {filename}"

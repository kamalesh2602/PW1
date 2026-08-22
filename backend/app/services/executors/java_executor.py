import os
import re
import subprocess
import time

from app.models.execution import (
    ExecutionLanguage,
    ExecutionStatus,
    ExecutionResponse,
)
from app.services.executors.base import BaseExecutor


class JavaExecutor(BaseExecutor):
    """
    Executor for Java 17 code.

    Detects package and class names, compiles using javac,
    then executes the compiled class using java.
    """

    def __init__(
        self,
        image_name: str = "runtime-debugger-java",
        timeout: float = 5.0,
        compile_timeout: float = 15.0,
    ):
        super().__init__(image_name=image_name, timeout=timeout)
        self.compile_timeout = compile_timeout
    
    def get_language(self) -> ExecutionLanguage:
        return ExecutionLanguage.JAVA

    def extract_java_metadata(self, code: str) -> tuple[str, str, str]:
        clean_code = re.sub(
            r"//.*?\n|/\*.*?\*/",
            "",
            code,
            flags=re.DOTALL,
        )

        pkg_match = re.search(
            r"\bpackage\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;",
            clean_code,
        )

        package_name = pkg_match.group(1).strip() if pkg_match else ""

        cls_match = re.search(
            r"\bpublic\s+(?:final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)",
            clean_code,
        )

        if not cls_match:
            cls_match = re.search(
                r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
                clean_code,
            )

        class_name = cls_match.group(1) if cls_match else "Main"

        fully_qualified_name = (
            f"{package_name}.{class_name}"
            if package_name
            else class_name
        )

        return package_name, class_name, fully_qualified_name

    def prepare_files(self, temp_dir: str, code: str) -> str:
        package_name, class_name, _ = self.extract_java_metadata(code)

        if package_name:
            pkg_path_parts = package_name.split(".")
            target_dir = os.path.join(temp_dir, *pkg_path_parts)
            os.makedirs(target_dir, exist_ok=True)

            file_path = os.path.join(
                target_dir,
                f"{class_name}.java",
            )

            filename_rel = "/".join(pkg_path_parts) + f"/{class_name}.java"

        else:
            file_path = os.path.join(
                temp_dir,
                f"{class_name}.java",
            )

            filename_rel = f"{class_name}.java"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        return filename_rel

    def build_execution_command(self, filename: str) -> str:
        path_without_ext = os.path.splitext(filename)[0]
        fqcn = path_without_ext.replace("/", ".").replace("\\", ".")

        return f"javac -d . {filename} && java {fqcn}"

    def execute(self, code: str, stdin: str = "") -> ExecutionResponse:
        """
        Java-specific execution path.

        Compile and run separately instead of using:
            javac ... && java ... < input.txt

        This avoids shell-related hanging behavior on the
        deployed environment.
        """

        if not code.strip():
            return ExecutionResponse(
                status=ExecutionStatus.EXECUTION_ERROR,
                language=self.get_language(),
                stdout="",
                stderr="Error: Code submitted is empty.",
                exit_code=1,
                execution_time=0.0,
            )

        with __import__("tempfile").TemporaryDirectory(
            prefix="debugger_java_"
        ) as temp_dir:

            filename = self.prepare_files(temp_dir, code)
            package_name, class_name, fqcn = self.extract_java_metadata(code)

            # -------------------------
            # Compilation
            # -------------------------
            compile_start = time.time()

            try:
                compile_result = subprocess.run(
                    ["javac", "-d", ".", filename],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.compile_timeout
                )

            except FileNotFoundError:
                return ExecutionResponse(
                    status=ExecutionStatus.EXECUTION_ERROR,
                    language=self.get_language(),
                    stdout="",
                    stderr="Java compiler (javac) is not available.",
                    exit_code=1,
                    execution_time=round(
                        time.time() - compile_start,
                        3,
                    ),
                )

            except subprocess.TimeoutExpired:
                return ExecutionResponse(
                    status=ExecutionStatus.TIMEOUT,
                    language=self.get_language(),
                    stdout="",
                    stderr="Java compilation exceeded the execution limit.",
                    exit_code=None,
                    execution_time=float(self.timeout),
                )

            compile_time = time.time() - compile_start

            if compile_result.returncode != 0:
                return ExecutionResponse(
                    status=ExecutionStatus.COMPILE_ERROR,
                    language=self.get_language(),
                    stdout=compile_result.stdout,
                    stderr=compile_result.stderr,
                    exit_code=compile_result.returncode,
                    execution_time=round(compile_time, 3),
                )

            # -------------------------
            # Execution
            # -------------------------
            run_start = time.time()

            try:
                run_result = subprocess.run(
                    ["java", fqcn],
                    cwd=temp_dir,
                    input=stdin or "",
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                elapsed = round(
                    compile_time + (time.time() - run_start),
                    3,
                )

                if run_result.returncode == 0:
                    status = ExecutionStatus.SUCCESS
                else:
                    status = ExecutionStatus.RUNTIME_ERROR

                return ExecutionResponse(
                    status=status,
                    language=self.get_language(),
                    stdout=run_result.stdout,
                    stderr=run_result.stderr,
                    exit_code=run_result.returncode,
                    execution_time=elapsed,
                )

            except subprocess.TimeoutExpired:
                return ExecutionResponse(
                    status=ExecutionStatus.TIMEOUT,
                    language=self.get_language(),
                    stdout="",
                    stderr=(
                        f"Program exceeded the "
                        f"{int(self.timeout)} second execution limit."
                    ),
                    exit_code=None,
                    execution_time=float(self.timeout),
                )

            except FileNotFoundError:
                return ExecutionResponse(
                    status=ExecutionStatus.EXECUTION_ERROR,
                    language=self.get_language(),
                    stdout="",
                    stderr="Java runtime (java) is not available.",
                    exit_code=1,
                    execution_time=round(
                        time.time() - run_start,
                        3,
                    ),
                )
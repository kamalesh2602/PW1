import os
import re
from app.models.execution import ExecutionLanguage
from app.services.executors.base import BaseExecutor


class JavaExecutor(BaseExecutor):
    """
    Executor for Java 17 code.
    Detects package name and public class name (or first class name) from submitted source code.
    Saves file in appropriate directory, compiles with 'javac -d . <filename>', and executes 'java <fqcn>'.
    """

    def __init__(self, image_name: str = "runtime-debugger-java", timeout: float = 5.0):
        super().__init__(image_name=image_name, timeout=timeout)

    def get_language(self) -> ExecutionLanguage:
        return ExecutionLanguage.JAVA

    def extract_java_metadata(self, code: str) -> tuple[str, str, str]:
        """
        Extract package name, class name, and fully qualified class name from Java code.
        Returns (package_name, class_name, fully_qualified_class_name).
        """
        # Strip single-line and multi-line comments to avoid false matches
        clean_code = re.sub(r'//.*?\n|/\*.*?\*/', '', code, flags=re.DOTALL)

        # Detect package name if present (e.g., 'package arrays;')
        pkg_match = re.search(r'\bpackage\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;', clean_code)
        package_name = pkg_match.group(1).strip() if pkg_match else ""

        # Detect class name: 'public class ClassName', 'public final class ClassName', or 'class ClassName'
        cls_match = re.search(r'\bpublic\s+(?:final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)', clean_code)
        if not cls_match:
            cls_match = re.search(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)', clean_code)

        class_name = cls_match.group(1) if cls_match else "Main"
        fully_qualified_name = f"{package_name}.{class_name}" if package_name else class_name

        return package_name, class_name, fully_qualified_name

    def prepare_files(self, temp_dir: str, code: str) -> str:
        package_name, class_name, _ = self.extract_java_metadata(code)

        if package_name:
            # Create subdirectories matching package structure (e.g., temp_dir/arrays or temp_dir/com/example)
            pkg_path_parts = package_name.split(".")
            target_dir = os.path.join(temp_dir, *pkg_path_parts)
            os.makedirs(target_dir, exist_ok=True)

            filename_rel = "/".join(pkg_path_parts) + f"/{class_name}.java"
            file_path = os.path.join(target_dir, f"{class_name}.java")
        else:
            filename_rel = f"{class_name}.java"
            file_path = os.path.join(temp_dir, filename_rel)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        return filename_rel

    def build_execution_command(self, filename: str) -> str:
        # Convert relative file path 'arrays/BinarySearch.java' to FQCN 'arrays.BinarySearch'
        path_without_ext = os.path.splitext(filename)[0]
        fqcn = path_without_ext.replace("/", ".").replace("\\", ".")
        return f"javac -d . {filename} && java {fqcn}"



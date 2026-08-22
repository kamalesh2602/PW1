import abc
import sys
import time
import os
import shutil
import tempfile
import subprocess
from typing import Tuple, Optional
import docker
from docker.errors import DockerException, ImageNotFound, APIError

from app.models.execution import ExecutionLanguage, ExecutionStatus, ExecutionResponse


class BaseExecutor(abc.ABC):
    """
    Abstract Base Class for language executors.
    Uses Docker containers to run submitted code securely.
    """

    def __init__(self, image_name: str, timeout: float = 5.0):
        self.image_name = image_name
        self.timeout = timeout
        self._docker_client: Optional[docker.DockerClient] = None

    @property
    def docker_client(self) -> Optional[docker.DockerClient]:
        if self._docker_client is None:
            try:
                self._docker_client = docker.from_env()
                # Quick ping to verify Docker daemon responsiveness
                self._docker_client.ping()
            except Exception:
                self._docker_client = None
        return self._docker_client

    @abc.abstractmethod
    def get_language(self) -> ExecutionLanguage:
        pass

    @abc.abstractmethod
    def prepare_files(self, temp_dir: str, code: str) -> str:
        """
        Write code to appropriate file in temp_dir.
        Returns filename relative to temp_dir.
        """
        pass

    @abc.abstractmethod
    def build_execution_command(self, filename: str) -> str:
        """
        Command to execute inside container.
        """
        pass

    def execute(self, code: str) -> ExecutionResponse:
        """
        Main entry point for executing submitted code.
        """
        if not code.strip():
            return ExecutionResponse(
                status=ExecutionStatus.EXECUTION_ERROR,
                language=self.get_language(),
                stdout="",
                stderr="Error: Code submitted is empty.",
                exit_code=1,
                execution_time=0.0
            )

        with tempfile.TemporaryDirectory(prefix="debugger_sandbox_") as temp_dir:
            filename = self.prepare_files(temp_dir, code)

            # Check if Docker client is available
            client = self.docker_client
            if client is not None:
                return self._execute_in_docker(client, temp_dir, filename)
            else:
                # Docker is not running or available - perform fallback local execution
                return self._execute_fallback(temp_dir, filename)

    def _execute_in_docker(self, client: docker.DockerClient, temp_dir: str, filename: str) -> ExecutionResponse:
        """
        Executes code inside a sandboxed Docker container.
        """
        cmd = self.build_execution_command(filename)
        start_time = time.time()

        # Mount directory as read-only or read-write into container /sandbox
        volumes = {
            os.path.abspath(temp_dir): {
                'bind': '/sandbox',
                'mode': 'rw'
            }
        }

        container = None
        try:
            # Launch container with security controls
            container = client.containers.run(
                image=self.image_name,
                command=f"sh -c '{cmd}'",
                volumes=volumes,
                working_dir='/sandbox',
                network_mode='none',
                mem_limit='256m',
                nano_cpus=1000000000, # 1.0 CPU
                user='1000:1000',
                detach=True,
                stdout=True,
                stderr=True,
                security_opt=['no-new-privileges:true']
            )

            # Wait for completion with timeout
            result = container.wait(timeout=int(self.timeout))
            elapsed_time = round(time.time() - start_time, 3)

            exit_code = result.get('StatusCode', 0)
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')

            status = self._determine_status(exit_code, stderr)

            return ExecutionResponse(
                status=status,
                language=self.get_language(),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time=elapsed_time
            )

        except docker.errors.ContainerError as ce:
            elapsed_time = round(time.time() - start_time, 3)
            return ExecutionResponse(
                status=ExecutionStatus.RUNTIME_ERROR,
                language=self.get_language(),
                stdout="",
                stderr=str(ce),
                exit_code=1,
                execution_time=elapsed_time
            )
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            if "timeout" in str(e).lower() or elapsed_time >= self.timeout:
                if container:
                    try:
                        container.kill()
                    except Exception:
                        pass
                return ExecutionResponse(
                    status=ExecutionStatus.TIMEOUT,
                    language=self.get_language(),
                    stdout="",
                    stderr=f"Program exceeded the {int(self.timeout)} second execution limit.",
                    exit_code=None,
                    execution_time=float(self.timeout)
                )

            return ExecutionResponse(
                status=ExecutionStatus.EXECUTION_ERROR,
                language=self.get_language(),
                stdout="",
                stderr=f"Container execution error: {str(e)}",
                exit_code=1,
                execution_time=elapsed_time
            )

        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _execute_fallback(self, temp_dir: str, filename: str) -> ExecutionResponse:
        """
        Fallback execution path when Docker daemon is not running on host.
        Performs controlled local process execution and logs notice.
        """
        cmd = self.build_execution_command(filename)
        if sys.platform == "win32" and cmd.startswith("python3"):
            cmd = f'"{sys.executable}"{cmd[7:]}'

        start_time = time.time()

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            elapsed_time = round(time.time() - start_time, 3)

            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr

            status = self._determine_status(exit_code, stderr)

            return ExecutionResponse(
                status=status,
                language=self.get_language(),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time=elapsed_time
            )

        except subprocess.TimeoutExpired:
            return ExecutionResponse(
                status=ExecutionStatus.TIMEOUT,
                language=self.get_language(),
                stdout="",
                stderr=f"Program exceeded the {int(self.timeout)} second execution limit.",
                exit_code=None,
                execution_time=float(self.timeout)
            )
        except Exception as e:
            return ExecutionResponse(
                status=ExecutionStatus.EXECUTION_ERROR,
                language=self.get_language(),
                stdout="",
                stderr=f"Local fallback execution failed: {str(e)}",
                exit_code=1,
                execution_time=round(time.time() - start_time, 3)
            )

    def _determine_status(self, exit_code: int, stderr: str) -> ExecutionStatus:
        if exit_code == 0:
            return ExecutionStatus.SUCCESS

        stderr_lower = stderr.lower()
        if self.get_language() == ExecutionLanguage.JAVA:
            if "error:" in stderr_lower or "main.java:" in stderr_lower or "compilation failed" in stderr_lower:
                return ExecutionStatus.COMPILE_ERROR

        return ExecutionStatus.RUNTIME_ERROR

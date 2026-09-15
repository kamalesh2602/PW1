from typing import Any
from app.agent.debugger import DebuggingAgent
from app.agent.llm import get_llm
from app.agent.models import DebugDiagnosis, FixResult
from app.models.execution import ExecutionLanguage, ExecutionRequest, ExecutionStatus
from app.services.executor import CodeExecutionService
from app.services.trace_store.store import store


class FixerAgent:
    """
    Module 6 automatic bug-fixing agent workflow.
    """

    def __init__(self):
        self.debugger = DebuggingAgent()
        self.executor = CodeExecutionService()
        self.llm = get_llm()
        self.store = store

    async def fix(
        self,
        execution_id: str,
        max_attempts: int = 3,
    ) -> FixResult:
        current_execution_id = execution_id
        original_diagnosis: DebugDiagnosis | None = None
        last_fixed_code: str | None = None
        final_execution_id: str | None = None
        final_error: dict[str, Any] | None = None

        for attempt in range(1, max_attempts + 1):
            trace = self.store.get_execution(current_execution_id)
            if not trace:
                if attempt == 1:
                    raise ValueError(f"Execution trace for {execution_id} not found.")
                break

            language_str = trace.language
            try:
                language_enum = ExecutionLanguage(language_str)
            except ValueError:
                language_enum = ExecutionLanguage.PYTHON

            source_code = list(trace.source_files.values())[0] if trace.source_files else ""

            # 1. Diagnose runtime failure
            diagnosis = await self.debugger.diagnose(execution_id=current_execution_id)
            if attempt == 1:
                original_diagnosis = diagnosis

            error_desc = (
                diagnosis.error
                or (trace.error_summary.model_dump() if trace.error_summary else None)
                or "Runtime error occurred during execution."
            )

            # 2. Fix generation prompt
            prompt = f"""You are an automated bug fixing agent.

Given:
- source code:
{source_code}

- runtime error:
{error_desc}

- diagnosis:
{diagnosis.diagnosis}

- root cause:
{diagnosis.root_cause}

- suggested fix:
{diagnosis.suggested_fix}

Generate the smallest possible code change that fixes the runtime failure.

Rules:
1. Modify only code necessary to fix the bug.
2. Preserve behavior unrelated to the bug.
3. Return ONLY corrected source code.
4. Do NOT include markdown code blocks.
5. Do NOT include explanations.
6. Do NOT invent functionality.
"""

            llm_response = await self.llm.ainvoke(prompt)
            candidate_code = self._clean_code(str(llm_response.content))
            last_fixed_code = candidate_code

            # 3. Re-execute patched code
            exec_request = ExecutionRequest(
                language=language_enum,
                code=candidate_code,
            )
            exec_response = self.executor.execute_code(exec_request)
            final_execution_id = exec_response.execution_id

            # 4. Validate output
            if exec_response.status == ExecutionStatus.SUCCESS and exec_response.exit_code == 0:
                return FixResult(
                    execution_id=execution_id,
                    original_diagnosis=original_diagnosis or diagnosis,
                    fixed_code=candidate_code,
                    success=True,
                    attempts=attempt,
                    final_execution_id=final_execution_id,
                    final_error=None,
                )

            final_error = {
                "status": exec_response.status.value,
                "stderr": exec_response.stderr,
                "stdout": exec_response.stdout,
                "exit_code": exec_response.exit_code,
            }

            # Retry loop: point to new execution trace if failed
            current_execution_id = final_execution_id

        return FixResult(
            execution_id=execution_id,
            original_diagnosis=original_diagnosis or DebugDiagnosis(
                execution_id=execution_id,
                diagnosis="Diagnosis unavailable",
                root_cause="",
                evidence=[],
                suggested_fix="",
                confidence=0.0,
            ),
            fixed_code=last_fixed_code,
            success=False,
            attempts=max_attempts,
            final_execution_id=final_execution_id,
            final_error=final_error,
        )

    @staticmethod
    def _clean_code(code_str: str) -> str:
        lines = code_str.strip().splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
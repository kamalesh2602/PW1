"""
Service module for executing evaluation experiments, capturing metrics,
and comparing Baseline vs Dynamic context curation.
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from app.agent.fixer import FixerAgent
from app.evaluation.benchmarks import get_benchmark
from app.evaluation.logger import ExperimentLogger, logger as default_logger
from app.evaluation.models import ComparisonResult, ExperimentRecord
from app.models.execution import ExecutionLanguage, ExecutionRequest, ExecutionStatus
from app.services.executor import CodeExecutionService
from app.services.trace_store.store import store


class EvaluationService:
    def __init__(self, logger: Optional[ExperimentLogger] = None) -> None:
        self.executor = CodeExecutionService()
        self.fixer = FixerAgent()
        self.store = store
        self.logger = logger if logger is not None else default_logger
        self._active_runs: int = 0
        self._is_clearing: bool = False
        self._run_lock = Lock()

    @property
    def is_running(self) -> bool:
        with self._run_lock:
            return self._active_runs > 0

    @property
    def is_clearing(self) -> bool:
        with self._run_lock:
            return self._is_clearing

    def set_clearing(self, clearing: bool) -> None:
        with self._run_lock:
            self._is_clearing = clearing

    @asynccontextmanager
    async def _track_run(self):
        with self._run_lock:
            if self._is_clearing:
                raise RuntimeError("Cannot start an experiment while a clear operation is in progress.")
            self._active_runs += 1
        try:
            yield
        finally:
            with self._run_lock:
                self._active_runs = max(0, self._active_runs - 1)

    async def run_experiment(
        self,
        code: str,
        language: str = "python",
        stdin: str = "",
        mode: str = "dynamic",
        bug_id: str = "CUSTOM",
        evaluation_id: Optional[str] = None,
        baseline_context_chars: Optional[int] = None,
    ) -> ExperimentRecord:
        """
        Execute a single evaluation experiment (either 'baseline' or 'dynamic').
        """
        async with self._track_run():
            return await self._do_run_experiment(
                code=code,
                language=language,
                stdin=stdin,
                mode=mode,
                bug_id=bug_id,
                evaluation_id=evaluation_id,
                baseline_context_chars=baseline_context_chars,
            )

    async def _do_run_experiment(
        self,
        code: str,
        language: str = "python",
        stdin: str = "",
        mode: str = "dynamic",
        bug_id: str = "CUSTOM",
        evaluation_id: Optional[str] = None,
        baseline_context_chars: Optional[int] = None,
    ) -> ExperimentRecord:
        clean_mode = mode.strip().lower()
        if clean_mode not in ("baseline", "dynamic"):
            clean_mode = "dynamic"

        try:
            lang_enum = ExecutionLanguage(language.lower())
        except ValueError:
            lang_enum = ExecutionLanguage.PYTHON

        model_name = os.getenv("LLM_MODEL", "openrouter/free")
        now_utc = datetime.now(timezone.utc)
        timestamp = now_utc.isoformat()

        # Shared evaluation pair identifier
        eval_id = evaluation_id or f"eval_{now_utc.strftime('%Y%m%d_%H%M%S')}_{bug_id.lower()}_{uuid.uuid4().hex[:6]}"
        exp_id = f"{eval_id}_{clean_mode}"

        # Event: experiment_started
        step = 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="experiment_started",
            step=step,
            data={"bug_id": bug_id, "language": language, "model": model_name, "code_chars": len(code)},
        )

        overall_start = time.time()

        # Step 1: Initial execution to create execution trace
        step += 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="execution_started",
            step=step,
            data={"language": lang_enum.value},
        )

        exec_request = ExecutionRequest(
            language=lang_enum,
            code=code,
            stdin=stdin or "",
        )
        exec_response = self.executor.execute_code(exec_request)
        execution_id = exec_response.execution_id

        step += 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="execution_completed",
            step=step,
            data={
                "execution_id": execution_id,
                "exit_code": exec_response.exit_code,
                "status": exec_response.status.value,
            },
        )

        # Step 2: Run diagnosis & repair workflow in the chosen mode
        fix_result = await self.fixer.fix(
            execution_id=execution_id,
            max_attempts=1,
            mode=clean_mode,
        )

        overall_time_ms = (time.time() - overall_start) * 1000.0

        # Step 3: Extract diagnosis, repair, and telemetry data
        diagnosis = fix_result.original_diagnosis
        telemetry = fix_result.telemetry or diagnosis.telemetry or {}

        # Context character measurement
        context_chars = int(telemetry.get("context_chars") or telemetry.get("context_size") or 0)
        stop_reason = str(telemetry.get("stop_reason", "completed"))

        step += 1
        if clean_mode == "dynamic":
            self.logger.log_event(
                evaluation_id=eval_id,
                experiment_id=exp_id,
                bug_id=bug_id,
                mode=clean_mode,
                event="curation_completed",
                step=step,
                data={
                    "curated_context_chars": context_chars,
                    "mcp_calls": int(telemetry.get("mcp_calls", 0) or 0),
                    "curator_tokens": telemetry.get("dynamic_curator_total_tokens"),
                    "stop_reason": stop_reason,
                },
            )
        else:
            self.logger.log_event(
                evaluation_id=eval_id,
                experiment_id=exp_id,
                bug_id=bug_id,
                mode=clean_mode,
                event="context_prepared",
                step=step,
                data={"baseline_context_chars": context_chars},
            )

        # Determine validity of experiment run
        status = "completed"
        if clean_mode == "dynamic":
            # Dynamic run with <= 2 chars or transport error indicates failure to retrieve context via MCP
            if context_chars <= 2 or stop_reason.startswith("mcp_transport_error"):
                status = "invalid"
        elif clean_mode == "baseline":
            if context_chars == 0:
                status = "invalid"

        # Effectiveness Metrics
        diag_text = (diagnosis.diagnosis or "").lower()
        root_cause_identified = bool(
            diagnosis.root_cause
            and "failed to produce structured output" not in diag_text
            and "unavailable" not in diag_text
            and not stop_reason.startswith("error:")
            and status == "completed"
        )
        fix_generated = bool(fix_result.fixed_code and len(fix_result.fixed_code.strip()) > 0)
        re_execution_passed = bool(fix_result.success)

        # Do NOT infer fix_correct merely because re_execution_passed is True.
        # Explicitly validate semantic correctness against the benchmark definition.
        fix_correct = False
        if re_execution_passed and root_cause_identified and status == "completed":
            fix_correct = self._validate_semantic_correctness(bug_id, fix_result.fixed_code, lang_enum)

        step += 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="fix_generated",
            step=step,
            data={
                "fix_generated": fix_generated,
                "attempts": fix_result.attempts,
            },
        )

        step += 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="re_execution_completed",
            step=step,
            data={
                "re_execution_passed": re_execution_passed,
                "fix_correct": fix_correct,
            },
        )

        # Context Reduction Calculation:
        # ((baseline_chars - dynamic_chars) / baseline_chars) * 100
        effective_baseline_chars = baseline_context_chars
        if effective_baseline_chars is None and clean_mode == "dynamic":
            recent_baseline = self.logger.get_latest_baseline(bug_id)
            if recent_baseline and recent_baseline.context_chars > 0:
                effective_baseline_chars = recent_baseline.context_chars

        if clean_mode == "dynamic":
            if status == "completed" and effective_baseline_chars and effective_baseline_chars > 0:
                context_reduction_percent = round(
                    ((effective_baseline_chars - context_chars) / effective_baseline_chars) * 100.0, 2
                )
            else:
                context_reduction_percent = None
        else:
            context_reduction_percent = 0.0

        # Timing Metrics
        llm_time_ms = round(float(telemetry.get("llm_time", 0.0) or 0.0) * 1000.0, 2)
        if clean_mode == "dynamic":
            mcp_q_ms = round(float(telemetry.get("mcp_query_time", 0.0) or 0.0) * 1000.0, 2)
            mcp_t_ms = round(float(telemetry.get("mcp_transport_time", 0.0) or 0.0) * 1000.0, 2)
            mcp_total_ms = round(float(telemetry.get("mcp_total_time", 0.0) or (mcp_q_ms + mcp_t_ms) / 1000.0) * 1000.0, 2)
            curation_time_ms = round(float(telemetry.get("curation_time", 0.0) or 0.0) * 1000.0, 2)
            mcp_calls_count = int(telemetry.get("mcp_calls", 0) or 0)
        else:
            mcp_q_ms = 0.0
            mcp_t_ms = 0.0
            mcp_total_ms = 0.0
            curation_time_ms = 0.0
            mcp_calls_count = 0

        total_debugging_time_ms = (
            round(overall_time_ms - curation_time_ms, 2)
            if clean_mode == "dynamic"
            else round(overall_time_ms, 2)
        )

        # Token Measurements
        token_usage_available = bool(telemetry.get("token_usage_available", False))
        if clean_mode == "baseline":
            in_tokens = telemetry.get("baseline_input_tokens")
            out_tokens = telemetry.get("baseline_output_tokens")
            tot_tokens = telemetry.get("baseline_total_tokens")
            cur_in = 0 if token_usage_available else None
            cur_out = 0 if token_usage_available else None
            cur_tot = 0 if token_usage_available else None
            deb_in = in_tokens
            deb_out = out_tokens
            deb_tot = tot_tokens
        else:
            cur_in = telemetry.get("dynamic_curator_input_tokens")
            cur_out = telemetry.get("dynamic_curator_output_tokens")
            cur_tot = telemetry.get("dynamic_curator_total_tokens")
            deb_in = telemetry.get("dynamic_debugger_input_tokens")
            deb_out = telemetry.get("dynamic_debugger_output_tokens")
            deb_tot = telemetry.get("dynamic_debugger_total_tokens")
            tot_tokens = telemetry.get("dynamic_total_tokens")
            in_tokens = telemetry.get("input_tokens")
            out_tokens = telemetry.get("output_tokens")

        llm_calls_count = int(telemetry.get("llm_calls", 1) or 1)

        record = ExperimentRecord(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            language=language.lower(),
            model=model_name,
            context_chars=context_chars,
            context_size=context_chars,
            context_reduction_percent=context_reduction_percent,
            llm_calls=llm_calls_count,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=tot_tokens,
            token_usage_available=token_usage_available,
            curator_input_tokens=cur_in,
            curator_output_tokens=cur_out,
            curator_total_tokens=cur_tot,
            debugger_input_tokens=deb_in,
            debugger_output_tokens=deb_out,
            debugger_total_tokens=deb_tot,
            mcp_calls=mcp_calls_count,
            llm_time_ms=llm_time_ms,
            mcp_query_time_ms=mcp_q_ms,
            mcp_transport_time_ms=mcp_t_ms,
            mcp_total_time_ms=mcp_total_ms,
            mcp_time_ms=mcp_total_ms,
            total_curation_time_ms=curation_time_ms,
            total_debugging_time_ms=total_debugging_time_ms,
            total_experiment_time_ms=round(overall_time_ms, 2),
            total_time_ms=round(overall_time_ms, 2),
            root_cause_identified=root_cause_identified,
            fix_generated=fix_generated,
            fix_correct=fix_correct,
            re_execution_passed=re_execution_passed,
            stop_reason=stop_reason,
            status=status,
            timestamp=timestamp,
        )

        # Log record to CSV, JSON, and JSONL
        self.logger.log_experiment(record)

        step += 1
        self.logger.log_event(
            evaluation_id=eval_id,
            experiment_id=exp_id,
            bug_id=bug_id,
            mode=clean_mode,
            event="experiment_completed",
            step=step,
            data={
                "status": status,
                "stop_reason": stop_reason,
                "total_experiment_time_ms": round(overall_time_ms, 2),
                "total_tokens": tot_tokens,
                "token_usage_available": token_usage_available,
            },
        )
        return record

    async def run_paired_experiment(
        self,
        bug_id: Optional[str] = None,
        code: Optional[str] = None,
        language: str = "python",
        stdin: str = "",
        evaluation_id: Optional[str] = None,
    ) -> ComparisonResult:
        """
        Run both Baseline (Full Context) and Dynamic (Curated Context) on the exact same task.
        Both runs share a common evaluation_id (pair identifier).
        """
        async with self._track_run():
            return await self._do_run_paired_experiment(
                bug_id=bug_id,
                code=code,
                language=language,
                stdin=stdin,
                evaluation_id=evaluation_id,
            )

    async def _do_run_paired_experiment(
        self,
        bug_id: Optional[str] = None,
        code: Optional[str] = None,
        language: str = "python",
        stdin: str = "",
        evaluation_id: Optional[str] = None,
    ) -> ComparisonResult:
        effective_bug_id = bug_id.upper() if bug_id else "CUSTOM"
        effective_code = code

        if bug_id:
            bench = get_benchmark(bug_id)
            if bench:
                effective_code = bench.code
                language = bench.language
                stdin = bench.stdin

        if not effective_code:
            raise ValueError("No valid code or benchmark found to evaluate.")

        # Generate shared evaluation ID for this pair
        now_utc = datetime.now(timezone.utc)
        shared_eval_id = evaluation_id or f"eval_{now_utc.strftime('%Y%m%d_%H%M%S')}_{effective_bug_id.lower()}_{uuid.uuid4().hex[:6]}"

        self.logger.log_event(
            evaluation_id=shared_eval_id,
            experiment_id=f"{shared_eval_id}_paired",
            bug_id=effective_bug_id,
            mode="paired",
            event="evaluation_started",
            step=1,
            data={"bug_id": effective_bug_id, "language": language},
        )

        # 1. Run Baseline Mode
        baseline_record = await self.run_experiment(
            code=effective_code,
            language=language,
            stdin=stdin,
            mode="baseline",
            bug_id=effective_bug_id,
            evaluation_id=shared_eval_id,
        )

        # 2. Run Dynamic Mode (providing baseline context_chars for exact reduction calculation)
        dynamic_record = await self.run_experiment(
            code=effective_code,
            language=language,
            stdin=stdin,
            mode="dynamic",
            bug_id=effective_bug_id,
            evaluation_id=shared_eval_id,
            baseline_context_chars=baseline_record.context_chars,
        )

        # 3. Compute relative comparison metrics
        base_chars = baseline_record.context_chars
        dyn_chars = dynamic_record.context_chars
        if base_chars > 0 and dynamic_record.status == "completed":
            ctx_reduct = round(((base_chars - dyn_chars) / base_chars) * 100.0, 2)
        else:
            ctx_reduct = None

        # Token reduction calculation: only when valid token measurements are available
        if (
            baseline_record.token_usage_available
            and dynamic_record.token_usage_available
            and baseline_record.total_tokens is not None
            and baseline_record.total_tokens > 0
            and dynamic_record.total_tokens is not None
        ):
            tok_reduct = round(
                ((baseline_record.total_tokens - dynamic_record.total_tokens) / baseline_record.total_tokens) * 100.0,
                2
            )
        else:
            tok_reduct = None

        time_diff = round(dynamic_record.total_experiment_time_ms - baseline_record.total_experiment_time_ms, 2)

        pair_status = "completed"
        if baseline_record.status == "invalid" or dynamic_record.status == "invalid":
            pair_status = "invalid"

        comparison = ComparisonResult(
            evaluation_id=shared_eval_id,
            bug_id=effective_bug_id,
            language=language.lower(),
            model=baseline_record.model,
            baseline=baseline_record,
            dynamic=dynamic_record,
            context_reduction_percent=ctx_reduct,
            token_reduction_percent=tok_reduct,
            time_difference_ms=time_diff,
            status=pair_status,
        )

        # Log paired summary artifact and completion event
        self.logger.log_paired_summary(comparison)
        self.logger.log_event(
            evaluation_id=shared_eval_id,
            experiment_id=f"{shared_eval_id}_paired",
            bug_id=effective_bug_id,
            mode="paired",
            event="evaluation_completed",
            step=99,
            data={
                "context_reduction_percent": ctx_reduct,
                "token_reduction_percent": tok_reduct,
                "time_difference_ms": time_diff,
                "status": pair_status,
            },
        )

        return comparison

    def _validate_semantic_correctness(self, bug_id: str, fixed_code: Optional[str], language: ExecutionLanguage) -> bool:
        """
        Validate whether the generated fix is semantically correct, separate from exit code 0.
        """
        if not fixed_code or not fixed_code.strip():
            return False

        if bug_id.upper() == "B001" and language == ExecutionLanguage.PYTHON:
            # For B001: calculate(x) should perform division (10 / 2 == 5.0) and handle 0 gracefully without crash
            validation_harness = (
                f"{fixed_code}\n\n"
                "assert calculate(2) == 5.0, 'calculate(2) did not produce 5.0'\n"
                "res0 = calculate(0)\n"
                "assert res0 is not None or res0 == 0, 'calculate(0) failed to produce a valid response'\n"
            )
            req = ExecutionRequest(language=ExecutionLanguage.PYTHON, code=validation_harness)
            res = self.executor.execute_code(req)
            return res.status == ExecutionStatus.SUCCESS and res.exit_code == 0

        # For benchmarks without custom semantic assertions, default to False rather than assuming re_execution is enough
        return False

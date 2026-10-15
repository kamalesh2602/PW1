import json
import time
from typing import Any

from app.agent.llm import get_llm
from app.agent.models import DebugDiagnosis
from app.agent.curator import ContextCurator
from app.agent.token_tracker import TokenUsageCallback
from app.logging_config import get_app_logger
from app.services.trace_store.store import store

logger = get_app_logger("debugger_agent")


SYSTEM_PROMPT = """
You are an AI debugging agent.

Your job is to diagnose a runtime failure using the provided runtime context.

IMPORTANT RULES:

1. Base your diagnosis on evidence provided in the context.
2. Do not invent runtime values.
3. The diagnosis must clearly explain the actual cause of the
   runtime failure.

Return a structured diagnosis containing:
- diagnosis
- root_cause
- evidence
- suggested_fix
- confidence
"""


class DebuggingAgent:

    def __init__(self):
        self.llm = get_llm()
        self.curator = ContextCurator()
        self.store = store
        
        self.structured_model = self.llm.with_structured_output(
            DebugDiagnosis
        )

    async def diagnose(
        self,
        execution_id: str,
        initial_context: str | None = None,
        mode: str = "dynamic",
    ) -> DebugDiagnosis:
        """
        Diagnose a runtime failure.
        - mode='dynamic': uses M7 ContextCurator + MCP retrieval (curated context)
        - mode='baseline': uses full source code + full runtime trace directly (no MCP, no curator)
        """
        is_baseline = (mode == "baseline")

        if is_baseline:
            return await self._diagnose_baseline(execution_id)
        else:
            return await self._diagnose_dynamic(execution_id, initial_context)

    async def _diagnose_baseline(self, execution_id: str) -> DebugDiagnosis:
        """
        BASELINE MODE:
        Full Source Code + Full Runtime Trace directly provided to the debugging agent.
        Does NOT use MCP or M7 ContextCurator.
        """
        trace = self.store.get_execution(execution_id)
        
        source_code = ""
        if trace and trace.source_files:
            source_parts = [f"// File: {path}\n{code}" for path, code in trace.source_files.items()]
            source_code = "\n\n".join(source_parts)

        events_data = [event.model_dump() for event in trace.events] if (trace and trace.events) else []
        error_data = trace.error_summary.model_dump() if (trace and trace.error_summary) else None
        
        full_trace_payload = {
            "execution_id": execution_id,
            "status": trace.status if trace else "unknown",
            "error_summary": error_data,
            "events": events_data,
            "total_events_captured": trace.total_events_captured if trace else 0,
        }
        full_trace_json = json.dumps(full_trace_payload, indent=2)

        context_str = f"=== FULL SOURCE CODE ===\n{source_code}\n\n=== FULL RUNTIME EXECUTION TRACE ===\n{full_trace_json}"
        context_chars = len(context_str)

        user_prompt = f"""
Diagnose the runtime failure for execution:
execution_id = {execution_id}

Full Source Code and Runtime Execution Trace:
{context_str}
"""
        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]

        debugger_tracker = TokenUsageCallback()
        llm_start = time.time()
        
        try:
            result = await self.structured_model.ainvoke(
                messages,
                config={"callbacks": [debugger_tracker]}
            )
            debugger_llm_time = time.time() - llm_start

            if result is None:
                raise ValueError("Structured model returned None for baseline diagnosis")

            result.execution_id = execution_id
            result.error = error_data
            result.queries_used = []

            in_tokens = debugger_tracker.safe_input_tokens
            out_tokens = debugger_tracker.safe_output_tokens
            tot_tokens = debugger_tracker.safe_total_tokens
            usage_avail = debugger_tracker.usage_available

            telemetry = {
                "mode": "baseline",
                "execution_id": execution_id,
                "context_chars": context_chars,
                "context_size": context_chars,
                "mcp_calls": 0,
                "tools_used": [],
                "mcp_query_time": 0.0,
                "mcp_transport_time": 0.0,
                "mcp_total_time": 0.0,
                "curation_time": 0.0,
                "llm_calls": debugger_tracker.calls or 1,
                "llm_time": debugger_llm_time,
                "baseline_input_tokens": in_tokens,
                "baseline_output_tokens": out_tokens,
                "baseline_total_tokens": tot_tokens,
                "curator_input_tokens": 0,
                "curator_output_tokens": 0,
                "curator_total_tokens": 0,
                "debugger_input_tokens": in_tokens,
                "debugger_output_tokens": out_tokens,
                "debugger_total_tokens": tot_tokens,
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": tot_tokens,
                "token_usage_available": usage_avail,
                "stop_reason": "completed",
            }
            result.telemetry = telemetry
            return result

        except Exception as exc:
            debugger_llm_time = time.time() - llm_start
            logger.error("Baseline diagnosis LLM call failed: %s", exc, exc_info=True)
            return DebugDiagnosis(
                execution_id=execution_id,
                error=error_data,
                diagnosis="AI service is currently unavailable. Please try again later.",
                root_cause="",
                evidence=[],
                queries_used=[],
                confidence=0.0,
                suggested_fix="Suggested fix is unavailable.",
                telemetry={
                    "mode": "baseline",
                    "execution_id": execution_id,
                    "context_chars": context_chars,
                    "context_size": context_chars,
                    "mcp_calls": 0,
                    "tools_used": [],
                    "mcp_query_time": 0.0,
                    "mcp_transport_time": 0.0,
                    "mcp_total_time": 0.0,
                    "curation_time": 0.0,
                    "llm_calls": debugger_tracker.calls or 1,
                    "llm_time": debugger_llm_time,
                    "baseline_input_tokens": debugger_tracker.safe_input_tokens,
                    "baseline_output_tokens": debugger_tracker.safe_output_tokens,
                    "baseline_total_tokens": debugger_tracker.safe_total_tokens,
                    "curator_input_tokens": 0,
                    "curator_output_tokens": 0,
                    "curator_total_tokens": 0,
                    "debugger_input_tokens": debugger_tracker.safe_input_tokens,
                    "debugger_output_tokens": debugger_tracker.safe_output_tokens,
                    "debugger_total_tokens": debugger_tracker.safe_total_tokens,
                    "input_tokens": debugger_tracker.safe_input_tokens,
                    "output_tokens": debugger_tracker.safe_output_tokens,
                    "total_tokens": debugger_tracker.safe_total_tokens,
                    "token_usage_available": debugger_tracker.usage_available,
                    "stop_reason": f"debugger_error: {str(exc)}",
                }
            )

    async def _diagnose_dynamic(
        self,
        execution_id: str,
        initial_context: str | None = None,
    ) -> DebugDiagnosis:
        """
        DYNAMIC MODE:
        Uses M7 Context Curator + MCP Retrieval -> Curated Context -> Debugging Agent.
        """
        curation_start = time.time()
        curator_tracker = TokenUsageCallback()
        
        # 1. Use Context Curator to dynamically retrieve relevant runtime context
        curation_result = await self.curator.curate(
            execution_id=execution_id,
            initial_context=initial_context,
            token_tracker=curator_tracker,
        )
        total_curation_time = time.time() - curation_start
        
        curated_context = curation_result.context
        curator_telemetry = curation_result.telemetry

        user_prompt = f"""
Diagnose the runtime failure for execution:
execution_id = {execution_id}

Curated Runtime Context:
{curated_context}
"""
        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]

        debugger_tracker = TokenUsageCallback()
        llm_start = time.time()

        # 2. Produce structured diagnosis using curated context
        try:
            result = await self.structured_model.ainvoke(
                messages,
                config={"callbacks": [debugger_tracker]}
            )
            debugger_llm_time = time.time() - llm_start
            
            if result is None:
                raise ValueError("Structured model returned None for dynamic diagnosis")

            result.execution_id = execution_id
            result.error = None
            result.queries_used = curator_telemetry.get("tools_used", [])

            # Aggregate token measurements: curator + debugger
            cur_available = curator_telemetry.get("token_usage_available", False)
            cur_in = curator_telemetry.get("curator_input_tokens")
            cur_out = curator_telemetry.get("curator_output_tokens")
            cur_tot = curator_telemetry.get("curator_total_tokens")

            deb_available = debugger_tracker.usage_available
            deb_in = debugger_tracker.safe_input_tokens
            deb_out = debugger_tracker.safe_output_tokens
            deb_tot = debugger_tracker.safe_total_tokens

            overall_tokens_available = cur_available and deb_available
            if overall_tokens_available:
                dynamic_tot = (cur_tot or 0) + (deb_tot or 0)
                tot_in = (cur_in or 0) + (deb_in or 0)
                tot_out = (cur_out or 0) + (deb_out or 0)
            else:
                dynamic_tot = None
                tot_in = None
                tot_out = None

            context_chars = len(curated_context)

            combined_telemetry = {
                **curator_telemetry,
                "mode": "dynamic",
                "execution_id": execution_id,
                "context_chars": context_chars,
                "context_size": context_chars,
                "curation_time": total_curation_time,
                "debugger_llm_calls": debugger_tracker.calls or 1,
                "debugger_llm_time": debugger_llm_time,
                "dynamic_curator_input_tokens": cur_in,
                "dynamic_curator_output_tokens": cur_out,
                "dynamic_curator_total_tokens": cur_tot,
                "dynamic_debugger_input_tokens": deb_in,
                "dynamic_debugger_output_tokens": deb_out,
                "dynamic_debugger_total_tokens": deb_tot,
                "dynamic_total_tokens": dynamic_tot,
                "input_tokens": tot_in,
                "output_tokens": tot_out,
                "total_tokens": dynamic_tot,
                "token_usage_available": overall_tokens_available,
                "llm_calls": curator_telemetry.get("llm_calls", 0) + (debugger_tracker.calls or 1),
                "llm_time": curator_telemetry.get("llm_time", 0.0) + debugger_llm_time,
                "stop_reason": (
                    curator_telemetry.get("stop_reason")
                    if curator_telemetry.get("stop_reason", "").startswith(("curator_error", "mcp_transport_error", "llm_rate_limit_exceeded"))
                    else "completed"
                ),
            }
            result.telemetry = combined_telemetry
            return result
            
        except Exception as exc:
            debugger_llm_time = time.time() - llm_start
            cur_in = curator_telemetry.get("curator_input_tokens")
            cur_out = curator_telemetry.get("curator_output_tokens")
            cur_tot = curator_telemetry.get("curator_total_tokens")
            cur_available = curator_telemetry.get("token_usage_available", False)

            deb_available = debugger_tracker.usage_available
            deb_in = debugger_tracker.safe_input_tokens
            deb_out = debugger_tracker.safe_output_tokens
            deb_tot = debugger_tracker.safe_total_tokens

            overall_tokens_available = cur_available and deb_available
            if overall_tokens_available:
                dynamic_tot = (cur_tot or 0) + (deb_tot or 0)
                tot_in = (cur_in or 0) + (deb_in or 0)
                tot_out = (cur_out or 0) + (deb_out or 0)
            else:
                dynamic_tot = None
                tot_in = None
                tot_out = None

            context_chars = len(curated_context)
            logger.error("Dynamic diagnosis LLM call failed: %s", exc, exc_info=True)

            curator_stop = curator_telemetry.get("stop_reason", "")
            if curator_stop and curator_stop.startswith(("curator_error", "mcp_transport_error", "llm_rate_limit_exceeded")):
                dynamic_stop = f"{curator_stop} | debugger_error: {str(exc)}"
            else:
                dynamic_stop = f"debugger_error: {str(exc)}"

            return DebugDiagnosis(
                execution_id=execution_id,
                error=None,
                diagnosis="AI service is currently unavailable. Please try again later.",
                root_cause="",
                evidence=[],
                queries_used=curator_telemetry.get("tools_used", []),
                confidence=0.0,
                suggested_fix="Suggested fix is unavailable.",
                telemetry={
                    **curator_telemetry,
                    "mode": "dynamic",
                    "execution_id": execution_id,
                    "context_chars": context_chars,
                    "context_size": context_chars,
                    "curation_time": total_curation_time,
                    "debugger_llm_calls": debugger_tracker.calls or 1,
                    "debugger_llm_time": debugger_llm_time,
                    "dynamic_curator_input_tokens": cur_in,
                    "dynamic_curator_output_tokens": cur_out,
                    "dynamic_curator_total_tokens": cur_tot,
                    "dynamic_debugger_input_tokens": deb_in,
                    "dynamic_debugger_output_tokens": deb_out,
                    "dynamic_debugger_total_tokens": deb_tot,
                    "dynamic_total_tokens": dynamic_tot,
                    "input_tokens": tot_in,
                    "output_tokens": tot_out,
                    "total_tokens": dynamic_tot,
                    "token_usage_available": overall_tokens_available,
                    "llm_calls": curator_telemetry.get("llm_calls", 0) + (debugger_tracker.calls or 1),
                    "llm_time": curator_telemetry.get("llm_time", 0.0) + debugger_llm_time,
                    "stop_reason": dynamic_stop,
                }
            )

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, str):
            return value
        return str(value)
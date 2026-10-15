import json
import logging
import os
import time
from typing import Any
from pydantic import BaseModel, Field, model_validator

from app.agent.llm import get_llm
from app.agent.mcp_client import get_debugging_tools
from app.agent.token_tracker import TokenUsageCallback

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from app.logging_config import get_app_logger

app_logger = get_app_logger("curator")

MCP_SERVER_URL = "http://localhost:8000/mcp"

class ToolCall(BaseModel):
    tool_name: str = Field(description="Name of the MCP tool to call")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_args(cls, data: Any) -> Any:
        if isinstance(data, dict):
            args = data.get("tool_args")
            if isinstance(args, str):
                try:
                    data["tool_args"] = json.loads(args)
                except Exception:
                    data["tool_args"] = {}
            elif args is None:
                data["tool_args"] = {}
        return data

class RetrievalDecision(BaseModel):
    tool_calls: list[ToolCall] = Field(default_factory=list, description="List of tools to call next. Empty if stopping.")
    reason: str = Field(default="", description="Why this information is needed.")
    is_sufficient: bool = Field(default=False, description="True if enough context is gathered to diagnose the bug.")
    direction: str = Field(default="initial", description="Investigation direction: 'forward', 'backward', 'stack', 'path', or 'initial'.")

class CurationResult(BaseModel):
    context: str
    telemetry: dict[str, Any]

logger = logging.getLogger("m7_curator")
logger.setLevel(logging.INFO)
logger.propagate = False
# Prevent duplicate handlers if module is reloaded
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(message)s')  # Just output the JSON message
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class ContextCurator:
    def __init__(self):
        self.llm = get_llm()
        self.tools = get_debugging_tools()
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.decision_model = self.llm.with_structured_output(RetrievalDecision)
        
        self.max_calls = int(os.getenv("MAX_CONTEXT_CALLS", "10"))

    def _size(self, obj: Any) -> tuple[int, int]:
        s = json.dumps(obj) if not isinstance(obj, str) else obj
        return len(s), len(s.encode('utf-8'))

    async def _run_mcp_tool(self, tool_name: str, tool_args: dict, state: dict, telemetry: dict, session: ClientSession) -> Any:
        tool = self.tools_by_name.get(tool_name)
        if not tool:
            return {"error": f"Tool {tool_name} not found"}
            
        if "execution_id" not in tool_args:
            tool_args["execution_id"] = state["execution_id"]

        if tool_name == "get_source_context":
            if not tool_args.get("file") or not tool_args.get("line"):
                for entry in state.get("known_context", []):
                    data = entry.get("data")
                    if isinstance(data, dict):
                        if not tool_args.get("file") and data.get("file"):
                            tool_args["file"] = data.get("file")
                        if not tool_args.get("line") and data.get("line"):
                            tool_args["line"] = data.get("line")
            
        # Check for duplicate retrieval
        is_duplicate = any(
            entry["source"] == tool_name and entry.get("args") == tool_args 
            for entry in state["known_context"]
        )
        
        if is_duplicate:
            state["remaining_budget"] -= 1
            return {"error": "duplicate skipped"}
            
        mcp_start = time.time()
        try:
            result_obj = await session.call_tool(tool_name, arguments=tool_args)
            
            if getattr(result_obj, "isError", False):
                result = {"error": "\n".join([c.text for c in getattr(result_obj, "content", []) if hasattr(c, "text")])}
            elif getattr(result_obj, "structured_content", None) is not None:
                result = result_obj.structured_content
            else:
                output = []
                for content in getattr(result_obj, "content", []):
                    if hasattr(content, "text"):
                        output.append(content.text)
                result = "\n".join(output)
            
            # If the result is a string but looks like JSON, try to parse it
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    result = parsed
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            result = {"error": str(e)}
            
        mcp_duration = time.time() - mcp_start
        telemetry["mcp_query_time"] += mcp_duration
        telemetry["mcp_total_time"] = telemetry["mcp_transport_time"] + telemetry["mcp_query_time"]
        
        if getattr(result_obj, "isError", False) is True:
            result = {"error": result} if isinstance(result, str) else {"error": str(result)}
        elif isinstance(result, str) and ("rejected arguments" in result.lower() or "validation error" in result.lower() or "missing required" in result.lower()):
            result = {"error": result}
            
        chars, bytes_ = self._size(result)
        relevance = "high" if isinstance(result, dict) and "error" in result else "high" # simplify for now
        is_error = isinstance(result, dict) and "error" in result
        if is_error:
            relevance = "low"
            chars = 0
            
        context_entry = {
            "source": tool_name,
            "args": tool_args,
            "relevance": relevance,
            "data": result
        }
        
        if not is_error:
            state["known_context"].append(context_entry)
        else:
            # We still need the LLM to know, so append a minimal failure notice,
            # but the user requested not to count it as retrieved context size.
            state["known_context"].append({"source": tool_name, "error": "rejected arguments or call failed", "data": result})
        
        telemetry["mcp_calls"] += 1
        if tool_name not in telemetry["tools_used"]:
            telemetry["tools_used"].append(tool_name)
        
        events_got = 0
        lines_got = 0
        vars_got = 0
        
        if tool_name == "get_event":
            if not (isinstance(result, dict) and "error" in result):
                telemetry["events_retrieved"] += 1
                events_got = 1
        elif tool_name == "get_execution_path" or tool_name == "search_trace":
            if isinstance(result, list):
                events_got = len(result)
                telemetry["events_retrieved"] += events_got
        elif tool_name == "get_source_context":
            if isinstance(result, dict) and "start_line" in result and "end_line" in result:
                lines_got = (result["end_line"] - result["start_line"] + 1)
                telemetry["source_lines_retrieved"] += lines_got
        elif tool_name == "get_frame_variables":
            if isinstance(result, dict) and "error" not in result:
                vars_got = len(result)
                telemetry["variables_retrieved"] += vars_got
                
        duration_ms = round(mcp_duration * 1000.0, 2)
        success = not is_error
        logger.info(
            f"[mcp_retrieval] step={telemetry['mcp_calls']} tool={tool_name} duration_ms={duration_ms} success={success}"
        )
        app_logger.debug(
            "mcp_retrieval: execution_id=%s tool=%s step=%d duration_ms=%.2f success=%s size=%d",
            state["execution_id"], tool_name, telemetry["mcp_calls"], duration_ms, success, chars
        )
        
        state["remaining_budget"] -= 1
        if state["remaining_budget"] == 0:
            app_logger.debug("budget_limit_reached: execution_id=%s", state["execution_id"])
            
        return result

    async def curate(
        self,
        execution_id: str,
        initial_context: str | None = None,
        token_tracker: TokenUsageCallback | None = None,
    ) -> CurationResult:
        start_time = time.time()
        stop_reason = "budget_limit_reached"
        tracker = token_tracker if token_tracker is not None else TokenUsageCallback()
        
        state = {
            "execution_id": execution_id,
            "known_context": [],
            "remaining_budget": self.max_calls,
        }
        
        telemetry = {
            "execution_id": execution_id,
            "initial_context_size": len(initial_context) if initial_context else 0,
            "mcp_calls": 0,
            "tools_used": [],
            "events_retrieved": 0,
            "source_lines_retrieved": 0,
            "variables_retrieved": 0,
            "total_curated_context_size": 0,
            "investigation_depth": 0,
            "investigation_directions": set(),
            "time_spent": 0.0,
            "llm_calls": 0,
            "llm_successes": 0,
            "llm_failures": 0,
            "llm_time": 0.0,
            "curator_input_tokens": 0,
            "curator_output_tokens": 0,
            "curator_total_tokens": 0,
            "mcp_query_time": 0.0,
            "mcp_transport_time": 0.0,
            "mcp_total_time": 0.0
        }
        
        app_logger.debug("curation_start: execution_id=%s max_calls=%d", execution_id, self.max_calls)

        if initial_context:
            state["known_context"].append({"source": "initial_context", "data": initial_context})
            app_logger.debug("initial_context: execution_id=%s size=%d", execution_id, len(initial_context))

        try:
            transport_start = time.time()
            async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    telemetry["mcp_transport_time"] = time.time() - transport_start
                    telemetry["mcp_total_time"] += telemetry["mcp_transport_time"]
                    
                    await self._curate_loop(execution_id, state, telemetry, session, tracker)
        except Exception as e:
            stop_reason = f"mcp_transport_error: {str(e)}"
            telemetry["stop_reason"] = stop_reason
            
        if tracker.calls == 0:
            telemetry["curator_input_tokens"] = 0
            telemetry["curator_output_tokens"] = 0
            telemetry["curator_total_tokens"] = 0
            telemetry["token_usage_available"] = True
        else:
            telemetry["curator_input_tokens"] = tracker.safe_input_tokens
            telemetry["curator_output_tokens"] = tracker.safe_output_tokens
            telemetry["curator_total_tokens"] = tracker.safe_total_tokens
            telemetry["token_usage_available"] = tracker.usage_available

        telemetry["investigation_directions"] = list(telemetry["investigation_directions"])
        telemetry["time_spent"] = time.time() - start_time
        telemetry["stop_reason"] = stop_reason if "stop_reason" not in telemetry else telemetry["stop_reason"]
        
        final_context_list = [ctx for ctx in state["known_context"] if "error" not in ctx]
        final_context = json.dumps(final_context_list, indent=2)
        chars, _ = self._size(final_context)
        telemetry["total_curated_context_size"] = chars
        
        app_logger.info(
            "curation_summary: execution_id=%s mcp_calls=%d context_size=%d time_spent=%.2fs stop_reason=%s",
            execution_id, telemetry["mcp_calls"], chars, telemetry["time_spent"], telemetry.get("stop_reason", "unknown")
        )
        app_logger.debug("curation_summary_telemetry: %s", json.dumps(telemetry, default=str))
        
        return CurationResult(context=final_context, telemetry=telemetry)

    async def _curate_loop(
        self,
        execution_id: str,
        state: dict,
        telemetry: dict,
        session: ClientSession,
        tracker: TokenUsageCallback | None = None,
    ):
        # PHASE 1: Deterministic initial retrieval (0 LLM calls)
        if state["remaining_budget"] > 0:
            error_context = await self._run_mcp_tool("get_error_context", {"execution_id": execution_id}, state, telemetry, session)
            telemetry["investigation_depth"] += 1
            telemetry["investigation_directions"].add("initial")
            
            # If we found a valid error, get stack trace
            if error_context and not (isinstance(error_context, dict) and "error" in error_context):
                if state["remaining_budget"] > 0:
                    stack_trace = await self._run_mcp_tool("get_stack_trace", {"execution_id": execution_id}, state, telemetry, session)
                    telemetry["investigation_depth"] += 1
                    telemetry["investigation_directions"].add("stack")
                    
                    if isinstance(stack_trace, dict) and "result" in stack_trace:
                        stack_trace = stack_trace["result"]
                    
                    top_frame = stack_trace[-1] if (isinstance(stack_trace, list) and len(stack_trace) > 0) else {}
                    # Deterministically get source code and variables for top frame or error location
                    file = top_frame.get("file") or (isinstance(error_context, dict) and error_context.get("file"))
                    line = top_frame.get("line") or (isinstance(error_context, dict) and error_context.get("line"))
                    frame_id = top_frame.get("frame_id")
                    
                    if file and line and state["remaining_budget"] > 0:
                        await self._run_mcp_tool("get_source_context", {"execution_id": execution_id, "file": file, "line": line}, state, telemetry, session)
                        telemetry["investigation_depth"] += 1
                        
                    if frame_id is not None and state["remaining_budget"] > 0:
                        await self._run_mcp_tool("get_frame_variables", {"execution_id": execution_id, "frame_id": frame_id}, state, telemetry, session)
                        telemetry["investigation_depth"] += 1

                # Fast path: For syntax, parse, or compilation errors where source lines are already fetched,
                # no dynamic execution paths, traces, or variables exist.
                err_type = str(error_context.get("error_type", "") if isinstance(error_context, dict) else "").lower()
                err_msg = str(error_context.get("message", "") if isinstance(error_context, dict) else "").lower()
                is_static_error = any(k in err_type or k in err_msg for k in ["syntaxerror", "compilation", "compile", "unterminated", "indentationerror"])
                has_source = any(entry.get("source") == "get_source_context" for entry in state.get("known_context", []))
                
                if is_static_error and has_source:
                    telemetry["stop_reason"] = "root_cause_identified"
                    app_logger.debug("root_cause_identified: execution_id=%s static failure '%s'", execution_id, err_type)
                    return

        # PHASE 2: LLM Curation (Only if necessary)
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        system_prompt = f"""You are the Dynamic Context Curator. 
Your goal is to gather ONLY the runtime context relevant to diagnosing a failure.
Based on the error, investigate backwards, forwards, stack, or path incrementally.

Available tools:
{tool_descriptions}

CRITICAL STOPPING RULES:
1. Once you have sufficient evidence to identify the root cause of the failure (e.g. you know what failed, on what line, and the source code and variables are present), you MUST stop immediately by setting is_sufficient to True and tool_calls to an empty list.
2. For syntax errors, parse errors, or compilation errors, there are NO runtime execution paths or trace events. Once the error context and failing source code lines are present, DO NOT call get_execution_path, search_trace, or get_event. Stop immediately with is_sufficient = True.
3. Do not retrieve redundant or already known information.
"""

        while state["remaining_budget"] > 0:
            prompt = f"Current State: {json.dumps(state['known_context'])}\nRemaining Budget: {state['remaining_budget']}\nWhat context should we retrieve next? If we have enough evidence to diagnose the bug, stop."
            
            llm_start = time.time()
            telemetry["llm_calls"] += 1
            try:
                invoke_kwargs = {}
                if tracker is not None:
                    invoke_kwargs["config"] = {"callbacks": [tracker]}
                decision: RetrievalDecision = await self.decision_model.ainvoke([
                    ("system", system_prompt),
                    ("human", prompt)
                ], **invoke_kwargs)
                telemetry["llm_successes"] += 1
                telemetry["llm_time"] += (time.time() - llm_start)
                
                if decision is None:
                    app_logger.warning("curation_decision_none: execution_id=%s", execution_id)
                    telemetry["stop_reason"] = "no_further_context_available"
                    break

                duration_ms = round((time.time() - llm_start) * 1000.0, 2)
                logger.info(
                    f"[llm_decision] step={telemetry['mcp_calls'] + 1} direction={decision.direction} is_sufficient={decision.is_sufficient}"
                )
                app_logger.debug(
                    "llm_decision: execution_id=%s step=%d direction=%s is_sufficient=%s duration_ms=%.2f reason=%s",
                    execution_id, telemetry["mcp_calls"] + 1, decision.direction, decision.is_sufficient, duration_ms, decision.reason
                )
            except Exception as e:
                telemetry["llm_failures"] += 1
                telemetry["llm_time"] += (time.time() - llm_start)
                error_msg = repr(e)
                if "429" in error_msg or "Too Many Requests" in error_msg or "Rate limit exceeded" in error_msg or "free-models-per-day" in error_msg:
                    telemetry["stop_reason"] = "llm_rate_limit_exceeded"
                    app_logger.warning("LLM rate limit exceeded during curation: %s", error_msg)
                else:
                    telemetry["stop_reason"] = "curator_error"
                    app_logger.warning("LLM error during curation: %s", error_msg, exc_info=True)
                break

            telemetry["investigation_directions"].add(decision.direction)

            if decision.is_sufficient:
                telemetry["stop_reason"] = "root_cause_identified"
                app_logger.debug("root_cause_identified: execution_id=%s reason=%s", execution_id, decision.reason)
                break
                
            if not decision.tool_calls:
                if not decision.is_sufficient:
                    telemetry["stop_reason"] = "no_further_context_available"
                    app_logger.debug("curation_stop: execution_id=%s incomplete", execution_id)
                break
                
            telemetry["investigation_depth"] += 1
            
            # Execute requested tools
            for call in decision.tool_calls:
                if state["remaining_budget"] <= 0:
                    break
                await self._run_mcp_tool(call.tool_name, call.tool_args, state, telemetry, session)

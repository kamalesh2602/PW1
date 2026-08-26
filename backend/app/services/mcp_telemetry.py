"""Small, replaceable telemetry boundary for MCP tool calls."""
import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable


logger = logging.getLogger("app.mcp.telemetry")


def record_tool_call(tool_name: str, execution_id: str | None, operation: Callable[[], Any]) -> Any:
    """Run a query and emit structured, non-sensitive operational telemetry."""
    started = perf_counter()
    success = False
    result: Any = None
    try:
        result = operation()
        success = not (isinstance(result, dict) and "error" in result)
        return result
    finally:
        payload = {
            "execution_id": execution_id,
            "mcp_tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "query_duration_ms": round((perf_counter() - started) * 1000, 3),
            "result_size": len(json.dumps(result, default=str)) if result is not None else 0,
            "events_returned": len(result) if isinstance(result, list) else 0,
        }
        logger.info("mcp_telemetry=%s", json.dumps(payload, default=str))

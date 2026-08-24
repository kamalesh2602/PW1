"""Normalises language-specific runtime artifacts into the common trace model."""
from datetime import datetime, timezone
import os
import re
from typing import Any
from app.models.execution import ExecutionResponse
from app.models.trace import StackFrame, TraceEvent, TraceException, TraceExecution


class TraceBuilder:
    MAX_EVENTS = int(os.getenv("TRACE_MAX_EVENTS", "2000"))

    def build(self, execution_id: str, language: str, code: str, result: ExecutionResponse) -> TraceExecution:
        raw = (result.trace_artifact or {}).get("events", [])
        events = [TraceEvent.model_validate(event) for event in raw[:self.MAX_EVENTS]]
        if not events:
            events = self._fallback_events(language, code, result)
        error = next((event.exception for event in reversed(events) if event.exception), None)
        return TraceExecution(
            execution_id=execution_id, language=language, status=result.status.value,
            started_at=datetime.now(timezone.utc), duration=result.execution_time,
            source_files={self._filename(language, code): code},
            events=events, error_summary=error,
            truncated=len(raw) > self.MAX_EVENTS or bool((result.trace_artifact or {}).get("truncated")),
            total_events_captured=len(raw) or len(events),
        )

    def _fallback_events(self, language: str, code: str, result: ExecutionResponse) -> list[TraceEvent]:
        filename = self._filename(language, code)
        events = [TraceEvent(event_id=1, event_type="program_start", language=language, file=filename)]
        event_id = 2
        if language == "java":
            stack_calls = re.findall(r"\bat\s+[\w.$]+\.(\w+)\(([^:()]+\.java):(\d+)\)", result.stderr)
            # JVM prints innermost-to-outermost; execution order is the reverse.
            calls = [(name, int(line)) for name, file, line in reversed(stack_calls) if file == filename]
            if not calls:
                calls = [(match.group(1), code[:match.start()].count("\n") + 1) for match in re.finditer(r"(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{", code)]
            for name, line in calls:
                events.append(TraceEvent(event_id=event_id, event_type="function_call", language=language, file=filename, line=line, function=name))
                event_id += 1
        if result.status.value == "compile_error":
            line_match = re.search(r":(\d+):\s+error:\s*(.*)", result.stderr)
            events.append(TraceEvent(event_id=event_id, event_type="compilation_error", language=language, file=filename,
                line=int(line_match.group(1)) if line_match else None, function=None,
                exception=TraceException(type="CompilationError", message=line_match.group(2) if line_match else result.stderr[:500])))
            return events
        if result.status.value in {"runtime_error", "timeout"}:
            exc = self._exception(language, result.stderr, result.status.value)
            line = self._error_line(language, result.stderr)
            frames = []
            if language == "java":
                for index, (function, frame_file, frame_line) in enumerate(re.findall(r"\bat\s+[\w.$]+\.(\w+)\(([^:()]+\.java):(\d+)\)", result.stderr)):
                    if frame_file == filename:
                        frames.append(StackFrame(frame_id=index, function=function, file=frame_file, line=int(frame_line)))
            events.append(TraceEvent(event_id=event_id, event_type="exception", language=language, file=filename, line=line, exception=exc, stack=frames))
            event_id += 1
        events.append(TraceEvent(event_id=event_id, event_type="program_end", language=language, file=filename))
        return events

    def _filename(self, language: str, code: str) -> str:
        if language == "python":
            return "script.py"
        match = re.search(r"\b(?:public\s+)?class\s+([A-Za-z_]\w*)", code)
        return f"{match.group(1) if match else 'Main'}.java"

    def _exception(self, language: str, stderr: str, status: str) -> TraceException:
        if status == "timeout": return TraceException(type="Timeout", message=stderr[:500])
        if language == "python":
            match = re.search(r"([A-Za-z_][\w.]*Error|Exception):\s*(.*)", stderr)
        else:
            match = re.search(r"(?:Exception in thread .*? )?([\w.]+(?:Exception|Error)):\s*(.*)", stderr)
        return TraceException(type=match.group(1).split(".")[-1] if match else "RuntimeError", message=match.group(2)[:500] if match else stderr[:500])

    def _error_line(self, language: str, stderr: str) -> int | None:
        pattern = r'File "script\.py", line (\d+)' if language == "python" else r'\((?:Main|[\w$]+)\.java:(\d+)\)'
        matches = re.findall(pattern, stderr)
        return int(matches[-1]) if matches else None

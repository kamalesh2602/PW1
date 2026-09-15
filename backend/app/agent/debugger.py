from typing import Any

from app.agent.llm import get_llm
from app.agent.mcp_client import get_debugging_tools
from app.agent.models import DebugDiagnosis

from langchain_core.messages import ToolMessage


SYSTEM_PROMPT = """
You are an AI debugging agent.

Your job is to diagnose a runtime failure using selective
runtime information.

IMPORTANT RULES:

1. Start with the runtime error.
2. Do NOT request the entire trace.
3. Do NOT request unnecessary information.
4. Use debugging tools only when the information is needed.
5. Prefer small, targeted source and variable queries.
6. Use the stack trace when you need call-chain information.
7. Use execution_path only when control-flow information is useful.
8. Use search_trace when a specific event or pattern must be found.
9. Base your diagnosis on evidence returned by the tools.
10. Do not invent runtime values.

When you have enough evidence, return a structured diagnosis
containing:

- diagnosis
- root_cause
- evidence
- suggested_fix
- confidence

The diagnosis must clearly explain the actual cause of the
runtime failure.
"""


class DebuggingAgent:

    def __init__(self):

        self.llm = get_llm()

        self.tools = get_debugging_tools()

        self.tools_by_name = {
            tool.name: tool
            for tool in self.tools
        }

        self.model = self.llm.bind_tools(
            self.tools
        )

        self.structured_model = self.llm.with_structured_output(
            DebugDiagnosis
        )

    async def diagnose(
        self,
        execution_id: str,
        initial_context: str | None = None,
    ) -> DebugDiagnosis:

        queries_used: list[str] = []

        tool_results: dict[str, Any] = {}

        user_prompt = f"""
Diagnose the runtime failure for execution:

execution_id = {execution_id}

Initial context:
{initial_context or "No additional context was provided."}

Start by obtaining the runtime error.

Then decide what additional information is necessary.

Do not request unnecessary trace information.
"""

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]

        max_iterations = 8

        # ------------------------------------------------
        # Agent tool-calling loop
        # ------------------------------------------------

        for _ in range(max_iterations):

            response = await self.model.ainvoke(
                messages
            )

            messages.append(response)

            # --------------------------------------------
            # Model has finished gathering information
            # --------------------------------------------

            if not response.tool_calls:

                return await self._create_structured_diagnosis(
                    execution_id=execution_id,
                    messages=messages,
                    queries_used=queries_used,
                    tool_results=tool_results,
                )

            # --------------------------------------------
            # Execute requested tools
            # --------------------------------------------

            for tool_call in response.tool_calls:

                tool_name = tool_call["name"]

                tool_args = tool_call.get(
                    "args",
                    {},
                )

                queries_used.append(tool_name)

                tool = self.tools_by_name.get(
                    tool_name
                )

                if tool is None:

                    tool_result = {
                        "error": (
                            f"Unknown debugging tool: "
                            f"{tool_name}"
                        )
                    }

                else:

                    try:

                        # LangChain StructuredTool can execute
                        # synchronous functions in a worker thread
                        # through ainvoke().
                        tool_result = await tool.ainvoke(
                            tool_args
                        )

                    except Exception as exc:

                        tool_result = {
                            "error": (
                                f"Tool execution failed: "
                                f"{str(exc)}"
                            )
                        }

                tool_results[tool_name] = tool_result

                messages.append(
                    ToolMessage(
                        content=self._serialize(
                            tool_result
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )

        # ------------------------------------------------
        # Maximum iterations reached
        # ------------------------------------------------

        return DebugDiagnosis(
            execution_id=execution_id,

            error=tool_results.get(
                "get_error_context"
            ),

            diagnosis=(
                "The debugging agent reached its maximum "
                "number of tool calls before completing "
                "the diagnosis."
            ),

            root_cause="",

            evidence=[],

            queries_used=queries_used,

            confidence=0.0,

            suggested_fix=None,
        )

    async def _create_structured_diagnosis(
        self,
        execution_id: str,
        messages: list[Any],
        queries_used: list[str],
        tool_results: dict[str, Any],
    ) -> DebugDiagnosis:

        diagnosis_prompt = """
Based on the debugging conversation and tool results above,
produce the final structured diagnosis.

Requirements:

1. diagnosis:
   Clearly explain what happened.

2. root_cause:
   Explain the exact underlying programming mistake.

3. evidence:
   List concrete evidence obtained from debugging tools.
   Do not invent evidence.

4. suggested_fix:
   Give a practical code-level fix.

5. confidence:
   Give a value between 0.0 and 1.0 based on the strength
   of the evidence.

Only use information available in the debugging conversation.
"""

        structured_messages = list(messages)

        structured_messages.append(
            (
                "human",
                diagnosis_prompt,
            )
        )

        try:

            result = await self.structured_model.ainvoke(
                structured_messages
            )

            result.execution_id = execution_id

            result.error = tool_results.get(
                "get_error_context"
            )

            result.queries_used = queries_used

            return result

        except Exception as exc:

            return DebugDiagnosis(
                execution_id=execution_id,

                error=tool_results.get(
                    "get_error_context"
                ),

                diagnosis=(
                    "The agent gathered debugging evidence "
                    "but failed to produce structured output: "
                    f"{str(exc)}"
                ),

                root_cause="",

                evidence=[],

                queries_used=queries_used,

                confidence=0.0,

                suggested_fix="No reliable code fix could be generated because structured diagnosis failed.",
            )

    @staticmethod
    def _serialize(value: Any) -> str:

        if isinstance(value, str):
            return value

        return str(value)
import asyncio
from typing import Any

from langchain_core.tools import StructuredTool

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_SERVER_URL = "http://localhost:8000/mcp"


def _run_async(coro):
    """
    Run an async MCP operation from our synchronous
    LangChain tool functions.
    """

    try:
        loop = asyncio.get_running_loop()

    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # The current code path is synchronous, so normally
        # there should not be an active event loop here.
        # If there is one, run the coroutine in a separate thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1
        ) as executor:

            future = executor.submit(
                asyncio.run,
                coro,
            )

            return future.result()

    return asyncio.run(coro)


async def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """
    Connect to the MCP server and call one MCP tool.
    """

    async with streamable_http_client(
        MCP_SERVER_URL
    ) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments,
            )

            # MCP returns structured content when available.
            if result.structured_content is not None:
                return result.structured_content

            # Otherwise extract normal text content.
            output = []

            for content in result.content:

                if hasattr(content, "text"):
                    output.append(content.text)

            return "\n".join(output)


def get_error_context(
    execution_id: str,
) -> Any:
    """
    Retrieve the most relevant runtime error
    through the MCP server.
    """

    return _run_async(
        _call_mcp_tool(
            "get_error_context",
            {
                "execution_id": execution_id,
            },
        )
    )


def get_stack_trace(
    execution_id: str,
) -> Any:
    """
    Retrieve stack frames through MCP.
    """

    return _run_async(
        _call_mcp_tool(
            "get_stack_trace",
            {
                "execution_id": execution_id,
            },
        )
    )


def get_frame_variables(
    execution_id: str,
    frame_id: int,
) -> Any:
    """
    Retrieve frame variables through MCP.
    """

    return _run_async(
        _call_mcp_tool(
            "get_frame_variables",
            {
                "execution_id": execution_id,
                "frame_id": frame_id,
            },
        )
    )


def get_source_context(
    execution_id: str,
    file: str,
    line: int,
    radius: int = 3,
) -> Any:
    """
    Retrieve targeted source context through MCP.
    """

    return _run_async(
        _call_mcp_tool(
            "get_source_context",
            {
                "execution_id": execution_id,
                "file": file,
                "line": line,
                "radius": radius,
            },
        )
    )


def get_execution_path(
    execution_id: str,
    max_events: int = 50,
) -> Any:
    """
    Retrieve bounded execution path through MCP.
    """

    return _run_async(
        _call_mcp_tool(
            "get_execution_path",
            {
                "execution_id": execution_id,
                "max_events": max_events,
            },
        )
    )


def get_event(
    execution_id: str,
    event_id: int,
) -> Any:
    """
    Retrieve one detailed event through MCP.
    """

    return _run_async(
        _call_mcp_tool(
            "get_event",
            {
                "execution_id": execution_id,
                "event_id": event_id,
            },
        )
    )


def search_trace(
    execution_id: str,
    event_type: str | None = None,
    function: str | None = None,
    variable: str | None = None,
    file: str | None = None,
    exception_type: str | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
    max_results: int = 20,
) -> Any:
    """
    Search trace events through MCP.
    """

    arguments = {
        "execution_id": execution_id,
        "event_type": event_type,
        "function": function,
        "variable": variable,
        "file": file,
        "exception_type": exception_type,
        "line_start": line_start,
        "line_end": line_end,
        "max_results": max_results,
    }

    # Remove optional parameters that were not provided.
    arguments = {
        key: value
        for key, value in arguments.items()
        if value is not None
    }

    return _run_async(
        _call_mcp_tool(
            "search_trace",
            arguments,
        )
    )


def get_debugging_tools():
    """
    Convert MCP-backed debugging operations into
    LangChain tools for the debugging agent.
    """

    return [

        StructuredTool.from_function(
            func=get_error_context,
            name="get_error_context",
            description=(
                "Retrieve the most relevant runtime error "
                "through the MCP debugging server. "
                "Use this first."
            ),
        ),

        StructuredTool.from_function(
            func=get_stack_trace,
            name="get_stack_trace",
            description=(
                "Retrieve captured stack frames "
                "through the MCP debugging server."
            ),
        ),

        StructuredTool.from_function(
            func=get_frame_variables,
            name="get_frame_variables",
            description=(
                "Retrieve local variables for one stack frame "
                "through the MCP debugging server."
            ),
        ),

        StructuredTool.from_function(
            func=get_source_context,
            name="get_source_context",
            description=(
                "Retrieve a small source region around a "
                "recorded location through MCP."
            ),
        ),

        StructuredTool.from_function(
            func=get_execution_path,
            name="get_execution_path",
            description=(
                "Retrieve a bounded execution path "
                "through the MCP debugging server."
            ),
        ),

        StructuredTool.from_function(
            func=get_event,
            name="get_event",
            description=(
                "Retrieve one detailed runtime event "
                "through the MCP debugging server."
            ),
        ),

        StructuredTool.from_function(
            func=search_trace,
            name="search_trace",
            description=(
                "Search trace events using optional filters "
                "through the MCP debugging server."
            ),
        ),
    ]
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():

    print("Connecting to MCP server...")

    async with streamable_http_client(
        "http://localhost:8000/mcp"
    ) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            print("Initializing MCP session...")

            await session.initialize()

            print("MCP connection successful!")

            tools = await session.list_tools()

            print("\nAvailable MCP tools:")

            for tool in tools.tools:
                print(f"- {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())
"""Secret-safe live MCP smoke test used by Docker CI."""

from __future__ import annotations

import asyncio
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    endpoint = os.environ.get("MCP_SMOKE_URL", "http://127.0.0.1:8000/mcp")
    token = os.environ.get("MCP_SMOKE_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with (
        httpx.AsyncClient(headers=headers, timeout=10) as client,
        streamable_http_client(endpoint, http_client=client) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_health_overview", {"days": 7})
        if initialized.serverInfo.name != "google-health-agent":
            raise RuntimeError("Unexpected MCP server identity.")
        if len(tools.tools) != 8:
            raise RuntimeError("Unexpected MCP tool contract.")
        if result.isError or not result.structuredContent:
            raise RuntimeError("MCP overview smoke test failed.")
        if result.structuredContent.get("data_label") != "SYNTHETIC DATA":
            raise RuntimeError("Docker smoke test did not return synthetic data.")
    print("Live MCP smoke test passed with synthetic data.")


if __name__ == "__main__":
    asyncio.run(main())

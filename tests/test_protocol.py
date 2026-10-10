import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_lists_tools_and_keeps_cli_input_separate():
    async def run():
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        async with stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "agent_reach_plus.server"], env=env)) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = {t.name for t in (await client.list_tools()).tools}
                assert len(tools) == 9 and "get_status" in tools
                result = await client.call_tool("agent_reach_fetch_url", {"url": "http://127.0.0.1/"})
                payload = json.loads(result.content[0].text)
                assert payload["ok"] is False and payload["error"]["code"] == "invalid_url"
    asyncio.run(run())

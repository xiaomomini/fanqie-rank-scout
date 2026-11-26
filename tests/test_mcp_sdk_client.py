"""用官方 MCP Python SDK 当真实客户端，端到端验证 fanqie_rank_mcp.py。"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.expanduser("~/projects/fanqie-rank-scout/fanqie_rank_mcp.py")


async def main():
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("initialize:", init.protocol_version, "|", init.server_info.name, init.server_info.version)
            print("capabilities:", init.capabilities.model_dump(exclude_none=True))

            tools = await session.list_tools()
            print("tools:", [(t.name, bool(t.output_schema)) for t in tools.tools])

            res = await session.call_tool("list_categories", {"board": "female-new"})
            print("list_categories(female-new):", str(res.content[0].text)[:110])
            print("  structured keys:", list(res.structured_content.keys()) if res.structured_content else None)

            res = await session.call_tool("rank_list", {"board": "female-new", "category": "古言脑洞", "limit": 3})
            print("rank_list is_error:", res.is_error)
            print(res.content[0].text)

            res = await session.call_tool("rank_list", {"board": "female-new", "category": "都市异能", "limit": 3, "resolve": False})
            print("rank_list resolve=False is_error:", res.is_error)
            print(res.content[0].text[:400])


asyncio.run(main())

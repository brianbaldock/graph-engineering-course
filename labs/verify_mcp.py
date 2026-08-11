import asyncio
import sys

sys.argv = ["mcp_server.py", "/tmp/lab_verify.db"]
import mcp_server

tools = asyncio.run(mcp_server.mcp.list_tools())
print("MCP server loaded. Tools registered:")
for t in tools:
    print(f"  - {t.name}: {(t.description or '').splitlines()[0]}")

print()
print(mcp_server.add_knowledge("Dana joined Fabrikam 2025.", "verify", "2025-01-01"))
print(mcp_server.search_entities("Dana"))
print(mcp_server.get_subgraph(["Dana"], hops=1))
print(mcp_server.graph_stats())

"""
PAAIM MCP server — exposes the Factory Context Graph over the Model Context
Protocol so any MCP client (Claude Desktop, external agents, our own agents)
can query factory context through one standard, auditable interface instead of
hardcoded calls.

Spec-compliant JSON-RPC 2.0 over stdio, hand-rolled (the official `mcp` SDK
requires Python 3.10+; this runs on 3.9). Implements: initialize,
resources/list, resources/read, tools/list, tools/call.

Run:
    cd backend && source venv/bin/activate
    python -m paaim.mcp_server
"""

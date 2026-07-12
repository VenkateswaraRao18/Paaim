"""
MCP stdio server entrypoint — newline-delimited JSON-RPC 2.0 over stdin/stdout.

Implements the MCP methods an client needs: initialize, resources/list,
resources/read, tools/list, tools/call, ping. Logs go to stderr so stdout
stays a clean JSON-RPC channel.

Register with Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "paaim-factory": {
          "command": "/path/to/backend/venv/bin/python",
          "args": ["-m", "paaim.mcp_server"],
          "cwd": "/path/to/backend"
        }
      }
    }
"""

import asyncio
import json
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./paaim_dev.db")

from paaim.mcp_server.handlers import (
    RESOURCES, TOOLS, read_resource, call_tool,
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "paaim-factory-context", "version": "1.0.0"}


def _log(msg: str) -> None:
    print(f"[paaim-mcp] {msg}", file=sys.stderr, flush=True)


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def handle(msg: dict):
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params", {}) or {}

    # Notifications (no id) — no response.
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _result(req_id, {})

    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"resources": {}, "tools": {}},
            "serverInfo": SERVER_INFO,
        })

    if method == "resources/list":
        return _result(req_id, {"resources": RESOURCES})

    if method == "resources/read":
        uri = params.get("uri", "")
        try:
            body = await read_resource(uri)
            return _result(req_id, {"contents": [
                {"uri": uri, "mimeType": "application/json",
                 "text": json.dumps(body, indent=2, default=str)}
            ]})
        except Exception as e:
            return _error(req_id, -32602, f"resource read failed: {e}")

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        try:
            out = await call_tool(name, args)
            return _result(req_id, {
                "content": [{"type": "text", "text": json.dumps(out, indent=2, default=str)}],
                "isError": False,
            })
        except Exception as e:
            return _result(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    return _error(req_id, -32601, f"Method not found: {method}")


async def main():
    _log("PAAIM Factory Context MCP server ready (stdio)")
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        line = line.decode().strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = await handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        pass

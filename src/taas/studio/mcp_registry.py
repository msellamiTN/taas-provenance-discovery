"""Read-only MCP server inspection for TaaS Studio.

Only operator-configured stdio servers may be spawned. Browser users cannot
supply commands, arguments, URLs, or environment values. This module lists
tool contracts only; it never invokes tools/call.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any


class MCPRegistryError(RuntimeError):
    """MCP registry configuration or connection failure."""


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def _load_config() -> list[dict[str, Any]]:
    raw = os.environ.get("TAAS_MCP_SERVERS_JSON", "").strip()
    path = os.environ.get("TAAS_MCP_SERVERS_FILE", "").strip()
    if raw and path:
        raise MCPRegistryError("Set only one of TAAS_MCP_SERVERS_JSON or TAAS_MCP_SERVERS_FILE")
    if path:
        config_path = Path(path).expanduser().resolve()
        if not config_path.is_file():
            raise MCPRegistryError("Configured MCP server registry file does not exist")
        raw = config_path.read_text(encoding="utf-8")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MCPRegistryError("MCP server registry must be valid JSON") from exc
    if not isinstance(parsed, list) or len(parsed) > 50:
        raise MCPRegistryError("MCP server registry must be an array of at most 50 entries")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise MCPRegistryError(f"MCP server entry {index} must be an object")
        server_id = item.get("id")
        name = item.get("name")
        command = item.get("command")
        args = item.get("args", [])
        env_keys = item.get("env", [])
        if not isinstance(server_id, str) or not _ID.fullmatch(server_id) or server_id in seen:
            raise MCPRegistryError(f"MCP server entry {index} has an invalid or duplicate id")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise MCPRegistryError(f"MCP server {server_id} requires a display name")
        if not isinstance(command, str) or not command.strip() or len(command) > 512:
            raise MCPRegistryError(f"MCP server {server_id} requires an executable command")
        if not isinstance(args, list) or len(args) > 64 or any(not isinstance(x, str) or len(x) > 2048 for x in args):
            raise MCPRegistryError(f"MCP server {server_id} args must be an array of strings")
        if not isinstance(env_keys, list) or len(env_keys) > 64 or any(
            not isinstance(x, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", x) for x in env_keys
        ):
            raise MCPRegistryError(f"MCP server {server_id} env must list environment variable names")
        seen.add(server_id)
        normalized.append({"id": server_id, "name": name.strip(), "command": command,
                           "args": args, "env": env_keys, "transport": "stdio"})
    return normalized


def list_servers() -> dict[str, Any]:
    servers = _load_config()
    return {"count": len(servers), "servers": [
        {"id": item["id"], "name": item["name"], "transport": "stdio",
         "configured": True, "credentials_configured": all(k in os.environ for k in item["env"])}
        for item in servers
    ]}


async def _inspect_stdio(server: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise MCPRegistryError("Install MCP support with: pip install -e '.[mcp]'") from exc

    missing = [key for key in server["env"] if key not in os.environ]
    if missing:
        raise MCPRegistryError("Missing required environment variables: " + ", ".join(missing))
    child_env = {key: os.environ[key] for key in server["env"]}
    params = StdioServerParameters(command=server["command"], args=server["args"], env=child_env)

    async def inspect() -> dict[str, Any]:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                result = await session.list_tools()
                tools = []
                for tool in result.tools:
                    tools.append({
                        "server": server["id"],
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema or {"type": "object", "properties": {}},
                        "output_schema": getattr(tool, "outputSchema", None),
                        "annotations": tool.annotations.model_dump(exclude_none=True)
                            if getattr(tool, "annotations", None) is not None else None,
                        "source": "mcp-live-inspection",
                        "category": "mcp",
                    })
                info = getattr(initialized, "serverInfo", None)
                return {
                    "server_id": server["id"],
                    "server_name": server["name"],
                    "server_info": ({"name": info.name, "version": info.version}
                                    if info is not None else None),
                    "protocol_version": getattr(initialized, "protocolVersion", None),
                    "tool_count": len(tools),
                    "tools": tools,
                    "inspection_only": True,
                    "tool_execution_performed": False,
                }
    try:
        return await asyncio.wait_for(inspect(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise MCPRegistryError(f"Timed out inspecting MCP server {server['id']}") from exc
    except MCPRegistryError:
        raise
    except Exception as exc:
        raise MCPRegistryError(f"MCP inspection failed for {server['id']}: {type(exc).__name__}: {exc}") from exc


def inspect_server(server_id: str, timeout_seconds: float = 20.0) -> dict[str, Any]:
    if not _ID.fullmatch(server_id):
        raise ValueError("Invalid MCP server id")
    servers = {item["id"]: item for item in _load_config()}
    if server_id not in servers:
        raise ValueError("Unknown MCP server id")
    return asyncio.run(_inspect_stdio(servers[server_id], timeout_seconds))

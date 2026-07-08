from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class McpStdioError(RuntimeError):
    pass


def _dump_message(message: dict[str, Any]) -> str:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"


def _write_message(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise McpStdioError("MCP server stdin is not available")
    proc.stdin.write(_dump_message(message))
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen[str]) -> dict[str, Any]:
    if proc.stdout is None:
        raise McpStdioError("MCP server stdout is not available")
    line = proc.stdout.readline()
    if not line:
        raise McpStdioError("MCP server closed stdout before sending a response")
    try:
        response = json.loads(line)
    except json.JSONDecodeError as exc:
        raise McpStdioError(f"MCP server returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise McpStdioError("MCP server returned a non-object JSON-RPC response")
    if response.get("error"):
        raise McpStdioError(f"MCP server error: {response['error']}")
    return response


def _request(proc: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    _write_message(proc, message)
    response = _read_response(proc)
    return response.get("result") or {}


def _close_process(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None and not proc.stdin.closed:
        proc.stdin.close()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


def call_stdio_tool(
    command: str,
    *,
    save_path: str | Path | None = None,
    tool_name: str = "sese_board_game",
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Call the packaged MCP stdio server once and return run_command() payload."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "sese_board_game.mcp_server"],
        cwd=str(cwd) if cwd is not None else None,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        _request(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "sese-board-game-http-bridge", "version": "0.1.0"},
            },
        )
        _write_message(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        arguments: dict[str, Any] = {"command": command}
        if save_path is not None:
            arguments["save_path"] = str(save_path)
        result = _request(proc, 2, "tools/call", {"name": tool_name, "arguments": arguments})
        payload = result.get("structuredContent")
        if not isinstance(payload, dict):
            raise McpStdioError("MCP tool result did not include structuredContent payload")
        return payload
    finally:
        _close_process(proc)

from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from sese_board_game.mcp_stdio_client import call_stdio_tool


GAME_DIR = Path(__file__).resolve().parent
SAVE_PATH = Path(tempfile.gettempdir()) / "sese-board-game-mcp-preview.json"


def run_via_mcp(command: str) -> dict:
    return call_stdio_tool(command, save_path=SAVE_PATH, cwd=GAME_DIR)


class McpPreviewHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "transport": "mcp-stdio",
                    "mcp_server": "python3 -m sese_board_game.mcp_server",
                    "save_path": str(SAVE_PATH),
                }
            )
            return
        if path == "/state":
            self._send_json(run_via_mcp("status"))
            return
        self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/command":
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            command = str(body.get("command") or "").strip() or "status"
            self._send_json(run_via_mcp(command))
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[mcp-preview] {self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8766), McpPreviewHandler)
    print("Sese Board Game MCP preview bridge: http://127.0.0.1:8766")
    print("Frontend can keep using http://127.0.0.1:8766/command")
    print(f"MCP preview save: {SAVE_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()

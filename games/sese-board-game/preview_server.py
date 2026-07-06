from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from sese_board_game.engine import run_command


SAVE_PATH = Path(tempfile.gettempdir()) / "sese-board-game-preview.json"


class PreviewHandler(BaseHTTPRequestHandler):
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
            self._send_json({"ok": True, "save_path": str(SAVE_PATH)})
            return
        if path == "/state":
            self._send_json(run_command("status", save_path=SAVE_PATH))
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
            self._send_json(run_command(command, save_path=SAVE_PATH))
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[preview] {self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8766), PreviewHandler)
    print("Sese Board Game preview API: http://127.0.0.1:8766")
    print(f"Preview save: {SAVE_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()

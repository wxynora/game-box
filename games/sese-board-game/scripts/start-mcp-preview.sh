#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend/preview"
API_BASE="http://127.0.0.1:8766"
FRONTEND_URL="http://127.0.0.1:5176/"
BRIDGE_PID=""

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

cleanup() {
  if [ -n "$BRIDGE_PID" ] && kill -0 "$BRIDGE_PID" >/dev/null 2>&1; then
    kill "$BRIDGE_PID" >/dev/null 2>&1 || true
    wait "$BRIDGE_PID" >/dev/null 2>&1 || true
  fi
}

wait_for_bridge() {
  if ! command -v curl >/dev/null 2>&1; then
    sleep 2
    return
  fi

  for _ in $(seq 1 30); do
    if curl -fsS "$API_BASE/health" 2>/dev/null | grep -q "mcp-stdio"; then
      return
    fi
    if [ -n "$BRIDGE_PID" ] && ! kill -0 "$BRIDGE_PID" >/dev/null 2>&1; then
      echo "MCP preview bridge stopped before it became ready." >&2
      echo "Port 8766 may already be used by another preview server." >&2
      exit 1
    fi
    sleep 0.2
  done

  echo "Timed out waiting for MCP preview bridge at $API_BASE." >&2
  echo "Port 8766 may already be used by another preview server." >&2
  exit 1
}

need_command python3
need_command npm

trap cleanup EXIT INT TERM

echo "Starting Sese Board MCP preview bridge..."
(cd "$ROOT_DIR" && python3 mcp_preview_server.py) &
BRIDGE_PID="$!"
wait_for_bridge

if [ -z "${SESE_BOARD_NODE_MODULES:-}" ] \
  && [ ! -d "$FRONTEND_DIR/node_modules/react" ] \
  && [ ! -d "$ROOT_DIR/node_modules/react" ]; then
  echo "Installing frontend dependencies..."
  npm install --prefix "$FRONTEND_DIR"
fi

echo
echo "Sese Board Game is starting."
echo "Open: $FRONTEND_URL"
echo "API:  $API_BASE"
echo "Press Ctrl-C to stop both servers."
echo

cd "$FRONTEND_DIR"
npm run dev

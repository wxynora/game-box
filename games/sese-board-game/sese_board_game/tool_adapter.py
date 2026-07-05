from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .engine import GAME_ID, run_command


TOOL_NAME = GAME_ID


def default_save_path() -> Path:
    return Path(os.environ.get("SESE_BOARD_GAME_SAVE", ".sese_board_game.json"))


def get_tools_for_inject() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": (
                    "Run one Sese Board Game command and return the board, public state, pending event, and player-facing text. "
                    "Useful commands: status, new_game, roll, roll 3, submit <text>, approve, reject, choose <id>, pass, end_game."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Game command, for example: status, roll, submit <text>, approve, choose add_prop, pass, new_game.",
                        },
                        "save_path": {
                            "type": "string",
                            "description": "Optional JSON save path. Defaults to SESE_BOARD_GAME_SAVE or .sese_board_game.json.",
                        },
                    },
                    "required": ["command"],
                },
            },
        }
    ]


def execute_tool(arguments: dict[str, Any] | None = None) -> str:
    args = arguments if isinstance(arguments, dict) else {}
    command = str(args.get("command") or "status")
    save_path = args.get("save_path") or default_save_path()
    payload = run_command(command, save_path=save_path)
    return json.dumps(payload, ensure_ascii=False)

from __future__ import annotations
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
                    "执行涩涩走格棋的一步命令，并返回棋盘、公开状态、待处理事件和玩家可读文本。"
                    "可用命令：status、new_game、roll、roll 3、submit <内容>、approve、reject、choose <选项id>、pass、end_game。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "游戏命令，例如：status、roll、submit <内容>、approve、choose add_prop、pass、new_game。",
                        },
                        "save_path": {
                            "type": "string",
                            "description": "可选 JSON 存档路径。默认使用 SESE_BOARD_GAME_SAVE 或当前目录下的 .sese_board_game.json。",
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
    return str(payload.get("ai_text") or payload.get("text") or "").strip()

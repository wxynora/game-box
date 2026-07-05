# Sese Board Game

A portable roll-and-move board game core with optional AI/tool and React UI
adapters.

This open-source version is intentionally separated from any private chat
system, memory system, body-state system, deployment route, or private content
library. The included card pack is a clean sample pack. Projects that embed the
game can replace `sese_board_game/cards.py` with their own content.

## What It Does

- Starts, resets, saves, and loads a JSON game state.
- Runs a 36-cell board with two actors: `player` and `ai`.
- Supports `roll`, manual dice values such as `roll 3`, and deterministic seeds
  such as `new_game seed=demo`.
- Tracks positions, turn actor, theme, reward cards, statuses, pending events,
  winner, and event log.
- Applies board events: pass-card reward, status add/clear/extend/replace,
  movement, position swap, blocked actions, review tasks, and choice penalties.
- Lets a player use a Pass Card to skip a pending penalty.
- Handles review tasks with `submit`, `approve`, and `reject`.
- Handles choice penalties with `choose <choice id>`.
- Exposes a tool schema through `sese_board_game.tool_adapter`.
- Includes a standalone React component in `frontend/SeseBoardGame.tsx`.

## Python Usage

```python
from sese_board_game import cmd, run_command

print(cmd("new_game seed=demo", save_path="./demo-game.json"))
payload = run_command("roll 4", save_path="./demo-game.json")
print(payload["state"]["positions"])
```

Useful commands:

```text
status
new_game
new_game seed=demo size=36
roll
roll 3
submit <text>
approve
reject [reason]
choose <id>
pass
end_game
```

## Tool Adapter

```python
from sese_board_game.tool_adapter import get_tools_for_inject, execute_tool

tools = get_tools_for_inject()
result_json = execute_tool({"command": "roll", "save_path": "./demo-game.json"})
```

The adapter is deliberately generic. A host app can expose it to any model or
backend that knows how to call a function with a `command` string.

## React UI

`frontend/SeseBoardGame.tsx` exports:

- `SeseBoardGame`
- `createHttpExecutor`
- `parseAssistantCommand`

The UI only needs an `executeCommand(command)` prop. It can also receive an
optional `sendToAssistant(payload, context)` prop for host apps that want to
connect an AI player.

No private backend route is required by the component.

## Not Included

- Private chat sync.
- Private recent-memory or archive injection.
- Body-state updates.
- Telegram/QQ/channel wakeups.
- Private explicit content packs.
- Production Flask routes from any one app.

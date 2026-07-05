# Games

Each game lives in its own subdirectory.

Suggested structure:

```text
games/example-game/
  README.md
  manifest.json
  engine.py
  tests/
  adapters/
  frontend/
```

Minimum requirements:

- The rules engine can run without a private backend.
- State storage paths are configurable.
- Player-facing text and AI/tool-facing text are separated.
- No private tokens, accounts, chat logs, or deployment config are committed.

Current games:

- `sese-board-game/`: roll-and-move board game with pass cards, review tasks,
  choice penalties, status tracking, a generic tool adapter, and standalone
  React UI.

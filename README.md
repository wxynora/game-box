# Game Box

Game Box is an open-source collection repo for small reusable games.

This repo keeps portable game cores that are not tied to any private backend,
chat system, memory system, or personal deployment environment. Each game should
try to provide:

- A standalone rules engine
- A command-style entry point, such as `cmd("roll")`
- Optional tool schemas / adapters for different AI or backend integrations
- A frontend example or reusable UI component
- Focused tests and minimal usage notes

## Structure

- `games/`: individual games, one subdirectory per game.
- `packages/`: lightweight shared packages used by multiple games.
- `docs/`: repo conventions, integration notes, and release notes.

## Games

- `games/sese-board-game/`: a portable roll-and-move board game with a Python
  rules engine, command/tool adapter, tests, and a reusable React UI component.

## Integration Boundary

Open-source games in this repo are responsible only for rules, state
transitions, player-facing text, and optional UI.

They should not include private project details:

- Private chat windows, accounts, tokens, or deployment config
- Dynamic memory, body state, archives, proactive wakeups, or other private flows
- Backend routes that only make sense inside one private project

Other projects can integrate a game by calling its `cmd()` entry point or by
using its tool adapter.

## License

PolyForm Noncommercial License 1.0.0 (`PolyForm-Noncommercial-1.0.0`).

The source is available for permitted noncommercial purposes only. Commercial use is not licensed. See [`LICENSE`](LICENSE) for the full terms.

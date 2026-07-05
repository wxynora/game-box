from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
import threading
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .cards import (
    CHOICE_PENALTY_CARDS,
    REVIEW_PENALTY_CARDS,
    REWARD_CARD_LABELS,
    REWARD_CARD_PASS,
    SLOTS,
    THEMES,
)

try:
    import fcntl
except Exception:  # pragma: no cover - fcntl is not available on every platform.
    fcntl = None


GAME_ID = "sese_board_game"
SCHEMA_VERSION = 1
DEFAULT_BOARD_SIZE = 36
DEFAULT_SAVE_PATH = Path(os.environ.get("SESE_BOARD_GAME_SAVE", ".sese_board_game.json"))
ACTORS = ("player", "ai")
DEFAULT_LABELS = {"player": "Player", "ai": "AI"}
COMMAND_HINT = "Commands: status, new_game, roll, roll 3, submit <text>, approve, reject [reason], choose <id>, pass, end_game"

_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actor_label(actor: str, labels: dict[str, str] | None = None) -> str:
    return (labels or DEFAULT_LABELS).get(actor, actor)


def _other(actor: str) -> str:
    return "ai" if actor == "player" else "player"


def _status_label(slot: str) -> str:
    return str(SLOTS.get(slot, {}).get("label") or slot)


def _compact_text(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def _cell(position: int, kind: str, name: str, **extra: Any) -> dict[str, Any]:
    payload = {"position": position, "kind": kind, "name": name}
    payload.update(extra)
    return payload


def build_cell_events(board_size: int = DEFAULT_BOARD_SIZE) -> list[dict[str, Any]]:
    """Return the public board layout.

    The last cell is always the finish cell. If callers use a smaller custom board,
    events beyond the finish are clipped.
    """

    events: list[dict[str, Any]] = [
        _cell(1, "start", "Start"),
        _cell(3, "reward", "Pass Card", reward=REWARD_CARD_PASS),
        _cell(4, "add_status", "Place State", slot="place", duration_type="until_clear"),
        _cell(6, "move", "Move Back", steps=-2),
        _cell(8, "clear_status", "Clear State"),
        _cell(9, "penalty_choice", "Penalty Choice"),
        _cell(11, "penalty_review", "Review Task"),
        _cell(12, "move_reward", "Move Forward", steps=2, reward=REWARD_CARD_PASS),
        _cell(14, "extend_status", "Extend State"),
        _cell(15, "swap_positions", "Swap Positions"),
        _cell(17, "block", "Prop Pause", slot="prop", actions=2),
        _cell(18, "replace_status", "Replace Place", slot="place", duration_type="until_clear"),
        _cell(20, "penalty_choice", "Penalty Choice"),
        _cell(21, "move", "Move Back", steps=-1),
        _cell(23, "clear_reward", "Clear + Reward", reward=REWARD_CARD_PASS),
        _cell(24, "add_status", "Pose State", slot="pose", duration_type="until_finish"),
        _cell(26, "penalty_review", "Review Task"),
        _cell(27, "reward", "Pass Card", reward=REWARD_CARD_PASS),
        _cell(29, "extend_status", "Extend State"),
        _cell(30, "penalty_choice", "Penalty Choice"),
        _cell(31, "move", "Move Back", steps=-2),
        _cell(33, "penalty_review", "Review Task"),
        _cell(34, "block", "Prop Pause", slot="prop", actions=1),
        _cell(35, "clear_status", "Clear State"),
    ]
    finish = _cell(board_size, "finish", "Finish")
    return [item for item in events if item["position"] < board_size] + [finish]


def _default_state(seed: str | None = None, board_size: int = DEFAULT_BOARD_SIZE) -> dict[str, Any]:
    seed_value = seed or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    now = utc_now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "game_id": GAME_ID,
        "seed": str(seed_value),
        "random_counter": 0,
        "board_size": int(board_size),
        "created_at": now,
        "updated_at": now,
        "turn_index": 0,
        "positions": {"player": 0, "ai": 0},
        "turn_actor": "player",
        "statuses": {"player": [], "ai": []},
        "hands": {"player": {REWARD_CARD_PASS: 0}, "ai": {REWARD_CARD_PASS: 0}},
        "pending_event": None,
        "theme_profile": None,
        "game_over": False,
        "winner": "",
        "result": "",
        "event_log": [],
    }


def _normalise_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("schema_version", SCHEMA_VERSION)
    state.setdefault("game_id", GAME_ID)
    state.setdefault("seed", "default")
    state.setdefault("random_counter", 0)
    state.setdefault("board_size", DEFAULT_BOARD_SIZE)
    state.setdefault("created_at", utc_now_iso())
    state.setdefault("updated_at", utc_now_iso())
    state.setdefault("turn_index", 0)
    state.setdefault("positions", {})
    state.setdefault("statuses", {})
    state.setdefault("hands", {})
    for actor in ACTORS:
        state["positions"].setdefault(actor, 0)
        state["statuses"].setdefault(actor, [])
        state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
        state["hands"][actor].setdefault(REWARD_CARD_PASS, 0)
    state.setdefault("turn_actor", "player")
    state.setdefault("pending_event", None)
    state.setdefault("theme_profile", None)
    state.setdefault("game_over", False)
    state.setdefault("winner", "")
    state.setdefault("result", "")
    state.setdefault("event_log", [])
    return state


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return _default_state()
    return _normalise_state(json.loads(raw))


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


@contextmanager
def _locked_state(path: Path):
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_key = str(path)
    with _PROCESS_LOCKS_GUARD:
        process_lock = _PROCESS_LOCKS.setdefault(lock_key, threading.Lock())
    with process_lock:
        lock_file = path.with_suffix(path.suffix + ".lock")
        with lock_file.open("a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                state = _load_state(path)
                yield state
                _save_state(path, state)
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


class SeseBoardGame:
    def __init__(self, save_path: str | os.PathLike[str] | None = None, labels: dict[str, str] | None = None):
        self.save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH
        self.labels = labels or DEFAULT_LABELS

    def run_command(self, command: str | None = None) -> dict[str, Any]:
        command_text = (command or "status").strip() or "status"
        with _locked_state(self.save_path) as state:
            return _run_on_state(state, command_text, self.labels)

    def cmd(self, command: str | None = None) -> str:
        return self.run_command(command).get("text", "")


def run_command(command: str | None = None, save_path: str | os.PathLike[str] | None = None, labels: dict[str, str] | None = None) -> dict[str, Any]:
    return SeseBoardGame(save_path=save_path, labels=labels).run_command(command)


def cmd(command: str | None = None, save_path: str | os.PathLike[str] | None = None, labels: dict[str, str] | None = None) -> str:
    return run_command(command, save_path=save_path, labels=labels).get("text", "")


def _run_on_state(state: dict[str, Any], command: str, labels: dict[str, str]) -> dict[str, Any]:
    state = _normalise_state(state)
    verb, args = _parse_command(command)
    if verb in {"open", "status", "state", "help"}:
        return _payload(state, verb, _status_text(state, labels), labels)
    if verb in {"new_game", "new", "reset", "restart"}:
        seed, board_size = _parse_new_game_args(args)
        state.clear()
        state.update(_default_state(seed=seed, board_size=board_size))
        return _payload(state, verb, _status_text(state, labels, intro="New game started."), labels)
    if verb in {"end_game", "end", "stop"}:
        state["game_over"] = True
        state["result"] = "Game ended manually."
        return _payload(state, verb, _status_text(state, labels, intro="Game ended."), labels)
    if state.get("game_over"):
        return _payload(state, verb, _status_text(state, labels, intro="The game is already over. Use new_game to restart."), labels, ok=False)
    if verb == "roll":
        dice = _parse_roll(args)
        return _roll(state, dice, labels)
    if verb == "submit":
        return _submit(state, args, labels)
    if verb == "approve":
        return _approve(state, labels)
    if verb == "reject":
        return _reject(state, args, labels)
    if verb == "choose":
        return _choose(state, args, labels)
    if verb == "pass":
        return _pass_pending(state, labels)
    return _payload(state, verb, _status_text(state, labels, intro=f"Unknown command. {COMMAND_HINT}"), labels, ok=False)


def _parse_command(command: str) -> tuple[str, str]:
    stripped = command.strip()
    if not stripped:
        return "status", ""
    parts = stripped.split(maxsplit=1)
    return parts[0].lower(), parts[1].strip() if len(parts) > 1 else ""


def _parse_new_game_args(args: str) -> tuple[str | None, int]:
    seed = None
    board_size = DEFAULT_BOARD_SIZE
    if args:
        try:
            tokens = shlex.split(args)
        except ValueError:
            tokens = args.split()
        for token in tokens:
            if token.startswith("seed="):
                seed = token.split("=", 1)[1] or None
            elif token.startswith("size="):
                board_size = max(8, min(72, int(token.split("=", 1)[1] or DEFAULT_BOARD_SIZE)))
    return seed, board_size


def _parse_roll(args: str) -> int | None:
    if not args:
        return None
    match = re.search(r"\d+", args)
    if not match:
        return None
    value = int(match.group(0))
    if 1 <= value <= 6:
        return value
    return None


def _rng_int(state: dict[str, Any], low: int, high: int) -> int:
    import random

    counter = int(state.get("random_counter") or 0)
    state["random_counter"] = counter + 1
    rng = random.Random(f"{state.get('seed')}:{counter}")
    return rng.randint(low, high)


def _rng_pick(state: dict[str, Any], items: Iterable[Any]) -> Any:
    items_list = list(items)
    if not items_list:
        raise ValueError("empty random choice")
    return items_list[_rng_int(state, 0, len(items_list) - 1)]


def _roll(state: dict[str, Any], dice: int | None, labels: dict[str, str]) -> dict[str, Any]:
    if state.get("pending_event"):
        return _payload(state, "roll", _status_text(state, labels, intro="Resolve the pending event before rolling."), labels, ok=False)

    actor = state["turn_actor"]
    blocked = _consume_blocked_action(state, actor)
    if blocked:
        text = _compact_text(
            [
                f"{_actor_label(actor, labels)} cannot move this action because of {blocked.get('value') or blocked.get('label')}.",
                f"Remaining blocked actions: {blocked.get('remaining_actions', 0)}.",
                _advance_turn(state, actor),
            ]
        )
        _log(state, actor, text)
        return _payload(state, "roll", _status_text(state, labels, intro=text), labels)

    dice_value = dice or _rng_int(state, 1, 6)
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    old_pos = int(state["positions"].get(actor) or 0)
    new_pos = min(board_size, old_pos + dice_value)
    state["positions"][actor] = new_pos
    state["turn_index"] = int(state.get("turn_index") or 0) + 1

    lines = [f"{_actor_label(actor, labels)} rolled {dice_value}, moving from {old_pos} to {new_pos}."]
    event_lines = _apply_cell_event(state, actor, new_pos, labels)
    lines.extend(event_lines)

    if new_pos >= board_size:
        state["game_over"] = True
        state["winner"] = actor
        state["result"] = f"{_actor_label(actor, labels)} reached the finish and wins."
        lines.append(state["result"])
    elif not state.get("pending_event"):
        lines.append(_advance_turn(state, actor))

    text = _compact_text(lines)
    _log(state, actor, text)
    return _payload(state, "roll", _status_text(state, labels, intro=text), labels)


def _consume_blocked_action(state: dict[str, Any], actor: str) -> dict[str, Any] | None:
    statuses = state["statuses"].get(actor, [])
    for item in list(statuses):
        if item.get("blocks_action") and int(item.get("remaining_actions") or 0) > 0:
            item["remaining_actions"] = max(0, int(item.get("remaining_actions") or 0) - 1)
            consumed = deepcopy(item)
            if int(item.get("remaining_actions") or 0) <= 0:
                statuses.remove(item)
            return consumed
    return None


def _advance_turn(state: dict[str, Any], actor: str) -> str:
    next_actor = _other(actor)
    state["turn_actor"] = next_actor
    return f"Next action: {_actor_label(next_actor)}."


def _apply_cell_event(state: dict[str, Any], actor: str, position: int, labels: dict[str, str]) -> list[str]:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    event = _event_at(state, position)
    if not event or event["kind"] in {"start", "finish"}:
        return []

    kind = event["kind"]
    lines = [f"Cell {position}: {event['name']}."]
    if kind == "theme":
        lines.append(_set_theme(state))
    elif kind == "reward":
        lines.append(_give_reward(state, actor, event.get("reward", REWARD_CARD_PASS), labels))
    elif kind == "move_reward":
        lines.append(_give_reward(state, actor, event.get("reward", REWARD_CARD_PASS), labels))
        lines.append(_move_without_event(state, actor, int(event.get("steps") or 0), labels))
    elif kind == "clear_reward":
        lines.append(_clear_status(state, actor, labels))
        lines.append(_give_reward(state, actor, event.get("reward", REWARD_CARD_PASS), labels))
    elif kind == "add_status":
        lines.append(_add_status(state, actor, str(event.get("slot") or "prop"), str(event.get("duration_type") or "until_clear"), labels))
    elif kind == "block":
        lines.append(_add_block(state, actor, str(event.get("slot") or "prop"), int(event.get("actions") or 1), labels))
    elif kind == "move":
        lines.append(_move_without_event(state, actor, int(event.get("steps") or 0), labels))
    elif kind == "swap_positions":
        state["positions"]["player"], state["positions"]["ai"] = state["positions"]["ai"], state["positions"]["player"]
        lines.append("Both players swapped positions.")
    elif kind == "clear_status":
        lines.append(_clear_status(state, actor, labels))
    elif kind == "extend_status":
        lines.append(_extend_status(state, actor, labels))
    elif kind == "replace_status":
        slot = str(event.get("slot") or "place")
        before = len(state["statuses"].get(actor, []))
        state["statuses"][actor] = [item for item in state["statuses"].get(actor, []) if item.get("slot") != slot]
        removed = before - len(state["statuses"].get(actor, []))
        lines.append(f"Removed {removed} {slot} state." if removed else f"No {slot} state to replace.")
        lines.append(_add_status(state, actor, slot, str(event.get("duration_type") or "until_clear"), labels))
    elif kind == "penalty_review":
        lines.append(_assign_review_penalty(state, actor, position, labels))
    elif kind == "penalty_choice":
        lines.append(_assign_choice_penalty(state, actor, position, labels))
    state["positions"][actor] = min(board_size, max(0, int(state["positions"].get(actor) or 0)))
    return lines


def _event_at(state: dict[str, Any], position: int) -> dict[str, Any] | None:
    for item in build_cell_events(int(state.get("board_size") or DEFAULT_BOARD_SIZE)):
        if item["position"] == position:
            return item
    return None


def _set_theme(state: dict[str, Any]) -> str:
    theme = _rng_pick(state, THEMES)
    lead = str(theme.get("lead") or "ai")
    state["theme_profile"] = {
        "id": theme.get("id"),
        "theme": theme.get("name"),
        "lead": lead,
        "direction": lead,
        "direction_label": f"{_actor_label(lead)} leads",
    }
    return f"Theme set to {theme.get('name')}; {_actor_label(lead)} leads."


def _give_reward(state: dict[str, Any], actor: str, reward_id: str, labels: dict[str, str]) -> str:
    reward_id = reward_id or REWARD_CARD_PASS
    hand = state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
    hand[reward_id] = int(hand.get(reward_id) or 0) + 1
    return f"{_actor_label(actor, labels)} gained {REWARD_CARD_LABELS.get(reward_id, reward_id)}."


def _add_status(state: dict[str, Any], actor: str, slot: str, duration_type: str, labels: dict[str, str], *, value: str | None = None, level: int = 1) -> str:
    value = value or _status_value(state, slot)
    item = {
        "id": f"{slot}-{len(state['statuses'].get(actor, [])) + 1}-{state.get('turn_index', 0)}",
        "slot": slot,
        "label": _status_label(slot),
        "value": value,
        "duration_type": duration_type,
        "level": level,
        "blocks_action": False,
    }
    state["statuses"].setdefault(actor, []).append(item)
    return f"{_actor_label(actor, labels)} is now under {_status_label(slot)}: {value}."


def _add_block(state: dict[str, Any], actor: str, slot: str, actions: int, labels: dict[str, str]) -> str:
    value = _status_value(state, slot)
    item = {
        "id": f"block-{slot}-{len(state['statuses'].get(actor, [])) + 1}-{state.get('turn_index', 0)}",
        "slot": slot,
        "label": _status_label(slot),
        "value": value,
        "duration_type": "actions",
        "remaining_actions": max(1, int(actions)),
        "level": 1,
        "blocks_action": True,
    }
    state["statuses"].setdefault(actor, []).append(item)
    return f"{_actor_label(actor, labels)} loses {item['remaining_actions']} action(s) under {value}."


def _status_value(state: dict[str, Any], slot: str) -> str:
    options = SLOTS.get(slot, {}).get("options") or (slot,)
    return str(_rng_pick(state, options))


def _move_without_event(state: dict[str, Any], actor: str, steps: int, labels: dict[str, str]) -> str:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    old = int(state["positions"].get(actor) or 0)
    new = max(0, min(board_size, old + int(steps)))
    state["positions"][actor] = new
    direction = "forward" if steps >= 0 else "back"
    return f"{_actor_label(actor, labels)} moved {direction} {abs(int(steps))} cell(s), from {old} to {new}."


def _clear_status(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state["statuses"].get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)} has no state to clear."
    index = _rng_int(state, 0, len(statuses) - 1)
    removed = statuses.pop(index)
    return f"Cleared {_actor_label(actor, labels)}'s {removed.get('label')}: {removed.get('value')}."


def _extend_status(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state["statuses"].get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)} has no state to extend."
    item = statuses[_rng_int(state, 0, len(statuses) - 1)]
    if item.get("duration_type") == "actions":
        item["remaining_actions"] = int(item.get("remaining_actions") or 0) + 1
        return f"Extended {_actor_label(actor, labels)}'s {item.get('label')} by 1 blocked action."
    item["level"] = int(item.get("level") or 1) + 1
    return f"Raised {_actor_label(actor, labels)}'s {item.get('label')} level to {item['level']}."


def _assign_review_penalty(state: dict[str, Any], actor: str, position: int, labels: dict[str, str]) -> str:
    card = deepcopy(_rng_pick(state, REVIEW_PENALTY_CARDS))
    pending = {
        "id": f"review-{position}-{state.get('turn_index', 0)}",
        "type": "review",
        "card_id": card.get("id"),
        "name": card.get("name"),
        "actor": actor,
        "reviewer": _other(actor),
        "phase": "assigned",
        "task": card.get("task"),
        "submission": card.get("submission"),
        "pass_result": card.get("pass_result"),
        "reject_prompt": card.get("reject_prompt"),
        "pass_allowed": bool(card.get("pass_allowed")),
        "cell": position,
        "theme": (state.get("theme_profile") or {}).get("theme") or "No theme",
        "reject_count": 0,
        "next_actor_after_event": _other(actor),
    }
    state["pending_event"] = pending
    state["turn_actor"] = actor
    return f"Review task assigned to {_actor_label(actor, labels)}: {pending['task']}"


def _assign_choice_penalty(state: dict[str, Any], actor: str, position: int, labels: dict[str, str]) -> str:
    card = deepcopy(_rng_pick(state, CHOICE_PENALTY_CARDS))
    choices = _available_choices(state, actor, card.get("choices") or [])
    if not choices:
        return _add_status(state, actor, "prop", "until_clear", labels)
    pending = {
        "id": f"choice-{position}-{state.get('turn_index', 0)}",
        "type": "choice",
        "card_id": card.get("id"),
        "name": card.get("name"),
        "actor": actor,
        "phase": "assigned",
        "prompt": card.get("prompt") or "Choose one penalty.",
        "pass_allowed": bool(card.get("pass_allowed")),
        "cell": position,
        "choices": choices,
        "next_actor_after_event": _other(actor),
    }
    state["pending_event"] = pending
    state["turn_actor"] = actor
    return f"Choice penalty assigned to {_actor_label(actor, labels)}: {pending['prompt']}"


def _available_choices(state: dict[str, Any], actor: str, choices: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for choice in choices:
        requires = choice.get("requires") or {}
        required_slot = requires.get("status_slot")
        if required_slot and not any(item.get("slot") == required_slot for item in state["statuses"].get(actor, [])):
            continue
        result.append(choice)
    return result


def _submit(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "submit", _status_text(state, labels, intro="There is no review task to submit."), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "submit", _status_text(state, labels, intro=f"It is not {_actor_label(actor, labels)}'s submission turn."), labels, ok=False)
    text = args.strip()
    if not text:
        return _payload(state, "submit", _status_text(state, labels, intro="Submit text cannot be empty."), labels, ok=False)
    pending["phase"] = "submitted"
    pending["submission_text"] = text
    state["turn_actor"] = pending.get("reviewer") or _other(actor)
    intro = f"{_actor_label(actor, labels)} submitted the task. Waiting for {_actor_label(state['turn_actor'], labels)} to approve or reject."
    _log(state, actor, intro)
    return _payload(state, "submit", _status_text(state, labels, intro=intro), labels)


def _approve(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "approve", _status_text(state, labels, intro="There is no review task to approve."), labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "approve", _status_text(state, labels, intro=f"Waiting for {_actor_label(pending.get('actor'), labels)} to submit first."), labels, ok=False)
    actor = pending.get("actor")
    intro = f"{_actor_label(reviewer, labels)} approved {_actor_label(actor, labels)}'s task. The event is complete."
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    _log(state, reviewer, intro)
    return _payload(state, "approve", _status_text(state, labels, intro=_compact_text([intro, f"Next action: {_actor_label(state['turn_actor'], labels)}."])), labels)


def _reject(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "reject", _status_text(state, labels, intro="There is no review task to reject."), labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "reject", _status_text(state, labels, intro=f"Waiting for {_actor_label(pending.get('actor'), labels)} to submit first."), labels, ok=False)
    pending["phase"] = "assigned"
    pending["reject_count"] = int(pending.get("reject_count") or 0) + 1
    reason = args.strip()
    if reason:
        pending["last_reject_reason"] = reason
    actor = pending.get("actor")
    state["turn_actor"] = actor
    intro = pending.get("reject_prompt") or f"{_actor_label(reviewer, labels)} rejected the submission. Submit again."
    _log(state, reviewer, intro)
    return _payload(state, "reject", _status_text(state, labels, intro=intro), labels)


def _choose(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "choice":
        return _payload(state, "choose", _status_text(state, labels, intro="There is no choice penalty to resolve."), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "choose", _status_text(state, labels, intro=f"It is not {_actor_label(actor, labels)}'s choice turn."), labels, ok=False)
    selected = _find_choice(pending.get("choices") or [], args)
    if not selected:
        return _payload(state, "choose", _status_text(state, labels, intro="Choice not found. Use choose <choice id>."), labels, ok=False)
    result = _apply_choice_effect(state, actor, selected, labels)
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = _compact_text([f"{_actor_label(actor, labels)} chose: {selected.get('label')}.", result, f"Next action: {_actor_label(state['turn_actor'], labels)}."])
    _log(state, actor, intro)
    return _payload(state, "choose", _status_text(state, labels, intro=intro), labels)


def _find_choice(choices: Iterable[dict[str, Any]], arg: str) -> dict[str, Any] | None:
    needle = arg.strip().lower()
    if not needle:
        return None
    for index, choice in enumerate(choices, start=1):
        values = {str(index), str(choice.get("id") or "").lower(), str(choice.get("label") or "").lower()}
        if needle in values:
            return choice
    for choice in choices:
        if needle in str(choice.get("label") or "").lower():
            return choice
    return None


def _apply_choice_effect(state: dict[str, Any], actor: str, choice: dict[str, Any], labels: dict[str, str]) -> str:
    effect = choice.get("effect") or {}
    kind = effect.get("kind")
    if kind == "add_status":
        return _add_status(state, actor, str(effect.get("slot") or "prop"), str(effect.get("duration_type") or "until_clear"), labels)
    if kind == "upgrade_status_level":
        return _upgrade_status_level(state, actor, str(effect.get("slot") or "prop"), int(effect.get("delta") or 1), labels)
    if kind == "move":
        return _move_without_event(state, actor, int(effect.get("steps") or 0), labels)
    if kind == "add_block":
        return _add_block(state, actor, str(effect.get("slot") or "prop"), int(effect.get("actions") or 1), labels)
    if kind == "add_status_and_block":
        return _compact_text(
            [
                _add_status(state, actor, str(effect.get("slot") or "prop"), "until_clear", labels),
                _add_block(state, actor, str(effect.get("slot") or "prop"), int(effect.get("actions") or 1), labels),
            ]
        )
    return "No effect was applied."


def _upgrade_status_level(state: dict[str, Any], actor: str, slot: str, delta: int, labels: dict[str, str]) -> str:
    for item in reversed(state["statuses"].get(actor, [])):
        if item.get("slot") == slot:
            item["level"] = int(item.get("level") or 1) + int(delta)
            return f"Raised {_actor_label(actor, labels)}'s {item.get('label')} level to {item['level']}."
    return _add_status(state, actor, slot, "until_clear", labels)


def _pass_pending(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending:
        return _payload(state, "pass", _status_text(state, labels, intro="There is no pending penalty to pass."), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "pass", _status_text(state, labels, intro=f"Only {_actor_label(actor, labels)} can pass this penalty."), labels, ok=False)
    if not pending.get("pass_allowed"):
        return _payload(state, "pass", _status_text(state, labels, intro="This penalty cannot be passed."), labels, ok=False)
    hand = state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
    if int(hand.get(REWARD_CARD_PASS) or 0) <= 0:
        return _payload(state, "pass", _status_text(state, labels, intro=f"{_actor_label(actor, labels)} has no Pass Card."), labels, ok=False)
    hand[REWARD_CARD_PASS] = int(hand.get(REWARD_CARD_PASS) or 0) - 1
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = f"{_actor_label(actor, labels)} used a Pass Card. Pending penalty skipped."
    _log(state, actor, intro)
    return _payload(state, "pass", _status_text(state, labels, intro=_compact_text([intro, f"Next action: {_actor_label(state['turn_actor'], labels)}."])), labels)


def _board_payload(state: dict[str, Any]) -> dict[str, Any]:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    events = {item["position"]: item for item in build_cell_events(board_size)}
    cells = []
    for position in range(1, board_size + 1):
        event = deepcopy(events.get(position) or {"position": position, "kind": "empty", "name": "Empty"})
        cells.append(event)
    return {"size": board_size, "cells": cells}


def _state_public(state: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(state)
    public["cell_events"] = _board_payload(state)["cells"]
    return public


def _payload(state: dict[str, Any], command: str, text: str, labels: dict[str, str], ok: bool = True) -> dict[str, Any]:
    board = _board_payload(state)
    public_state = _state_public(state)
    return {
        "ok": ok,
        "game_id": GAME_ID,
        "command": command,
        "text": text,
        "player_text": _status_text(state, {"player": "You", "ai": labels.get("ai", "AI")}),
        "ai_text": _status_text(state, {"player": labels.get("player", "Player"), "ai": "You"}),
        "board": board,
        "state": public_state,
        "game_over": bool(state.get("game_over")),
        "winner": state.get("winner") or "",
        "result": state.get("result") or "",
        "commands": COMMAND_HINT,
    }


def _status_text(state: dict[str, Any], labels: dict[str, str], intro: str = "") -> str:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    pos = state.get("positions") or {}
    turn_actor = state.get("turn_actor") or "player"
    lines = [
        intro,
        f"Progress: {_actor_label('player', labels)} {int(pos.get('player') or 0)}/{board_size} | {_actor_label('ai', labels)} {int(pos.get('ai') or 0)}/{board_size}",
        _theme_line(state, labels),
        f"Turn: {_actor_label(turn_actor, labels)}",
        _hand_line(state, labels),
        _statuses_line(state, "player", labels),
        _statuses_line(state, "ai", labels),
        _pending_line(state, labels),
    ]
    return _compact_text(lines)


def _theme_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    profile = state.get("theme_profile")
    if not profile:
        return "Theme: not triggered"
    lead = str(profile.get("lead") or profile.get("direction") or "")
    return f"Theme: {profile.get('theme')} | Lead: {_actor_label(lead, labels)}"


def _hand_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    hands = state.get("hands") or {}
    return "Hands: " + " | ".join(
        f"{_actor_label(actor, labels)} Pass Card x{int((hands.get(actor) or {}).get(REWARD_CARD_PASS) or 0)}"
        for actor in ACTORS
    )


def _statuses_line(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state.get("statuses", {}).get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)} states: none"
    parts = []
    for item in statuses:
        duration = item.get("duration_type")
        tail = ""
        if duration == "actions":
            tail = f", {int(item.get('remaining_actions') or 0)} action(s) left"
        elif duration:
            tail = f", {duration}"
        level = int(item.get("level") or 1)
        level_text = f" Lv.{level}" if level > 1 else ""
        parts.append(f"{item.get('label')}: {item.get('value')}{level_text}{tail}")
    return f"{_actor_label(actor, labels)} states: " + "; ".join(parts)


def _pending_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    pending = state.get("pending_event")
    if not pending:
        return "Pending: none"
    actor = _actor_label(str(pending.get("actor") or ""), labels)
    if pending.get("type") == "review":
        reviewer = _actor_label(str(pending.get("reviewer") or ""), labels)
        return f"Pending review: {pending.get('name')} for {actor}. Phase: {pending.get('phase')}. Reviewer: {reviewer}. Task: {pending.get('task')}"
    if pending.get("type") == "choice":
        choices = ", ".join(f"{idx}. {item.get('label')} [{item.get('id')}]" for idx, item in enumerate(pending.get("choices") or [], start=1))
        return f"Pending choice: {pending.get('name')} for {actor}. {pending.get('prompt')} Choices: {choices}"
    return f"Pending: {pending.get('name') or pending.get('type')}"


def _log(state: dict[str, Any], actor: str, text: str) -> None:
    event_log = state.setdefault("event_log", [])
    event_log.append({"at": utc_now_iso(), "actor": actor, "text": text})
    del event_log[:-50]

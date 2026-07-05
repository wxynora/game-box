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
DEFAULT_LABELS = {"player": "你", "ai": "对方"}
COMMAND_HINT = "可用命令：status / new_game / roll / roll 3 / submit <内容> / approve / reject [理由] / choose <选项> / pass / end_game"

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


def _status_title(item: dict[str, Any]) -> str:
    slot = str(item.get("slot") or "")
    if slot == "prop":
        return "道具惩罚"
    if slot == "limit":
        return "限制"
    if slot == "task":
        return "任务状态"
    if slot == "pose":
        return "姿势锁定"
    if slot == "place":
        return "地点状态"
    return str(item.get("label") or _status_label(slot) or "状态")


def _format_status_item(item: dict[str, Any], *, include_duration: bool = True) -> str:
    title = _status_title(item)
    return f"{title}：{_format_status_body(item, include_duration=include_duration)}"


def _format_status_body(item: dict[str, Any], *, include_duration: bool = True) -> str:
    value = str(item.get("value") or "未指定")
    level = int(item.get("level") or 1)
    details: list[str] = []
    if str(item.get("slot") or "") == "prop" and level > 1:
        details.append(f"{level}档")
    if include_duration:
        duration = str(item.get("duration_type") or "")
        if duration == "actions":
            details.append(f"停步剩余 {int(item.get('remaining_actions') or 0)} 次")
        elif duration:
            details.append(_duration_label(duration))
    suffix = f"（{'，'.join(details)}）" if details else ""
    return f"{value}{suffix}"


def _group_status_items(items: Iterable[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for item in items:
        title = _status_title(item)
        if title not in grouped:
            grouped[title] = []
            order.append(title)
        grouped[title].append(_format_status_body(item))
    return [f"{title}：" + "、".join(grouped[title]) for title in order]


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
        _cell(1, "start", "起点"),
        _cell(3, "reward", "奖励抽卡", reward=REWARD_CARD_PASS),
        _cell(4, "add_status", "地点追加", slot="place", duration_type="until_clear"),
        _cell(6, "move", "限制拖回", steps=-2),
        _cell(8, "clear_status", "解除状态"),
        _cell(9, "penalty_choice", "选择惩罚"),
        _cell(11, "penalty_review", "验收任务"),
        _cell(12, "move_reward", "奖励前进", steps=2, reward=REWARD_CARD_PASS),
        _cell(14, "extend_status", "状态延长"),
        _cell(15, "swap_positions", "位置交换"),
        _cell(17, "block", "道具停步", slot="prop", actions=2),
        _cell(18, "replace_status", "替换地点", slot="place", duration_type="until_clear"),
        _cell(20, "penalty_choice", "选择惩罚"),
        _cell(21, "move", "限制拖回", steps=-1),
        _cell(23, "clear_reward", "解除状态+奖励", reward=REWARD_CARD_PASS),
        _cell(24, "add_status", "姿势锁定", slot="pose", duration_type="until_finish"),
        _cell(26, "penalty_review", "验收任务"),
        _cell(27, "reward", "奖励抽卡", reward=REWARD_CARD_PASS),
        _cell(29, "extend_status", "状态延长"),
        _cell(30, "penalty_choice", "选择惩罚"),
        _cell(31, "move", "限制拖回", steps=-2),
        _cell(33, "penalty_review", "验收任务"),
        _cell(34, "block", "道具停步", slot="prop", actions=1),
        _cell(35, "clear_status", "解除状态"),
    ]
    finish = _cell(board_size, "finish", "终点")
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
        return _payload(state, verb, _status_text(state, labels, intro="新局已开始。"), labels)
    if verb in {"end_game", "end", "stop"}:
        state["game_over"] = True
        state["result"] = "游戏已手动结束。"
        return _payload(state, verb, _status_text(state, labels, intro="游戏已结束。"), labels)
    if state.get("game_over"):
        return _payload(state, verb, _status_text(state, labels, intro="本局已经结束。使用 new_game 重新开始。"), labels, ok=False)
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
    return _payload(state, verb, _status_text(state, labels, intro=f"未知命令。{COMMAND_HINT}"), labels, ok=False)


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
        return _payload(state, "roll", _status_text(state, labels, intro="当前还有待处理事件，先处理完再掷骰。"), labels, ok=False)

    actor = state["turn_actor"]
    blocked = _consume_blocked_action(state, actor)
    if blocked:
        text = _compact_text(
            [
                f"{_actor_label(actor, labels)}因为「{blocked.get('value') or blocked.get('label')}」本次无法行动。",
                f"剩余停步次数：{blocked.get('remaining_actions', 0)}。",
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

    lines = [f"{_actor_label(actor, labels)}掷出 {dice_value}，从 {old_pos} 走到 {new_pos}。"]
    event_lines = _apply_cell_event(state, actor, new_pos, labels)
    lines.extend(event_lines)

    if new_pos >= board_size:
        state["game_over"] = True
        state["winner"] = actor
        state["result"] = f"{_actor_label(actor, labels)}到达终点，获得胜利。"
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
    return f"下一次行动：{_actor_label(next_actor)}。"


def _apply_cell_event(state: dict[str, Any], actor: str, position: int, labels: dict[str, str]) -> list[str]:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    event = _event_at(state, position)
    if not event or event["kind"] in {"start", "finish"}:
        return []

    kind = event["kind"]
    lines = [f"第 {position} 格：{event['name']}。"]
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
        lines.append("双方交换位置。")
    elif kind == "clear_status":
        lines.append(_clear_status(state, actor, labels))
    elif kind == "extend_status":
        lines.append(_extend_status(state, actor, labels))
    elif kind == "replace_status":
        slot = str(event.get("slot") or "place")
        before = len(state["statuses"].get(actor, []))
        state["statuses"][actor] = [item for item in state["statuses"].get(actor, []) if item.get("slot") != slot]
        removed = before - len(state["statuses"].get(actor, []))
        slot_label = _status_label(slot)
        lines.append(f"已移除 {removed} 个{slot_label}状态。" if removed else f"当前没有可替换的{slot_label}状态。")
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
        "direction_label": f"{_actor_label(lead)}主导",
    }
    return f"本局主题设为「{theme.get('name')}」，主导方：{_actor_label(lead)}。"


def _give_reward(state: dict[str, Any], actor: str, reward_id: str, labels: dict[str, str]) -> str:
    reward_id = reward_id or REWARD_CARD_PASS
    hand = state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
    hand[reward_id] = int(hand.get(reward_id) or 0) + 1
    return f"{_actor_label(actor, labels)}获得 {REWARD_CARD_LABELS.get(reward_id, reward_id)}。"


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
    return f"{_actor_label(actor, labels)}新增状态：{_format_status_item(item)}。"


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
    return f"{_actor_label(actor, labels)}新增停步状态：{_format_status_item(item)}。"


def _status_value(state: dict[str, Any], slot: str) -> str:
    options = SLOTS.get(slot, {}).get("options") or (slot,)
    return str(_rng_pick(state, options))


def _move_without_event(state: dict[str, Any], actor: str, steps: int, labels: dict[str, str]) -> str:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    old = int(state["positions"].get(actor) or 0)
    new = max(0, min(board_size, old + int(steps)))
    state["positions"][actor] = new
    direction = "前进" if steps >= 0 else "后退"
    return f"{_actor_label(actor, labels)}{direction} {abs(int(steps))} 格，从 {old} 到 {new}。"


def _clear_status(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state["statuses"].get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)}当前没有可解除状态。"
    index = _rng_int(state, 0, len(statuses) - 1)
    removed = statuses.pop(index)
    return f"已解除{_actor_label(actor, labels)}的状态：{_format_status_item(removed, include_duration=False)}。"


def _extend_status(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state["statuses"].get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)}当前没有可延长状态。"
    item = statuses[_rng_int(state, 0, len(statuses) - 1)]
    if item.get("duration_type") == "actions":
        item["remaining_actions"] = int(item.get("remaining_actions") or 0) + 1
        return f"{_actor_label(actor, labels)}的状态已延长：{_format_status_item(item)}。"
    item["level"] = int(item.get("level") or 1) + 1
    return f"{_actor_label(actor, labels)}的状态已加码：{_format_status_item(item)}。"


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
        "theme": (state.get("theme_profile") or {}).get("theme") or "未触发主题",
        "reject_count": 0,
        "next_actor_after_event": _other(actor),
    }
    state["pending_event"] = pending
    state["turn_actor"] = actor
    return f"{_actor_label(actor, labels)}抽到验收任务：{pending['task']}"


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
        "prompt": card.get("prompt") or "选择一项惩罚。",
        "pass_allowed": bool(card.get("pass_allowed")),
        "cell": position,
        "choices": choices,
        "next_actor_after_event": _other(actor),
    }
    state["pending_event"] = pending
    state["turn_actor"] = actor
    return f"{_actor_label(actor, labels)}抽到选择惩罚：{pending['prompt']}"


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
        return _payload(state, "submit", _status_text(state, labels, intro="当前没有需要提交的验收任务。"), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "submit", _status_text(state, labels, intro=f"现在不是{_actor_label(actor, labels)}的提交回合。"), labels, ok=False)
    text = args.strip()
    if not text:
        return _payload(state, "submit", _status_text(state, labels, intro="提交内容不能为空。"), labels, ok=False)
    pending["phase"] = "submitted"
    pending["submission_text"] = text
    state["turn_actor"] = pending.get("reviewer") or _other(actor)
    intro = f"{_actor_label(actor, labels)}已提交任务，等待{_actor_label(state['turn_actor'], labels)}通过或驳回。"
    _log(state, actor, intro)
    return _payload(state, "submit", _status_text(state, labels, intro=intro), labels)


def _approve(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "approve", _status_text(state, labels, intro="当前没有待验收任务。"), labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "approve", _status_text(state, labels, intro=f"正在等待{_actor_label(pending.get('actor'), labels)}先提交任务。"), labels, ok=False)
    actor = pending.get("actor")
    intro = f"{_actor_label(reviewer, labels)}通过了{_actor_label(actor, labels)}的任务，本次事件完成。"
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    _log(state, reviewer, intro)
    return _payload(state, "approve", _status_text(state, labels, intro=_compact_text([intro, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"])), labels)


def _reject(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "reject", _status_text(state, labels, intro="当前没有可驳回的验收任务。"), labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "reject", _status_text(state, labels, intro=f"正在等待{_actor_label(pending.get('actor'), labels)}先提交任务。"), labels, ok=False)
    pending["phase"] = "assigned"
    pending["reject_count"] = int(pending.get("reject_count") or 0) + 1
    reason = args.strip()
    if reason:
        pending["last_reject_reason"] = reason
    actor = pending.get("actor")
    state["turn_actor"] = actor
    intro = pending.get("reject_prompt") or f"{_actor_label(reviewer, labels)}驳回了提交，请重新提交。"
    _log(state, reviewer, intro)
    return _payload(state, "reject", _status_text(state, labels, intro=intro), labels)


def _choose(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "choice":
        return _payload(state, "choose", _status_text(state, labels, intro="当前没有需要处理的选择惩罚。"), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "choose", _status_text(state, labels, intro=f"现在不是{_actor_label(actor, labels)}的选择回合。"), labels, ok=False)
    selected = _find_choice(pending.get("choices") or [], args)
    if not selected:
        return _payload(state, "choose", _status_text(state, labels, intro="没有找到这个选项。请使用 choose <选项id>。"), labels, ok=False)
    result = _apply_choice_effect(state, actor, selected, labels)
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = _compact_text([f"{_actor_label(actor, labels)}选择了：{selected.get('label')}。", result, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"])
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
    return "没有结算任何效果。"


def _upgrade_status_level(state: dict[str, Any], actor: str, slot: str, delta: int, labels: dict[str, str]) -> str:
    for item in reversed(state["statuses"].get(actor, [])):
        if item.get("slot") == slot:
            item["level"] = int(item.get("level") or 1) + int(delta)
            return f"{_actor_label(actor, labels)}的状态已加码：{_format_status_item(item)}。"
    return _add_status(state, actor, slot, "until_clear", labels)


def _pass_pending(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending:
        return _payload(state, "pass", _status_text(state, labels, intro="当前没有可跳过的待处理惩罚。"), labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "pass", _status_text(state, labels, intro=f"只有{_actor_label(actor, labels)}可以跳过这个惩罚。"), labels, ok=False)
    if not pending.get("pass_allowed"):
        return _payload(state, "pass", _status_text(state, labels, intro="这个惩罚不能使用 Pass 卡跳过。"), labels, ok=False)
    hand = state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
    if int(hand.get(REWARD_CARD_PASS) or 0) <= 0:
        return _payload(state, "pass", _status_text(state, labels, intro=f"{_actor_label(actor, labels)}没有 Pass 卡。"), labels, ok=False)
    hand[REWARD_CARD_PASS] = int(hand.get(REWARD_CARD_PASS) or 0) - 1
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = f"{_actor_label(actor, labels)}使用 Pass 卡，跳过当前惩罚。"
    _log(state, actor, intro)
    return _payload(state, "pass", _status_text(state, labels, intro=_compact_text([intro, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"])), labels)


def _board_payload(state: dict[str, Any]) -> dict[str, Any]:
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    events = {item["position"]: item for item in build_cell_events(board_size)}
    cells = []
    for position in range(1, board_size + 1):
        event = deepcopy(events.get(position) or {"position": position, "kind": "empty", "name": "空"})
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
        "player_text": _status_text(state, {"player": "你", "ai": labels.get("ai", "对方")}),
        "ai_text": _status_text(state, {"player": labels.get("player", "对方"), "ai": "你"}),
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
        f"进度：{_actor_label('player', labels)} {int(pos.get('player') or 0)}/{board_size} | {_actor_label('ai', labels)} {int(pos.get('ai') or 0)}/{board_size}",
        _theme_line(state, labels),
        f"轮到：{_actor_label(turn_actor, labels)}",
        _hand_line(state, labels),
        _statuses_line(state, "player", labels),
        _statuses_line(state, "ai", labels),
        _pending_line(state, labels),
    ]
    return _compact_text(lines)


def _theme_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    profile = state.get("theme_profile")
    if not profile:
        return "主题：未触发"
    lead = str(profile.get("lead") or profile.get("direction") or "")
    return f"主题：{profile.get('theme')} | 主导方：{_actor_label(lead, labels)}"


def _hand_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    hands = state.get("hands") or {}
    return "手牌：" + " | ".join(
        f"{_actor_label(actor, labels)} Pass 卡 x{int((hands.get(actor) or {}).get(REWARD_CARD_PASS) or 0)}"
        for actor in ACTORS
    )


def _statuses_line(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    statuses = state.get("statuses", {}).get(actor, [])
    if not statuses:
        return f"{_actor_label(actor, labels)}状态：无"
    parts = _group_status_items(statuses)
    return f"{_actor_label(actor, labels)}状态：" + "；".join(parts)


def _duration_label(duration: str) -> str:
    if duration == "until_clear":
        return "待解除"
    if duration == "until_finish":
        return "到终点前有效"
    if duration == "actions":
        return "按行动次数"
    return duration


def _pending_line(state: dict[str, Any], labels: dict[str, str]) -> str:
    pending = state.get("pending_event")
    if not pending:
        return "待处理：无"
    actor = _actor_label(str(pending.get("actor") or ""), labels)
    if pending.get("type") == "review":
        reviewer = _actor_label(str(pending.get("reviewer") or ""), labels)
        phase = "已提交，待验收" if pending.get("phase") == "submitted" else "待提交"
        return f"待处理验收任务：{pending.get('name')}；执行方：{actor}；状态：{phase}；验收方：{reviewer}；任务：{pending.get('task')}"
    if pending.get("type") == "choice":
        choices = ", ".join(f"{idx}. {item.get('label')} [{item.get('id')}]" for idx, item in enumerate(pending.get("choices") or [], start=1))
        return f"待处理选择惩罚：{pending.get('name')}；执行方：{actor}；{pending.get('prompt')} 选项：{choices}"
    return f"待处理：{pending.get('name') or pending.get('type')}"


def _log(state: dict[str, Any], actor: str, text: str) -> None:
    event_log = state.setdefault("event_log", [])
    event_log.append({"at": utc_now_iso(), "actor": actor, "text": text})
    del event_log[:-50]

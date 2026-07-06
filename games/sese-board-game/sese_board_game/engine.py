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
    DEFAULT_LIMIT_OPTIONS,
    REVIEW_PENALTY_CARDS,
    REWARD_CARD_LABELS,
    REWARD_CARD_PASS,
    SLOTS,
    THEME_LIMIT_OPTIONS,
    THEME_OPTION_PREFERENCES,
    THEMES,
)

try:
    import fcntl
except Exception:  # pragma: no cover - fcntl is not available on every platform.
    fcntl = None


GAME_ID = "sese_board_game"
SCHEMA_VERSION = 1
DEFAULT_BOARD_SIZE = 36
PASS_SKIP_LIMIT = 1
INVALID_PROP_VALUES = {"避孕套"}
HUMAN_ACTOR_FORBIDDEN_PROP_PATTERNS = ("锁精环",)
AI_ACTOR_FORBIDDEN_PROP_PATTERNS = ("阴蒂", "吸乳器")
LEVELABLE_PROP_PATTERNS = ("跳蛋", "震动", "按摩棒", "飞机杯", "吸乳器", "吸吮器")
POSE_LOCATION_PATTERNS = (
    "浴缸",
    "浴室",
    "淋浴",
    "停车场",
    "车",
    "床",
    "沙发",
    "椅",
    "桌",
    "墙",
    "壁",
    "镜",
    "门",
    "窗",
    "地",
    "楼梯",
    "厨房",
    "玄关",
    "洗手台",
    "会议",
    "办公",
    "教室",
    "图书馆",
    "KTV",
    "电影院",
    "衣帽间",
    "按摩床",
    "酒店",
    "试衣间",
    "阳台",
    "露台",
    "仓库",
    "小木屋",
    "帐篷",
)
POSE_VALUE_REPLACEMENTS = {
    "浴缸骑乘": "骑乘位",
    "椅子位": "坐姿位",
    "壁尻": "站立后入",
}
FINAL_APPEND_SLOT_ALIASES = {
    "prop": "prop",
    "道具": "prop",
    "道具惩罚": "prop",
    "limit": "limit",
    "限制": "limit",
    "规矩": "limit",
}
DEFAULT_SAVE_PATH = Path(os.environ.get("SESE_BOARD_GAME_SAVE", ".sese_board_game.json"))
ACTORS = ("player", "ai")
DEFAULT_LABELS = {"player": "你", "ai": "对方"}
COMMAND_HINT = "可用命令：status / new_game / roll / roll 3 / submit <内容> / approve / reject [理由] / choose <选项> / 剪刀石头布: 石头 / pass / end_game"
RPS_CHOICES = (
    {"id": "rock", "label": "石头"},
    {"id": "scissors", "label": "剪刀"},
    {"id": "paper", "label": "布"},
)
RPS_ALIASES = {
    "rock": "rock",
    "石头": "rock",
    "scissors": "scissors",
    "scissor": "scissors",
    "剪刀": "scissors",
    "paper": "paper",
    "布": "paper",
}
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}

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
        return "最终姿势"
    if slot == "place":
        return "最终地点"
    return str(item.get("label") or _status_label(slot) or "状态")


def _format_status_item(item: dict[str, Any], *, include_duration: bool = True) -> str:
    title = _status_title(item)
    return f"{title}：{_format_status_body(item, include_duration=include_duration)}"


def _format_status_body(item: dict[str, Any], *, include_duration: bool = True) -> str:
    value = str(item.get("value") or "未指定")
    level = int(item.get("level") or 1)
    details: list[str] = []
    if _status_supports_level(item) and level > 1:
        details.append(f"{level}档")
    if include_duration:
        duration = str(item.get("duration_type") or "")
        if duration == "actions":
            details.append(f"停步剩余 {int(item.get('remaining_actions') or 0)} 次")
        elif duration:
            label = _duration_label(duration)
            if label:
                details.append(label)
    suffix = f"（{'，'.join(details)}）" if details else ""
    return f"{value}{suffix}"


def _group_status_items(items: Iterable[dict[str, Any]], *, include_duration: bool = True) -> list[str]:
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for item in items:
        title = _status_title(item)
        if title not in grouped:
            grouped[title] = []
            order.append(title)
        grouped[title].append(_format_status_body(item, include_duration=include_duration))
    return [f"{title}：" + "、".join(grouped[title]) for title in order]


def _compact_text(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line).strip()


def _translate_actor_labels(text: str, source: dict[str, str], target: dict[str, str]) -> str:
    if not text or source == target:
        return text
    translated = str(text)
    markers = {actor: f"\u0000{actor}\u0000" for actor in ACTORS}
    for actor in sorted(ACTORS, key=lambda item: len(str(source.get(item) or DEFAULT_LABELS.get(item) or item)), reverse=True):
        label = str(source.get(actor) or DEFAULT_LABELS.get(actor) or actor)
        if label:
            translated = translated.replace(label, markers[actor])
    for actor in ACTORS:
        label = str(target.get(actor) or DEFAULT_LABELS.get(actor) or actor)
        translated = translated.replace(markers[actor], label)
    return translated


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
        _cell(3, "block", "道具停步", slot="prop", actions=1),
        _cell(4, "penalty_review", "惩罚任务"),
        _cell(5, "reward", "奖励抽卡", reward=REWARD_CARD_PASS),
        _cell(6, "move", "限制拖回", steps=-2),
        _cell(8, "clear_status", "解除状态"),
        _cell(9, "penalty_choice", "选择惩罚"),
        _cell(10, "move_self", "自己后退", steps=-3),
        _cell(11, "penalty_review", "惩罚任务"),
        _cell(12, "move", "奖励前进", steps=2),
        _cell(13, "move_other", "对方后退", steps=-2),
        _cell(14, "extend_status", "状态延长"),
        _cell(15, "swap_positions", "位置交换"),
        _cell(17, "block", "道具停步", slot="prop", actions=3),
        _cell(18, "replace_status", "替换地点", slot="place", duration_type="until_clear"),
        _cell(20, "penalty_review", "惩罚任务"),
        _cell(21, "penalty_choice", "选择惩罚"),
        _cell(22, "reward", "奖励抽卡", reward=REWARD_CARD_PASS),
        _cell(23, "clear_status", "解除状态"),
        _cell(24, "add_status", "最终姿势", slot="pose", duration_type="until_finish"),
        _cell(26, "penalty_review", "惩罚任务"),
        _cell(27, "reset_self", "重回起点"),
        _cell(29, "extend_status", "状态延长"),
        _cell(30, "penalty_choice", "选择惩罚"),
        _cell(31, "move", "限制拖回", steps=-2),
        _cell(32, "reward", "奖励抽卡", reward=REWARD_CARD_PASS),
        _cell(33, "penalty_review", "终局惩罚"),
        _cell(34, "block", "道具停步", slot="prop", actions=1),
        _cell(35, "clear_status", "最终整理"),
    ]
    finish = _cell(board_size, "finish", "终点")
    return [item for item in events if item["position"] < board_size] + [finish]


def _default_state(seed: str | None = None, board_size: int = DEFAULT_BOARD_SIZE) -> dict[str, Any]:
    seed_value = seed or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    now = utc_now_iso()
    state = {
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
        "final_note_items": [],
        "hands": {"player": {REWARD_CARD_PASS: 0}, "ai": {REWARD_CARD_PASS: 0}},
        "pass_skips_used": 0,
        "pending_event": None,
        "theme_profile": None,
        "final_note": None,
        "game_over": False,
        "winner": "",
        "result": "",
        "event_log": [],
    }
    _set_theme(state)
    return state


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
    raw_final_note_items = state.get("final_note_items") if isinstance(state.get("final_note_items"), list) else []
    final_note_items = []
    for item in raw_final_note_items:
        if not isinstance(item, dict) or not _status_item_allowed(item):
            continue
        normalized_item = _normalize_final_note_item(item) if _is_final_note_slot(str(item.get("slot") or "")) else item
        if normalized_item:
            final_note_items.append(normalized_item)
    state.setdefault("hands", {})
    for actor in ACTORS:
        state["positions"].setdefault(actor, 0)
        raw_statuses = state["statuses"].get(actor, [])
        actor_statuses = []
        for item in raw_statuses:
            if not isinstance(item, dict) or not _status_item_allowed(item):
                continue
            if _is_final_note_slot(str(item.get("slot") or "")):
                item = _normalize_final_note_item(item)
                if item:
                    final_note_items.append(item)
            else:
                actor_statuses.append(item)
        state["statuses"][actor] = actor_statuses
        _actor_hand(state, actor)
    deduped_final_note_items: list[dict[str, Any]] = []
    for item in final_note_items:
        slot = str(item.get("slot") or "").strip()
        if _is_final_note_slot(slot):
            deduped_final_note_items = [
                existing
                for existing in deduped_final_note_items
                if str(existing.get("slot") or "").strip() != slot
            ]
        deduped_final_note_items.append(item)
    state["final_note_items"] = deduped_final_note_items
    state["pass_skips_used"] = max(0, int(state.get("pass_skips_used") or 0))
    state.setdefault("turn_actor", "player")
    state.setdefault("pending_event", None)
    pending = state.get("pending_event") if isinstance(state.get("pending_event"), dict) else None
    state["pending_event"] = pending
    if pending and pending.get("type") == "duel":
        pending["first_actor"] = "player"
        pending.setdefault("opponent", _other(str(pending.get("actor") or "player")))
        picks = pending.get("picks") if isinstance(pending.get("picks"), dict) else {}
        pending["picks"] = picks
        if "player" not in picks:
            pending["current_actor"] = "player"
            state["turn_actor"] = "player"
        elif "ai" not in picks:
            pending["current_actor"] = "ai"
            state["turn_actor"] = "ai"
    state.setdefault("theme_profile", None)
    if not _theme_profile_allowed(state.get("theme_profile")):
        _set_theme(state)
    final_note = state.get("final_note") if isinstance(state.get("final_note"), dict) else None
    state["final_note"] = final_note
    if final_note and not _theme_name_allowed(str(final_note.get("theme") or "")):
        final_note["theme"] = str((state.get("theme_profile") or {}).get("theme") or "")
    state.setdefault("game_over", False)
    state.setdefault("winner", "")
    state.setdefault("result", "")
    winner = str(state.get("winner") or "")
    if state.get("game_over") and winner in ACTORS:
        state["positions"][winner] = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
        state["statuses"][winner] = []
        state["result"] = str(state.get("result") or "winner_control")
        if not isinstance(state.get("final_note"), dict):
            state["final_note"] = _build_final_note(state, winner=winner, target=_other(winner))
        target = str((state.get("final_note") or {}).get("target") or _other(winner))
        if target in ACTORS:
            _normalize_final_append_durations(state, target)
    state.setdefault("event_log", [])
    return state


def _normalize_final_append_durations(state: dict[str, Any], target: str) -> None:
    for item in state.get("statuses", {}).get(target) or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        if slot in {"prop", "limit"} and str(item.get("duration_type") or "") == "until_finish":
            item["duration_type"] = "final_note"


def _status_item_allowed(item: dict[str, Any]) -> bool:
    if str(item.get("slot") or "") != "prop":
        return True
    return str(item.get("value") or "").strip() not in INVALID_PROP_VALUES


def _normalize_final_note_item(item: dict[str, Any]) -> dict[str, Any] | None:
    slot = str(item.get("slot") or "").strip()
    if slot != "pose":
        return item
    value = _sanitize_pose_value(str(item.get("value") or ""))
    if not value:
        return None
    normalized = dict(item)
    normalized["value"] = value
    return normalized


def _sanitize_pose_value(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    replaced = POSE_VALUE_REPLACEMENTS.get(raw)
    if replaced:
        return replaced
    if _contains_any(raw, POSE_LOCATION_PATTERNS):
        return ""
    return raw


def _is_final_note_slot(slot: str) -> bool:
    return str(slot or "").strip() in {"place", "pose"}


def _final_note_slot_label(slot: str) -> str:
    slot_key = str(slot or "").strip()
    if slot_key == "place":
        return "最终地点"
    if slot_key == "pose":
        return "最终姿势"
    return "终局素材"


def _final_note_set_text(item: dict[str, Any]) -> str:
    return f"{_final_note_slot_label(str(item.get('slot') or ''))}设为：{item.get('value') or '未指定'}。"


def _theme_name_allowed(theme: str) -> bool:
    label = str(theme or "").strip()
    return bool(label and label in {str(item.get("name") or "").strip() for item in THEMES})


def _theme_profile_allowed(profile: Any) -> bool:
    if not isinstance(profile, dict):
        return False
    return _theme_name_allowed(str(profile.get("theme") or ""))


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
        return _payload(state, verb, "", labels)
    if verb in {"new_game", "new", "reset", "restart"}:
        seed, board_size = _parse_new_game_args(args)
        state.clear()
        state.update(_default_state(seed=seed, board_size=board_size))
        profile = state.get("theme_profile") or {}
        theme = str(profile.get("theme") or "").strip()
        lead = str(profile.get("lead") or profile.get("direction") or "").strip()
        theme_line = f"开局抽到主题：{theme}，主导方：{_actor_label(lead, labels)}。" if theme else ""
        return _payload(state, verb, _compact_text(["新局已开始。", theme_line]), labels)
    if verb in {"end_game", "end", "stop"}:
        state["game_over"] = True
        state["result"] = "游戏已手动结束。"
        return _payload(state, verb, "游戏已结束。", labels)
    if verb == "final_note_sent":
        return _payload(state, verb, _mark_final_note_sent(state), labels)
    if verb in {"append_final_status", "追加终局状态", "追加状态"}:
        return _payload(state, verb, _append_final_status(state, args, labels), labels)
    if verb in {"remove_final_status", "取消终局状态", "取消状态"}:
        return _payload(state, verb, _remove_final_status(state, args, labels), labels)
    if state.get("game_over"):
        return _payload(state, verb, "本局已经结束。使用 new_game 重新开始。", labels, ok=False)
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
    return _payload(state, verb, f"未知命令。{COMMAND_HINT}", labels, ok=False)


def _parse_command(command: str) -> tuple[str, str]:
    stripped = command.strip()
    if not stripped:
        return "status", ""
    duel_match = re.match(r"^(?:剪刀石头布|石头剪刀布)\s*[:：]\s*(.+)$", stripped)
    if duel_match:
        return "choose", duel_match.group(1).strip()
    parts = stripped.split(maxsplit=1)
    verb = parts[0].lower()
    if verb in {"剪刀石头布", "石头剪刀布"}:
        return "choose", parts[1].strip() if len(parts) > 1 else ""
    return verb, parts[1].strip() if len(parts) > 1 else ""


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
        return _payload(state, "roll", "当前还有待处理事件，先处理完再掷骰。", labels, ok=False)

    actor = state["turn_actor"]
    blocked = _consume_blocked_action(state, actor)
    if blocked:
        state["turn_index"] = int(state.get("turn_index") or 0) + 1
        text = _compact_text(
            [
                f"{_actor_label(actor, labels)}当前没有行动权，消耗 1 次限制。{_blocked_action_text(blocked)}",
                _advance_after_blocked_action(state, actor, labels),
            ]
        )
        _log(state, actor, text)
        return _payload(state, "roll", text, labels)

    dice_value = dice or _rng_int(state, 1, 6)
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    old_pos = int(state["positions"].get(actor) or 0)
    new_pos = min(board_size, old_pos + dice_value)
    state["positions"][actor] = new_pos
    state["turn_index"] = int(state.get("turn_index") or 0) + 1

    lines = [f"{_actor_label(actor, labels)}掷出 {dice_value}，从 {old_pos} 走到 {new_pos}。"]
    event_lines = _apply_cell_event(state, actor, new_pos, labels)
    lines.extend(event_lines)

    current_pos = int(state["positions"].get(actor) or 0)
    if current_pos >= board_size:
        _finish_game(state, actor)
        state["result"] = f"{_actor_label(actor, labels)}到达终点，状态清空，获得胜利。"
        lines.append(state["result"])
    elif not state.get("pending_event"):
        duel_line = _assign_duel_if_same_cell(state, actor, labels)
        if duel_line:
            lines.append(duel_line)
        else:
            lines.append(_advance_turn(state, actor, labels))

    text = _compact_text(lines)
    _log(state, actor, text)
    return _payload(state, "roll", text, labels)


def _finish_game(state: dict[str, Any], actor: str) -> None:
    target = _other(actor)
    state["positions"][actor] = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    state["statuses"][actor] = []
    state["game_over"] = True
    state["winner"] = actor
    state["final_note"] = _build_final_note(state, winner=actor, target=target)


def _build_final_note(state: dict[str, Any], *, winner: str, target: str) -> dict[str, Any]:
    profile = state.get("theme_profile") if isinstance(state.get("theme_profile"), dict) else {}
    return {
        "winner": winner,
        "target": target,
        "theme": str(profile.get("theme") or ""),
        "sent": False,
        "sent_at": "",
    }


def _append_final_status(state: dict[str, Any], args: str, labels: dict[str, str]) -> str:
    checked = _editable_final_note_target(state)
    if isinstance(checked, str):
        return checked
    note, target = checked

    args_text = str(args or "")
    level_match = re.search(r"(?:^|\s)(?:level|档位)=([1-5])(?:\s|$)", args_text)
    level = 1
    if level_match:
        level = int(level_match.group(1))
        args_text = re.sub(r"(?:^|\s)(?:level|档位)=[1-5](?:\s|$)", " ", args_text).strip()
    parts = args_text.split(maxsplit=1)
    slot = _final_append_slot(parts[0] if parts else "")
    value = " ".join((parts[1] if len(parts) > 1 else "").split()).strip()
    if not slot:
        return "请选择要追加的类型：道具惩罚或限制。"
    if not value:
        return "请先填写要追加的内容。"
    line = _add_status(
        state,
        target,
        slot,
        "final_note",
        labels,
        value=value,
        level=max(1, min(5, level)) if slot == "prop" and _prop_supports_level(value) else 1,
    )
    note["sent"] = False
    note["sent_at"] = ""
    if _is_final_note_slot(slot):
        return f"已追加到终局小纸条：{_final_note_slot_label(slot)}：{value}。"
    return f"已追加到终局小纸条：{line}"


def _remove_final_status(state: dict[str, Any], args: str, labels: dict[str, str]) -> str:
    checked = _editable_final_note_target(state)
    if isinstance(checked, str):
        return checked
    note, target = checked
    parts = str(args or "").split(maxsplit=1)
    slot = _final_append_slot(parts[0] if parts else "")
    value = " ".join((parts[1] if len(parts) > 1 else "").split()).strip()
    if not slot:
        return "请选择要取消的类型：道具惩罚或限制。"
    if not value:
        return "请先选择要取消的内容。"
    statuses = state["statuses"].setdefault(target, [])
    for index in range(len(statuses) - 1, -1, -1):
        item = statuses[index]
        if not isinstance(item, dict):
            continue
        if str(item.get("slot") or "") == slot and str(item.get("value") or "").strip() == value:
            removed = statuses.pop(index)
            note["sent"] = False
            note["sent_at"] = ""
            return f"已从终局小纸条取消：{_format_status_item(removed, include_duration=False)}。"
    return f"当前没有启用：{value}。"


def _editable_final_note_target(state: dict[str, Any]) -> tuple[dict[str, Any], str] | str:
    if not state.get("game_over"):
        return "本局还没有结束，不能修改终局状态。"
    note = state.get("final_note") if isinstance(state.get("final_note"), dict) else None
    if not note:
        winner = str(state.get("winner") or "")
        if winner not in ACTORS:
            return "当前没有可修改的终局小纸条。"
        note = _build_final_note(state, winner=winner, target=_other(winner))
        state["final_note"] = note
    if note.get("sent"):
        return "终局小纸条已经发送，不能再修改状态。"
    winner = str(note.get("winner") or state.get("winner") or "")
    if winner != "player":
        return "只有玩家先到终点时，才能修改终局状态。"
    target = str(note.get("target") or _other(winner))
    if target not in ACTORS:
        target = _other(winner)
        note["target"] = target
    return note, target


def _final_append_slot(slot_alias: str) -> str:
    key = str(slot_alias or "").strip()
    return FINAL_APPEND_SLOT_ALIASES.get(key) or FINAL_APPEND_SLOT_ALIASES.get(key.lower(), "")


def _mark_final_note_sent(state: dict[str, Any]) -> str:
    note = state.get("final_note") if isinstance(state.get("final_note"), dict) else None
    if not note:
        return "当前没有可发送的终局小纸条。"
    note["sent"] = True
    note["sent_at"] = utc_now_iso()
    return "终局小纸条已发送。"


def _consume_blocked_action(state: dict[str, Any], actor: str) -> dict[str, Any] | None:
    statuses = state["statuses"].get(actor, [])
    for item in list(statuses):
        if item.get("blocks_action") and int(item.get("remaining_actions") or 0) > 0:
            item["remaining_actions"] = max(0, int(item.get("remaining_actions") or 0) - 1)
            consumed = deepcopy(item)
            if int(item.get("remaining_actions") or 0) <= 0:
                consumed["block_finished"] = True
                if str(item.get("slot") or "") == "prop":
                    item.pop("blocks_action", None)
                    item.pop("remaining_actions", None)
                    item["duration_type"] = "until_clear"
                    consumed["prop_retained"] = True
                else:
                    statuses.remove(item)
            return consumed
    return None


def _actor_blocked(state: dict[str, Any], actor: str) -> bool:
    return any(
        item.get("blocks_action") and int(item.get("remaining_actions") or 0) > 0
        for item in state["statuses"].get(actor, [])
    )


def _blocked_action_text(blocked: dict[str, Any] | None) -> str:
    if not blocked:
        return ""
    if blocked.get("prop_retained"):
        return "停步已结束，道具惩罚仍保留。"
    if blocked.get("block_finished"):
        return "停步已结束。"
    return f"剩余停步次数：{blocked.get('remaining_actions', 0)}。"


def _advance_after_blocked_action(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    next_actor = _other(actor)
    if _actor_blocked(state, next_actor):
        blocked = _consume_blocked_action(state, next_actor)
        state["turn_index"] = int(state.get("turn_index") or 0) + 1
        state["turn_actor"] = actor
        return (
            f"{_actor_label(next_actor, labels)}也没有行动权，自动消耗 1 次限制。"
            f"{_actor_label(actor, labels)}继续处理停步回合。{_blocked_action_text(blocked)}"
        )
    state["turn_actor"] = next_actor
    return f"下一次行动：{_actor_label(next_actor, labels)}。"


def _advance_turn(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    next_actor = _other(actor)
    if _actor_blocked(state, next_actor):
        blocked = _consume_blocked_action(state, next_actor)
        if _actor_blocked(state, next_actor):
            state["turn_actor"] = actor
            return f"{_actor_label(next_actor, labels)}没有行动权，{_actor_label(actor, labels)}继续行动。{_blocked_action_text(blocked)}"
        state["turn_actor"] = next_actor
        return f"{_actor_label(next_actor, labels)}的行动权恢复。{_blocked_action_text(blocked)}"
    state["turn_actor"] = next_actor
    return f"下一次行动：{_actor_label(next_actor, labels)}。"


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
    elif kind == "move_self":
        lines.append(_move_without_event(state, actor, int(event.get("steps") or 0), labels))
    elif kind == "move_other":
        lines.append(_move_without_event(state, _other(actor), int(event.get("steps") or 0), labels))
    elif kind == "move_both":
        steps = int(event.get("steps") or 0)
        moved = [_move_without_event(state, item_actor, steps, labels) for item_actor in ACTORS]
        lines.append(" / ".join(moved))
    elif kind == "reset_all":
        before = {item_actor: int(state["positions"].get(item_actor) or 0) for item_actor in ACTORS}
        for item_actor in ACTORS:
            state["positions"][item_actor] = 0
        lines.append(f"双方回到起点（{_actor_label('player', labels)} {before['player']}->0；{_actor_label('ai', labels)} {before['ai']}->0）。")
    elif kind == "reset_self":
        old = int(state["positions"].get(actor) or 0)
        state["positions"][actor] = 0
        lines.append(f"{_actor_label(actor, labels)}从 {old} 回到起点。")
    elif kind == "reset_other":
        other = _other(actor)
        old = int(state["positions"].get(other) or 0)
        state["positions"][other] = 0
        lines.append(f"{_actor_label(other, labels)}从 {old} 回到起点。")
    elif kind == "finish_self":
        old = int(state["positions"].get(actor) or 0)
        state["positions"][actor] = board_size
        lines.append(f"{_actor_label(actor, labels)}从 {old} 直达终点。")
    elif kind == "swap_positions":
        state["positions"]["player"], state["positions"]["ai"] = state["positions"]["ai"], state["positions"]["player"]
        lines.append("双方交换位置。")
    elif kind == "clear_status":
        lines.append(_clear_status(state, actor, labels))
    elif kind == "extend_status":
        lines.append(_extend_status(state, actor, labels))
    elif kind == "replace_status":
        slot = str(event.get("slot") or "place")
        target_items = state.setdefault("final_note_items", []) if _is_final_note_slot(slot) else state["statuses"].get(actor, [])
        before = len(target_items)
        kept_items = [item for item in target_items if item.get("slot") != slot]
        removed = before - len(kept_items)
        if _is_final_note_slot(slot):
            state["final_note_items"] = kept_items
        else:
            state["statuses"][actor] = kept_items
        slot_label = _status_label(slot)
        lines.append(f"已移除 {removed} 个{slot_label}状态。" if removed else f"当前没有可替换的{slot_label}状态。")
        lines.append(_add_status(state, actor, slot, str(event.get("duration_type") or "until_clear"), labels))
    elif kind == "penalty_review":
        lines.append(_assign_review_penalty(state, actor, position, labels))
    elif kind == "penalty_choice":
        lines.append(_assign_choice_penalty(state, actor, position, labels))
    state["positions"][actor] = min(board_size, max(0, int(state["positions"].get(actor) or 0)))
    return lines


def _assign_duel_if_same_cell(state: dict[str, Any], actor: str, labels: dict[str, str]) -> str:
    if state.get("pending_event") or state.get("game_over"):
        return ""
    other = _other(actor)
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    pos = int(state["positions"].get(actor) or 0)
    other_pos = int(state["positions"].get(other) or -1)
    if pos <= 0 or pos >= board_size or pos != other_pos:
        return ""
    first_actor = "player"
    pending = {
        "id": f"duel-{pos}-{state.get('turn_index', 0)}",
        "type": "duel",
        "name": "剪刀石头布对抗",
        "actor": actor,
        "opponent": other,
        "reviewer": other,
        "first_actor": first_actor,
        "current_actor": first_actor,
        "phase": "first_pick",
        "choices": deepcopy(RPS_CHOICES),
        "picks": {},
        "pass_allowed": False,
        "cell": pos,
        "next_actor_after_event": other,
    }
    state["pending_event"] = pending
    state["turn_actor"] = first_actor
    return f"同格触发剪刀石头布对抗：{_actor_label(actor, labels)}和{_actor_label(other, labels)}在第 {pos} 格，等待{_actor_label(first_actor, labels)}出拳。"


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
    hand = _actor_hand(state, actor)
    hand[reward_id] = int(hand.get(reward_id) or 0) + 1
    return f"{_actor_label(actor, labels)}获得 {REWARD_CARD_LABELS.get(reward_id, reward_id)}。"


def _actor_hand(state: dict[str, Any], actor: str) -> dict[str, int]:
    hands = state.setdefault("hands", {})
    raw_hand = hands.get(actor) if isinstance(hands.get(actor), dict) else {}
    hand = {
        REWARD_CARD_PASS: max(0, int(raw_hand.get(REWARD_CARD_PASS) or 0)),
    }
    hands[actor] = hand
    return hand


def _add_status(state: dict[str, Any], actor: str, slot: str, duration_type: str, labels: dict[str, str], *, value: str | None = None, level: int = 1) -> str:
    value = value or _status_value(state, actor, slot)
    target_items = state.setdefault("final_note_items", []) if _is_final_note_slot(slot) else state["statuses"].setdefault(actor, [])
    if slot == "prop":
        existing = _find_status_by_value(state, actor, slot, value)
        if existing:
            if _status_supports_level(existing):
                existing["level"] = max(1, int(existing.get("level") or 1)) + 1
                return f"{_actor_label(actor, labels)}已有道具惩罚：{_format_status_item(existing)}，档位上调。"
            return f"{_actor_label(actor, labels)}已有道具惩罚：{_format_status_item(existing)}，不重复追加。"
    item = {
        "id": f"{slot}-{len(target_items) + 1}-{state.get('turn_index', 0)}",
        "slot": slot,
        "label": _status_label(slot),
        "value": value,
        "duration_type": duration_type,
        "level": level,
        "blocks_action": False,
    }
    if _is_final_note_slot(slot):
        state["final_note_items"] = [
            existing
            for existing in target_items
            if isinstance(existing, dict) and str(existing.get("slot") or "").strip() != slot
        ]
        state["final_note_items"].append(item)
        return _final_note_set_text(item)
    target_items.append(item)
    return f"{_actor_label(actor, labels)}新增状态：{_format_status_item(item)}。"


def _add_block(state: dict[str, Any], actor: str, slot: str, actions: int, labels: dict[str, str]) -> str:
    value = _status_value(state, actor, slot)
    if slot == "prop":
        existing = _find_status_by_value(state, actor, slot, value)
        if existing:
            existing["duration_type"] = "actions"
            existing["remaining_actions"] = max(1, int(existing.get("remaining_actions") or 0)) + max(1, int(actions))
            existing["blocks_action"] = True
            return f"{_actor_label(actor, labels)}已有道具惩罚：{_format_status_item(existing)}，行动限制延长。"
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


def _status_value(state: dict[str, Any], actor: str, slot: str) -> str:
    options = _limit_options_for_theme(state) if slot == "limit" else SLOTS.get(slot, {}).get("options") or (slot,)
    if slot != "limit":
        options = _theme_options_for_slot(state, slot, [str(item) for item in options])
    if slot == "pose":
        options = _filter_pose_options([str(item) for item in options])
    options = _status_options_for_actor(actor, slot, [str(item) for item in options])
    if slot == "prop":
        existing_values = {
            str(item.get("value") or "").strip()
            for item in state.get("statuses", {}).get(actor, [])
            if isinstance(item, dict) and str(item.get("slot") or "").strip() == "prop"
        }
        unused_options = [item for item in options if item not in existing_values]
        if unused_options:
            options = unused_options
    return str(_rng_pick(state, options))


def _find_status_by_value(state: dict[str, Any], actor: str, slot: str, value: str) -> dict[str, Any] | None:
    clean_value = str(value or "").strip()
    if not clean_value:
        return None
    for item in state.get("statuses", {}).get(actor, []):
        if not isinstance(item, dict):
            continue
        if str(item.get("slot") or "").strip() == slot and str(item.get("value") or "").strip() == clean_value:
            return item
    return None


def _limit_options_for_theme(state: dict[str, Any]) -> list[str]:
    profile = state.get("theme_profile") if isinstance(state.get("theme_profile"), dict) else {}
    theme = str(profile.get("theme") or "").strip()
    options = (*(THEME_LIMIT_OPTIONS.get(theme) or ()), *DEFAULT_LIMIT_OPTIONS)
    seen: set[str] = set()
    result: list[str] = []
    for item in options:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _filter_pose_options(options: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in options:
        value = _sanitize_pose_value(item)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _theme_options_for_slot(state: dict[str, Any], slot: str, options: list[str]) -> list[str]:
    profile = state.get("theme_profile") if isinstance(state.get("theme_profile"), dict) else {}
    theme = str(profile.get("theme") or "").strip()
    preferred = (THEME_OPTION_PREFERENCES.get(theme) or {}).get(slot) or ()
    patterns = tuple(str(item).strip() for item in preferred if str(item).strip())
    if not patterns:
        return options
    filtered = [item for item in options if _contains_any(item, patterns)]
    return filtered or options


def _status_options_for_actor(actor: str, slot: str, options: list[str]) -> list[str]:
    if slot != "prop":
        return options
    patterns = AI_ACTOR_FORBIDDEN_PROP_PATTERNS if actor == "ai" else HUMAN_ACTOR_FORBIDDEN_PROP_PATTERNS if actor == "player" else ()
    if not patterns:
        return options
    filtered = [item for item in options if not any(pattern and pattern in item for pattern in patterns)]
    return filtered or options


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern and pattern in text for pattern in patterns)


def _prop_supports_level(value: Any) -> bool:
    return _contains_any(str(value or ""), LEVELABLE_PROP_PATTERNS)


def _status_supports_level(item: dict[str, Any]) -> bool:
    return str(item.get("slot") or "") == "prop" and _prop_supports_level(item.get("value"))


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
    statuses = [
        item
        for item in state["statuses"].get(actor, [])
        if item.get("duration_type") == "actions" or _status_supports_level(item)
    ]
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
    reviewer = _other(actor)
    question_prompt = str(card.get("question_prompt") or "").strip()
    pending = {
        "id": f"review-{position}-{state.get('turn_index', 0)}",
        "type": "review",
        "card_id": card.get("id"),
        "name": card.get("name"),
        "actor": actor,
        "reviewer": reviewer,
        "phase": "questioning" if question_prompt else "assigned",
        "task": card.get("task"),
        "submission": card.get("submission"),
        "question_prompt": question_prompt,
        "question_text": "",
        "waiting_task": card.get("waiting_task") or "对方正在出题中。",
        "pass_result": card.get("pass_result"),
        "reject_prompt": card.get("reject_prompt"),
        "pass_allowed": bool(card.get("pass_allowed")),
        "cell": position,
        "theme": (state.get("theme_profile") or {}).get("theme") or "未触发主题",
        "reject_count": 0,
        "next_actor_after_event": _other(actor),
    }
    state["pending_event"] = pending
    state["turn_actor"] = reviewer if question_prompt else actor
    task = pending["waiting_task"] if question_prompt else pending["task"]
    return f"{_actor_label(actor, labels)}抽到验收任务：{task}"


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
        effect = choice.get("effect") or {}
        if effect.get("kind") == "upgrade_status_level" and required_slot == "prop":
            if not any(item.get("slot") == "prop" and _status_supports_level(item) for item in state["statuses"].get(actor, [])):
                continue
        result.append(choice)
    return result


def _submit(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "submit", "当前没有需要提交的验收任务。", labels, ok=False)
    actor = pending.get("actor")
    reviewer = pending.get("reviewer") or _other(actor)
    text = args.strip()
    if not text:
        return _payload(state, "submit", "提交内容不能为空。", labels, ok=False)
    if pending.get("phase") == "questioning":
        if state.get("turn_actor") != reviewer:
            return _payload(state, "submit", f"现在不是{_actor_label(reviewer, labels)}的出题回合。", labels, ok=False)
        pending["phase"] = "assigned"
        pending["question_text"] = text
        state["turn_actor"] = actor
        intro = f"{_actor_label(reviewer, labels)}已提交真心话问题，等待{_actor_label(actor, labels)}回答。"
        _log(state, reviewer, intro)
        return _payload(state, "submit", intro, labels)
    if state.get("turn_actor") != actor:
        return _payload(state, "submit", f"现在不是{_actor_label(actor, labels)}的提交回合。", labels, ok=False)
    pending["phase"] = "submitted"
    pending["submission_text"] = text
    state["turn_actor"] = reviewer
    intro = f"{_actor_label(actor, labels)}已提交任务，等待{_actor_label(state['turn_actor'], labels)}通过或驳回。"
    _log(state, actor, intro)
    return _payload(state, "submit", intro, labels)


def _approve(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "approve", "当前没有待验收任务。", labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "approve", f"正在等待{_actor_label(pending.get('actor'), labels)}先提交任务。", labels, ok=False)
    actor = pending.get("actor")
    intro = f"{_actor_label(reviewer, labels)}通过了{_actor_label(actor, labels)}的任务，本次事件完成。"
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    _log(state, reviewer, intro)
    return _payload(state, "approve", _compact_text([intro, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"]), labels)


def _reject(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending or pending.get("type") != "review":
        return _payload(state, "reject", "当前没有可驳回的验收任务。", labels, ok=False)
    reviewer = pending.get("reviewer")
    if state.get("turn_actor") != reviewer or pending.get("phase") != "submitted":
        return _payload(state, "reject", f"正在等待{_actor_label(pending.get('actor'), labels)}先提交任务。", labels, ok=False)
    pending["phase"] = "assigned"
    pending["reject_count"] = int(pending.get("reject_count") or 0) + 1
    reason = args.strip()
    if reason:
        pending["last_reject_reason"] = reason
    actor = pending.get("actor")
    state["turn_actor"] = actor
    intro = pending.get("reject_prompt") or f"{_actor_label(reviewer, labels)}驳回了提交，请重新提交。"
    _log(state, reviewer, intro)
    return _payload(state, "reject", intro, labels)


def _choose(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if pending and pending.get("type") == "duel":
        return _choose_duel(state, args, labels)
    if not pending or pending.get("type") != "choice":
        return _payload(state, "choose", "当前没有需要处理的选择惩罚。", labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "choose", f"现在不是{_actor_label(actor, labels)}的选择回合。", labels, ok=False)
    selected = _find_choice(pending.get("choices") or [], args)
    if not selected:
        return _payload(state, "choose", "没有找到这个选项。请使用 choose <选项id>。", labels, ok=False)
    result = _apply_choice_effect(state, actor, selected, labels)
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = _compact_text([f"{_actor_label(actor, labels)}选择了：{selected.get('label')}。", result, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"])
    _log(state, actor, intro)
    return _payload(state, "choose", intro, labels)


def _find_choice(choices: Iterable[dict[str, Any]], arg: str) -> dict[str, Any] | None:
    raw = arg.strip()
    for prefix in ("剪刀石头布", "石头剪刀布"):
        if raw.startswith(prefix):
            raw = raw.removeprefix(prefix).strip(" ：:")
            break
    needle = raw.lower()
    normalized_id = RPS_ALIASES.get(raw, needle)
    if not needle:
        return None
    for index, choice in enumerate(choices, start=1):
        values = {str(index), str(choice.get("id") or "").lower(), str(choice.get("label") or "").lower()}
        if needle in values:
            return choice
        if normalized_id == str(choice.get("id") or ""):
            return choice
    for choice in choices:
        if needle in str(choice.get("label") or "").lower():
            return choice
    return None


def _choose_duel(state: dict[str, Any], args: str, labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event") or {}
    actor = str(pending.get("actor") or "player")
    opponent = str(pending.get("opponent") or _other(actor))
    current = str(pending.get("current_actor") or actor)
    if state.get("turn_actor") != current:
        return _payload(state, "choose", f"现在不是{_actor_label(current, labels)}的出拳回合。", labels, ok=False)
    selected = _find_choice(pending.get("choices") or [], args)
    if not selected:
        return _payload(state, "choose", "没有这个出拳。可选：石头 / 剪刀 / 布。", labels, ok=False)
    selected_id = str(selected.get("id") or "")
    picks = pending.get("picks") if isinstance(pending.get("picks"), dict) else {}
    picks[current] = selected_id
    pending["picks"] = picks

    if actor not in picks or opponent not in picks:
        next_actor = opponent if current == actor else actor
        pending["current_actor"] = next_actor
        pending["phase"] = "second_pick"
        state["turn_actor"] = next_actor
        intro = f"{_actor_label(current, labels)}已出拳，等待{_actor_label(next_actor, labels)}出拳。"
        _log(state, current, intro)
        return _payload(state, "choose", intro, labels)

    actor_pick = str(picks.get(actor) or "")
    opponent_pick = str(picks.get(opponent) or "")
    if actor_pick == opponent_pick:
        first_actor = str(pending.get("first_actor") or "player")
        pending["picks"] = {}
        pending["current_actor"] = first_actor
        pending["phase"] = "first_pick"
        state["turn_actor"] = first_actor
        intro = f"系统判定：双方都出了{_rps_label(actor_pick)}，平局，重新选择。"
        _log(state, current, intro)
        return _payload(state, "choose", intro, labels)

    winner = actor if RPS_BEATS.get(actor_pick) == opponent_pick else opponent
    loser = opponent if winner == actor else actor
    board_size = int(state.get("board_size") or DEFAULT_BOARD_SIZE)
    state["positions"][winner] = min(board_size, int(state["positions"].get(winner) or 0) + 3)
    state["positions"][loser] = max(0, int(state["positions"].get(loser) or 0) - 3)
    state["pending_event"] = None
    winner_pick = _rps_label(actor_pick if winner == actor else opponent_pick)
    loser_pick = _rps_label(opponent_pick if winner == actor else actor_pick)
    lines = [
        f"系统判定：{_actor_label(winner, labels)}出{winner_pick}，{_actor_label(loser, labels)}出{loser_pick}，{_actor_label(winner, labels)}赢下对抗。",
        f"{_actor_label(winner, labels)}前进 3 格到 {state['positions'][winner]}，{_actor_label(loser, labels)}后退 3 格到 {state['positions'][loser]}。",
    ]
    if int(state["positions"].get(winner) or 0) >= board_size:
        _finish_game(state, winner)
        state["result"] = f"{_actor_label(winner, labels)}到达终点，状态清空，获得胜利。"
        lines.append(state["result"])
    else:
        state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
        lines.append(f"下一次行动：{_actor_label(state['turn_actor'], labels)}。")
    intro = _compact_text(lines)
    _log(state, current, intro)
    return _payload(state, "choose", intro, labels)


def _rps_label(choice_id: str) -> str:
    normalized = RPS_ALIASES.get(str(choice_id or "").strip(), str(choice_id or "").strip())
    for choice in RPS_CHOICES:
        if choice["id"] == normalized:
            return choice["label"]
    return normalized or "未出拳"


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
        return _add_block(state, actor, str(effect.get("slot") or "prop"), int(effect.get("actions") or 1), labels)
    return "没有结算任何效果。"


def _upgrade_status_level(state: dict[str, Any], actor: str, slot: str, delta: int, labels: dict[str, str]) -> str:
    for item in reversed(state["statuses"].get(actor, [])):
        if item.get("slot") == slot and (slot != "prop" or _status_supports_level(item)):
            item["level"] = int(item.get("level") or 1) + int(delta)
            return f"{_actor_label(actor, labels)}的状态已加码：{_format_status_item(item)}。"
    return f"{_actor_label(actor, labels)}当前没有可加码状态。"


def _pass_pending(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    pending = state.get("pending_event")
    if not pending:
        return _payload(state, "pass", "当前没有可跳过的待处理惩罚。", labels, ok=False)
    actor = pending.get("actor")
    if state.get("turn_actor") != actor:
        return _payload(state, "pass", f"只有{_actor_label(actor, labels)}可以跳过这个惩罚。", labels, ok=False)
    if not pending.get("pass_allowed"):
        return _payload(state, "pass", "这个惩罚不能使用 Pass 卡跳过。", labels, ok=False)
    if max(0, int(state.get("pass_skips_used") or 0)) >= PASS_SKIP_LIMIT:
        return _payload(state, "pass", "本局已经使用过一次 Pass 卡，不能再跳过惩罚任务。", labels, ok=False)
    hand = state["hands"].setdefault(actor, {REWARD_CARD_PASS: 0})
    if int(hand.get(REWARD_CARD_PASS) or 0) <= 0:
        return _payload(state, "pass", f"{_actor_label(actor, labels)}没有 Pass 卡。", labels, ok=False)
    hand[REWARD_CARD_PASS] = int(hand.get(REWARD_CARD_PASS) or 0) - 1
    state["pass_skips_used"] = max(0, int(state.get("pass_skips_used") or 0)) + 1
    state["pending_event"] = None
    state["turn_actor"] = pending.get("next_actor_after_event") or _other(actor)
    intro = f"{_actor_label(actor, labels)}使用 Pass 卡，跳过当前惩罚。"
    _log(state, actor, intro)
    return _payload(state, "pass", _compact_text([intro, f"下一次行动：{_actor_label(state['turn_actor'], labels)}。"]), labels)


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
    public["final_note"] = _final_note_public(state, {"player": "你", "ai": "对方"})
    public["theme_options"] = [str(item.get("name") or "").strip() for item in THEMES if str(item.get("name") or "").strip()]
    return public


def _payload(state: dict[str, Any], command: str, intro: str, labels: dict[str, str], ok: bool = True) -> dict[str, Any]:
    board = _board_payload(state)
    public_state = _state_public(state)
    intro_text = str(intro or "").strip()
    player_labels = {"player": "你", "ai": "对方"}
    ai_labels = {"player": "对方", "ai": "你"}
    return {
        "ok": ok,
        "game_id": GAME_ID,
        "command": command,
        "text": _status_text(state, labels, intro=intro_text),
        "player_text": _status_text(state, player_labels, intro=_translate_actor_labels(intro_text, labels, player_labels)),
        "ai_text": _status_text(state, ai_labels, intro=_translate_actor_labels(intro_text, labels, ai_labels)),
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
        _final_pose_line(state),
        _pending_line(state, labels),
        _final_note_text(state, labels) if state.get("game_over") else "",
    ]
    return _compact_text(lines)


def _final_note_public(state: dict[str, Any], labels: dict[str, str]) -> dict[str, Any] | None:
    note = state.get("final_note") if isinstance(state.get("final_note"), dict) else None
    if not note:
        return None
    payload = deepcopy(note)
    payload["text"] = _final_note_text(state, labels)
    payload["target_status"] = _status_summary(state, str(payload.get("target") or ""), include_duration=False)
    payload["final_note_items"] = _final_note_items_summary(state)
    payload["final_place"] = _final_note_slot_summary(state, "place")
    payload["final_pose"] = _final_pose_summary(state)
    return payload


def _final_note_text(state: dict[str, Any], labels: dict[str, str]) -> str:
    note = state.get("final_note") if isinstance(state.get("final_note"), dict) else None
    if not note:
        return ""
    winner = str(note.get("winner") or state.get("winner") or "player")
    target = str(note.get("target") or _other(winner))
    theme = str(note.get("theme") or (state.get("theme_profile") or {}).get("theme") or "本局主题")
    target_status = _status_summary(state, target, include_duration=False)
    final_place = _final_note_slot_summary(state, "place")
    final_pose = _final_pose_summary(state)
    parts = []
    if target_status:
        parts.append(f"{_actor_label(target, labels)}当前状态：{target_status}")
    if final_place:
        parts.append(f"最终地点：{final_place}")
    if final_pose:
        parts.append(f"最终姿势：{final_pose}")
    status_line = "；".join(parts) if parts else "没有遗留状态，可以自由决定最后玩法"
    return _compact_text([
        "【终局涩涩小纸条】",
        f"{_actor_label(winner, labels)}先到终点，{_actor_label(winner, labels)}的状态已清空。",
        f"请根据以下内容安排最后的玩法：{status_line}。",
        f"本局主题：{theme}。",
        "请尽情享受你们的ooxx吧！",
    ])


def _status_summary(state: dict[str, Any], actor: str, *, include_duration: bool = True) -> str:
    statuses = [
        item
        for item in state.get("statuses", {}).get(actor, [])
        if isinstance(item, dict) and not _is_final_note_slot(str(item.get("slot") or ""))
    ]
    if not statuses:
        return ""
    return "；".join(_group_status_items(statuses, include_duration=include_duration))


def _final_note_items_summary(state: dict[str, Any]) -> str:
    items = state.get("final_note_items") if isinstance(state.get("final_note_items"), list) else []
    valid_items = [item for item in items if isinstance(item, dict)]
    if not valid_items:
        return ""
    return "；".join(_group_status_items(valid_items))


def _final_pose_summary(state: dict[str, Any]) -> str:
    return _final_note_slot_summary(state, "pose")


def _final_note_slot_summary(state: dict[str, Any], slot: str) -> str:
    slot_key = str(slot or "").strip()
    items = state.get("final_note_items") if isinstance(state.get("final_note_items"), list) else []
    values = [
        _format_status_body(item, include_duration=False)
        for item in items
        if isinstance(item, dict) and str(item.get("slot") or "").strip() == slot_key
    ]
    return values[-1] if values else ""


def _final_pose_line(state: dict[str, Any]) -> str:
    final_place = _final_note_slot_summary(state, "place")
    final_pose = _final_pose_summary(state)
    return _compact_text([
        f"最终地点：{final_place}" if final_place else "",
        f"最终姿势：{final_pose}" if final_pose else "",
    ])


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
    statuses = [
        item
        for item in state.get("statuses", {}).get(actor, [])
        if isinstance(item, dict) and not _is_final_note_slot(str(item.get("slot") or ""))
    ]
    if not statuses:
        return f"{_actor_label(actor, labels)}状态：无"
    parts = _group_status_items(statuses)
    return f"{_actor_label(actor, labels)}状态：" + "；".join(parts)


def _duration_label(duration: str) -> str:
    if duration == "until_clear":
        return "待解除"
    if duration == "until_finish":
        return "到终点前有效"
    if duration == "final_note":
        return ""
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
        if pending.get("phase") == "questioning":
            return f"待处理验收任务：{pending.get('name')}；执行方：{actor}；状态：对方正在出题中；出题方：{reviewer}；任务：{pending.get('waiting_task')}"
        phase = "已提交，待验收" if pending.get("phase") == "submitted" else "待提交"
        question = f"；题目：{pending.get('question_text')}" if pending.get("question_text") else ""
        return f"待处理验收任务：{pending.get('name')}；执行方：{actor}；状态：{phase}；验收方：{reviewer}{question}；任务：{pending.get('task')}"
    if pending.get("type") == "choice":
        choices = ", ".join(f"{idx}. {item.get('label')} [{item.get('id')}]" for idx, item in enumerate(pending.get("choices") or [], start=1))
        return f"待处理选择惩罚：{pending.get('name')}；执行方：{actor}；{pending.get('prompt')} 选项：{choices}"
    if pending.get("type") == "duel":
        opponent = _actor_label(str(pending.get("opponent") or ""), labels)
        current = _actor_label(str(pending.get("current_actor") or pending.get("actor") or ""), labels)
        return f"待处理剪刀石头布对抗：{actor} vs {opponent}；当前出拳：{current}；可选：石头 / 剪刀 / 布；指令：【剪刀石头布：石头】"
    return f"待处理：{pending.get('name') or pending.get('type')}"


def _log(state: dict[str, Any], actor: str, text: str) -> None:
    event_log = state.setdefault("event_log", [])
    event_log.append({"at": utc_now_iso(), "actor": actor, "text": text})
    del event_log[:-50]

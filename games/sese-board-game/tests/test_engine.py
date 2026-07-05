from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sese_board_game.engine import run_command


def save_path() -> Path:
    return Path(tempfile.mkdtemp()) / "game.json"


def mutate_state(path: Path, mutator) -> None:
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    mutator(state)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle)


def test_new_game_and_manual_roll() -> None:
    path = save_path()
    payload = run_command("new_game seed=test", save_path=path)
    assert payload["ok"] is True
    assert payload["state"]["positions"] == {"player": 0, "ai": 0}

    payload = run_command("roll 3", save_path=path)
    assert payload["state"]["positions"]["player"] == 3
    assert payload["state"]["hands"]["player"]["pass"] == 1
    assert payload["state"]["turn_actor"] == "ai"


def test_blocked_action_is_consumed_without_deadlock() -> None:
    path = save_path()
    run_command("new_game seed=blocked", save_path=path)

    def add_block(state):
        state["turn_actor"] = "player"
        state["statuses"]["player"].append(
            {
                "slot": "prop",
                "label": "Prop Penalty",
                "value": "test block",
                "duration_type": "actions",
                "remaining_actions": 1,
                "blocks_action": True,
                "level": 1,
            }
        )

    mutate_state(path, add_block)

    payload = run_command("roll", save_path=path)
    assert payload["ok"] is True
    assert payload["state"]["positions"]["player"] == 0
    assert payload["state"]["turn_actor"] == "ai"
    assert payload["state"]["statuses"]["player"] == []


def test_review_task_submit_reject_approve() -> None:
    path = save_path()
    run_command("new_game seed=review", save_path=path)

    def setup_review_cell(state):
        state["positions"]["player"] = 10
        state["turn_actor"] = "player"

    mutate_state(path, setup_review_cell)
    payload = run_command("roll 1", save_path=path)
    assert payload["state"]["pending_event"]["type"] == "review"
    assert payload["state"]["turn_actor"] == "player"

    payload = run_command("submit a complete sample response", save_path=path)
    assert payload["state"]["pending_event"]["phase"] == "submitted"
    assert payload["state"]["turn_actor"] == "ai"

    payload = run_command("reject needs more detail", save_path=path)
    assert payload["state"]["pending_event"]["phase"] == "assigned"
    assert payload["state"]["turn_actor"] == "player"

    run_command("submit a more detailed sample response", save_path=path)
    payload = run_command("approve", save_path=path)
    assert payload["state"]["pending_event"] is None
    assert payload["state"]["turn_actor"] == "ai"


def test_choice_penalty_filters_unavailable_upgrade() -> None:
    path = save_path()
    run_command("new_game seed=choice", save_path=path)

    def setup_choice_cell(state):
        state["positions"]["player"] = 8
        state["turn_actor"] = "player"

    mutate_state(path, setup_choice_cell)
    payload = run_command("roll 1", save_path=path)
    pending = payload["state"]["pending_event"]
    if pending["type"] != "choice":
        raise AssertionError("cell 9 should create a choice penalty")
    for choice in pending["choices"]:
        assert not choice.get("requires")


def test_pass_card_skips_pending_penalty() -> None:
    path = save_path()
    run_command("new_game seed=pass", save_path=path)

    def setup_passable_review(state):
        state["positions"]["player"] = 10
        state["turn_actor"] = "player"
        state["hands"]["player"]["pass"] = 1

    mutate_state(path, setup_passable_review)
    run_command("roll 1", save_path=path)
    payload = run_command("pass", save_path=path)
    assert payload["ok"] is True
    assert payload["state"]["pending_event"] is None
    assert payload["state"]["hands"]["player"]["pass"] == 0


if __name__ == "__main__":
    test_new_game_and_manual_roll()
    test_blocked_action_is_consumed_without_deadlock()
    test_review_task_submit_reject_approve()
    test_choice_penalty_filters_unavailable_upgrade()
    test_pass_card_skips_pending_penalty()
    print("ok")

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sese_board_game.cards import CHOICE_PENALTY_CARDS, DEFAULT_LIMIT_OPTIONS, REVIEW_PENALTY_CARDS, SLOTS, THEME_LIMIT_OPTIONS, THEME_OPTION_PREFERENCES, THEMES
from sese_board_game.engine import _available_choices, _filter_pose_options, _limit_options_for_theme, _status_options_for_actor, _status_value, _theme_options_for_slot, build_cell_events, run_command
from sese_board_game.tool_adapter import execute_tool


PRIVATE_NAME_MARKERS = {"\u5c0f\u73a5", "\u6e21"}


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
    assert payload["state"]["theme_profile"]["theme"]
    assert payload["state"]["theme_options"] == [item["name"] for item in THEMES]
    assert payload["state"]["theme_profile"]["theme"] in payload["state"]["theme_options"]
    assert "开局抽到主题" in payload["player_text"]

    payload = run_command("roll 5", save_path=path)
    assert payload["state"]["positions"]["player"] == 5
    assert payload["state"]["hands"]["player"]["pass"] == 1
    assert payload["state"]["turn_actor"] == "ai"
    assert "你掷出 5" in payload["player_text"]
    assert "对方掷出 5" in payload["ai_text"]
    assert "下一次行动：你。" in payload["ai_text"]

    payload = run_command("roll 5", save_path=path)
    assert "对方获得" in payload["player_text"]
    assert "你获得" in payload["ai_text"]

    reward_positions = [item["position"] for item in build_cell_events() if item["kind"] in {"reward", "move_reward", "clear_reward"}]
    assert reward_positions == [5, 22, 32]
    review_positions = [item["position"] for item in build_cell_events() if item["kind"] == "penalty_review"]
    choice_positions = [item["position"] for item in build_cell_events() if item["kind"] == "penalty_choice"]
    assert review_positions == [4, 11, 20, 26, 33]
    assert choice_positions == [9, 21, 30]
    event_positions = {int(item["position"]) for item in build_cell_events() if item["position"] < 36}
    expected_empty_positions = {2, 7, 16, 19, 25, 28}
    assert event_positions == set(range(1, 36)) - expected_empty_positions
    assert {3, 4, 5, 9, 11, 13, 21, 23, 27, 29, 30, 31, 33, 34}.issubset(event_positions)
    event_kinds = {item["kind"] for item in build_cell_events()}
    assert {"move", "move_other", "move_self", "reset_self", "penalty_review", "penalty_choice"}.issubset(event_kinds)
    assert "reset_all" not in event_kinds
    assert "reset_other" not in event_kinds
    assert next(item for item in build_cell_events() if item["position"] == 27)["kind"] == "reset_self"


def test_reset_self_cell() -> None:
    path = save_path()
    run_command("new_game seed=reset-self", save_path=path)

    def setup_reset_cell(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 26
        state["positions"]["ai"] = 5

    mutate_state(path, setup_reset_cell)
    payload = run_command("roll 1", save_path=path)
    assert payload["state"]["positions"]["player"] == 0
    assert payload["state"]["game_over"] is False
    assert "重回起点" in payload["player_text"]


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
    player_statuses = payload["state"]["statuses"]["player"]
    assert len(player_statuses) == 1
    assert player_statuses[0]["slot"] == "prop"
    assert player_statuses[0]["duration_type"] == "until_clear"
    assert not player_statuses[0].get("blocks_action")
    assert "remaining_actions" not in player_statuses[0]
    assert "道具惩罚仍保留" in payload["player_text"]


def test_both_blocked_actions_are_consumed_without_deadlock() -> None:
    path = save_path()
    run_command("new_game seed=both-blocked", save_path=path)

    def add_blocks(state):
        state["turn_actor"] = "player"
        state["statuses"]["player"].append(
            {
                "slot": "prop",
                "label": "道具惩罚",
                "value": "player block",
                "duration_type": "actions",
                "remaining_actions": 1,
                "blocks_action": True,
                "level": 1,
            }
        )
        state["statuses"]["ai"].append(
            {
                "slot": "prop",
                "label": "道具惩罚",
                "value": "ai block",
                "duration_type": "actions",
                "remaining_actions": 1,
                "blocks_action": True,
                "level": 1,
            }
        )

    mutate_state(path, add_blocks)

    payload = run_command("roll", save_path=path)
    assert payload["ok"] is True
    assert payload["state"]["positions"]["player"] == 0
    assert payload["state"]["positions"]["ai"] == 0
    assert payload["state"]["turn_actor"] == "player"
    assert not payload["state"]["statuses"]["player"][0].get("blocks_action")
    assert not payload["state"]["statuses"]["ai"][0].get("blocks_action")
    assert "也没有行动权" in payload["player_text"]


def test_review_task_submit_reject_approve() -> None:
    path = save_path()
    run_command("new_game seed=review", save_path=path)

    def setup_review_cell(state):
        state["positions"]["player"] = 10
        state["turn_actor"] = "player"

    mutate_state(path, setup_review_cell)
    payload = run_command("roll 1", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["type"] == "review"
    if pending.get("phase") == "questioning":
        payload = run_command("submit a question for the player", save_path=path)
        assert payload["state"]["pending_event"]["phase"] == "assigned"
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

    upgrade_cards = [
        card
        for card in CHOICE_PENALTY_CARDS
        if any(str(choice.get("id") or "") == "upgrade_prop_level" for choice in card.get("choices") or () if isinstance(choice, dict))
    ]
    assert upgrade_cards
    no_prop_state = {"statuses": {"player": []}}
    plain_prop_state = {"statuses": {"player": [{"slot": "prop", "label": "道具惩罚", "value": "眼罩"}]}}
    levelable_prop_state = {"statuses": {"player": [{"slot": "prop", "label": "道具惩罚", "value": "跳蛋"}]}}
    for card in upgrade_cards:
        assert not any(choice.get("id") == "upgrade_prop_level" for choice in _available_choices(no_prop_state, "player", card.get("choices") or ()))
        assert not any(choice.get("id") == "upgrade_prop_level" for choice in _available_choices(plain_prop_state, "player", card.get("choices") or ()))
        assert any(choice.get("id") == "upgrade_prop_level" for choice in _available_choices(levelable_prop_state, "player", card.get("choices") or ()))


def test_pass_card_skips_pending_penalty() -> None:
    path = save_path()
    run_command("new_game seed=pass", save_path=path)

    def setup_passable_review(state):
        state["positions"]["player"] = 10
        state["turn_actor"] = "player"
        state["hands"]["player"]["pass"] = 1

    mutate_state(path, setup_passable_review)
    payload = run_command("roll 1", save_path=path)
    if payload["state"]["pending_event"].get("phase") == "questioning":
        payload = run_command("submit a question before pass", save_path=path)
        assert payload["state"]["pending_event"]["phase"] == "assigned"
    payload = run_command("pass", save_path=path)
    assert payload["ok"] is True
    assert payload["state"]["pending_event"] is None
    assert payload["state"]["hands"]["player"]["pass"] == 0
    assert payload["state"]["pass_skips_used"] == 1

    def setup_second_passable_review(state):
        state["positions"]["player"] = 10
        state["turn_actor"] = "player"
        state["hands"]["player"]["pass"] = 1
        state["pending_event"] = {
            "type": "choice",
            "actor": "player",
            "name": "第二个惩罚",
            "pass_allowed": True,
            "choices": [{"id": "prop", "label": "道具惩罚"}],
        }

    mutate_state(path, setup_second_passable_review)
    payload = run_command("pass", save_path=path)
    assert payload["ok"] is False
    assert payload["state"]["pending_event"] is not None
    assert payload["state"]["hands"]["player"]["pass"] == 1
    assert "已经使用过一次" in payload["player_text"]


def test_pass_without_card_is_rejected() -> None:
    path = save_path()
    run_command("new_game seed=no-pass", save_path=path)

    def setup_passable_review_without_card(state):
        state["turn_actor"] = "player"
        state["hands"]["player"]["pass"] = 0
        state["pending_event"] = {
            "type": "choice",
            "actor": "player",
            "name": "无卡惩罚",
            "pass_allowed": True,
            "choices": [{"id": "prop", "label": "道具惩罚"}],
        }

    mutate_state(path, setup_passable_review_without_card)
    payload = run_command("pass", save_path=path)
    assert payload["ok"] is False
    assert payload["state"]["pending_event"] is not None
    assert payload["state"]["hands"]["player"]["pass"] == 0
    assert "没有 Pass 卡" in payload["player_text"]


def test_duplicate_prop_is_not_stacked() -> None:
    path = save_path()
    run_command("new_game seed=dedupe-prop", save_path=path)

    def setup_duplicate_prop(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 16
        state["statuses"]["player"] = [
            {"slot": "prop", "label": "道具惩罚", "value": "眼罩", "duration_type": "until_clear", "level": 1}
        ]

    mutate_state(path, setup_duplicate_prop)
    payload = run_command("roll 1", save_path=path)
    props = [
        item for item in payload["state"]["statuses"]["player"]
        if item.get("slot") == "prop" and item.get("value") == "眼罩"
    ]
    assert len(props) == 1


def test_corpus_pruned_terms() -> None:
    banned = {
        "NTR幻想",
        "身份倒置",
        "反差诱惑",
        "秘密恋人",
        "支配臣服",
        "露出边缘",
        "身体崇拜",
        "感官剥夺",
        "和好炮",
        "久别重逢",
        "Alpha易感期",
        "临时标记",
        "强占有欲",
        "发情期交配成结",
        "民国旧上海play",
        "古代宫廷play",
        "电话做爱",
        "远程指令play",
        "电话指令",
        "皮革手套",
        "围巾",
        "网袜",
        "穿戴式玩具",
        "双头假阳具",
        "震动子弹",
        "透明胶带",
        "发绳",
        "跳蛋遥控器",
        "白衬衫",
        "领带",
        "皮带",
        "丝袜",
        "黑丝袜",
        "制服外套",
        "蜂蜜",
        "奶油",
        "冰棒",
        "电动牙刷",
        "口红",
        "浴缸骑乘",
        "陌生恋人play",
        "办公室偷情",
        "偷情play",
        "邻居偷情play",
        "摄影师模特play",
        "温度play",
        "吃醋惩罚",
        "强势命令",
        "奖惩调教",
        "罚跪调教",
        "命令羞耻",
        "体液标记",
        "天台雨后",
        "温室角落",
        "水族馆玻璃前",
        "成结",
        "易感期",
    }
    corpus_text = json.dumps({"themes": THEMES, "slots": SLOTS, "theme_limits": THEME_LIMIT_OPTIONS}, ensure_ascii=False)
    for term in banned:
        assert term not in corpus_text
    for name in PRIVATE_NAME_MARKERS:
        assert name not in corpus_text


def test_theme_specific_limit_pool() -> None:
    teacher_state = {"theme_profile": {"theme": "成人师生play"}}
    teacher_limits = _limit_options_for_theme(teacher_state)
    assert THEME_LIMIT_OPTIONS["成人师生play"][0] in teacher_limits
    assert any("教鞭" in item for item in teacher_limits)
    assert any("不许主动触碰对方" in item for item in teacher_limits)
    assert not any("医生" in item for item in teacher_limits)
    assert all(name not in item for name in PRIVATE_NAME_MARKERS for item in teacher_limits)

    butler_state = {"theme_profile": {"theme": "大小姐管家play"}}
    butler_limits = _limit_options_for_theme(butler_state)
    assert any("小姐" in item for item in butler_limits)
    assert any("不许主动触碰对方" in item for item in butler_limits)
    assert not any("医生" in item for item in butler_limits)

    pet_state = {"theme_profile": {"theme": "主人宠物play"}}
    pet_limits = _limit_options_for_theme(pet_state)
    assert any("主人喂食" in item for item in pet_limits)
    assert not any("医生" in item for item in pet_limits)

    assert _limit_options_for_theme({}) == list(DEFAULT_LIMIT_OPTIONS)


def test_theme_preferred_status_pools() -> None:
    teacher_state = {"theme_profile": {"theme": "成人师生play"}, "statuses": {"player": [], "ai": []}, "final_note_items": [], "turn_index": 0}
    teacher_places = _theme_options_for_slot(teacher_state, "place", list(SLOTS["place"]["options"]))
    assert teacher_places
    assert all(any(pattern in item for pattern in ("教室", "图书馆", "讲台")) for item in teacher_places)
    teacher_props = _theme_options_for_slot(teacher_state, "prop", list(SLOTS["prop"]["options"]))
    assert teacher_props == ["眼罩", "戒尺"]
    teacher_tasks = _theme_options_for_slot(teacher_state, "task", list(SLOTS["task"]["options"]))
    assert teacher_tasks
    assert all(any(pattern in item for pattern in ("报备", "检查", "命令", "羞耻", "台词")) for item in teacher_tasks)
    assert _status_value(teacher_state, "player", "place") in teacher_places

    butler_state = {"theme_profile": {"theme": "大小姐管家play"}, "statuses": {"player": [], "ai": []}, "final_note_items": [], "turn_index": 0}
    butler_tasks = _theme_options_for_slot(butler_state, "task", list(SLOTS["task"]["options"]))
    assert butler_tasks
    assert all(any(pattern in item for pattern in ("伺候", "命令", "验收", "围裙", "乖", "交给对方", "听对方")) for item in butler_tasks)

    assert _theme_options_for_slot({"theme_profile": {"theme": "不存在的主题"}}, "task", ["A", "B"]) == ["A", "B"]
    assert set(THEME_LIMIT_OPTIONS).issubset(set(THEME_OPTION_PREFERENCES))


def test_actor_prop_safety_filters() -> None:
    options = ["锁精环", "阴蒂吸吮器", "吸乳器", "胸链"]
    assert _status_options_for_actor("player", "prop", options) == ["阴蒂吸吮器", "吸乳器", "胸链"]
    assert _status_options_for_actor("ai", "prop", options) == ["锁精环", "胸链"]


def test_review_penalty_pool_and_final_pose_choices() -> None:
    names = {str(card.get("name") or "") for card in REVIEW_PENALTY_CARDS}
    expected = {"反向诱惑", "全部暴露！", "羞耻台词大放送", "自慰陈述", "真心话点名"}
    assert expected.issubset(names)
    truth_cards = [card for card in REVIEW_PENALTY_CARDS if "真心话" in str(card.get("name") or "")]
    assert len(truth_cards) == 1
    truth_question = next(card for card in truth_cards if str(card.get("id") or "") == "truth_question_by_partner")
    assert truth_question.get("task") == "这是一张真心话任务。请诚实回答对方的问题。"
    assert truth_question.get("submission") == "写下你对这个问题的回答。"
    assert truth_question.get("waiting_task") == "对方正在出题中。"
    assert "很想知道答案" in str(truth_question.get("question_prompt") or "")
    assert "真心话追问" not in names
    assert "主动索求" not in names
    assert "惩罚复盘" not in names
    assert "主题指令改写" not in names
    for card in CHOICE_PENALTY_CARDS:
        has_final_material = any(str((choice.get("effect") or {}).get("slot") or "") in {"place", "pose"} for choice in card.get("choices") or [])
        if has_final_material:
            assert card.get("pass_allowed") is False
            assert "惩罚" not in str(card.get("prompt") or "")
    assert "浴缸骑乘" not in _filter_pose_options(list(SLOTS["pose"]["options"]))
    assert "骑乘位" in _filter_pose_options(list(SLOTS["pose"]["options"]))


def test_final_pose_is_note_material() -> None:
    path = save_path()
    run_command("new_game seed=pose-material", save_path=path)

    def setup_pose_material(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 22
        state["final_note_items"] = [
            {"slot": "place", "label": "地点", "value": "旧地点", "duration_type": "until_finish"},
            {"slot": "pose", "label": "姿势", "value": "旧姿势", "duration_type": "until_finish"},
            {"slot": "pose", "label": "姿势", "value": "新姿势", "duration_type": "until_finish"},
            {"slot": "pose", "label": "姿势", "value": "浴缸骑乘", "duration_type": "until_finish"},
        ]
        state["statuses"]["player"] = [{"slot": "prop", "label": "道具", "value": "测试道具", "duration_type": "until_clear"}]
        state["statuses"]["ai"] = [
            {"slot": "place", "label": "地点", "value": "迁移地点", "duration_type": "until_finish"},
            {"slot": "pose", "label": "姿势", "value": "迁移姿势", "duration_type": "until_finish"},
        ]

    mutate_state(path, setup_pose_material)
    payload = run_command("status", save_path=path)
    places = [item for item in payload["state"]["final_note_items"] if item.get("slot") == "place"]
    assert len(places) == 1
    assert places[0]["value"] == "迁移地点"
    poses = [item for item in payload["state"]["final_note_items"] if item.get("slot") == "pose"]
    assert len(poses) == 1
    assert poses[0]["value"] == "迁移姿势"
    assert "浴缸骑乘" not in str(payload["state"]["final_note_items"])
    assert not any(item.get("slot") == "place" for item in payload["state"]["statuses"]["ai"])
    assert not any(item.get("slot") == "pose" for item in payload["state"]["statuses"]["ai"])

    payload = run_command("roll 1", save_path=path)
    places = [item for item in payload["state"]["final_note_items"] if item.get("slot") == "place"]
    assert len(places) == 1
    assert "最终地点：迁移地点" in payload["player_text"]
    poses = [item for item in payload["state"]["final_note_items"] if item.get("slot") == "pose"]
    assert len(poses) == 1
    assert "最终姿势：迁移姿势" in payload["player_text"]


def test_truth_question_flow() -> None:
    path = save_path()
    run_command("new_game seed=truth-question", save_path=path)
    card = next(card for card in REVIEW_PENALTY_CARDS if str(card.get("id") or "") == "truth_question_by_partner")

    def setup_truth_question(state):
        state["turn_actor"] = "ai"
        state["pending_event"] = {
            "id": "truth-test",
            "type": "review",
            "card_id": "truth_question_by_partner",
            "name": card["name"],
            "actor": "player",
            "reviewer": "ai",
            "phase": "questioning",
            "task": card["task"],
            "submission": card["submission"],
            "question_prompt": card["question_prompt"],
            "question_text": "",
            "waiting_task": card["waiting_task"],
            "pass_result": card["pass_result"],
            "reject_prompt": card["reject_prompt"],
            "pass_allowed": True,
            "cell": 11,
            "theme": "测试主题",
            "reject_count": 0,
        }

    mutate_state(path, setup_truth_question)
    payload = run_command("status", save_path=path)
    assert "对方正在出题中" in payload["player_text"]
    assert "出题方：你" in payload["ai_text"]

    payload = run_command("submit 你最想知道什么？", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["phase"] == "assigned"
    assert pending["question_text"] == "你最想知道什么？"
    assert payload["state"]["turn_actor"] == "player"
    assert "题目：你最想知道什么？" in payload["player_text"]
    assert "任务：这是一张真心话任务。请诚实回答对方的问题。" in payload["player_text"]

    payload = run_command("submit 我的回答", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["phase"] == "submitted"
    assert pending["submission_text"] == "我的回答"
    assert payload["state"]["turn_actor"] == "ai"


def test_same_cell_duel_flow() -> None:
    path = save_path()
    run_command("new_game seed=duel", save_path=path)

    def setup_duel(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 4
        state["positions"]["ai"] = 5

    mutate_state(path, setup_duel)
    payload = run_command("roll 1", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["type"] == "duel"
    assert pending["current_actor"] == "player"
    assert "剪刀石头布对抗" in payload["player_text"]

    payload = run_command("choose 石头", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["type"] == "duel"
    assert pending["current_actor"] == "ai"
    assert payload["state"]["turn_actor"] == "ai"

    payload = run_command("剪刀石头布: 剪刀", save_path=path)
    assert payload["state"]["pending_event"] is None
    assert payload["state"]["positions"]["player"] == 8
    assert payload["state"]["positions"]["ai"] == 2
    assert payload["state"]["turn_actor"] == "ai"
    assert "系统判定" in payload["player_text"]


def test_ai_triggered_duel_still_player_first() -> None:
    path = save_path()
    run_command("new_game seed=ai-duel", save_path=path)

    def setup_duel(state):
        state["turn_actor"] = "ai"
        state["positions"]["player"] = 5
        state["positions"]["ai"] = 4

    mutate_state(path, setup_duel)
    payload = run_command("roll 1", save_path=path)
    pending = payload["state"]["pending_event"]
    assert pending["type"] == "duel"
    assert pending["current_actor"] == "player"
    assert payload["state"]["turn_actor"] == "player"


def test_finish_generates_final_note() -> None:
    path = save_path()
    run_command("new_game seed=finish-note", save_path=path)

    def setup_finish(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 35
        state["statuses"]["player"] = [{"slot": "prop", "label": "道具", "value": "赢家旧状态"}]
        state["statuses"]["ai"] = [
            {"slot": "prop", "label": "道具", "value": "目标状态"},
            {"slot": "pose", "label": "姿势", "value": "跪趴"},
        ]

    mutate_state(path, setup_finish)
    payload = run_command("roll 1", save_path=path)
    assert payload["state"]["game_over"] is True
    assert payload["state"]["winner"] == "player"
    assert payload["state"]["statuses"]["player"] == []
    assert payload["state"]["statuses"]["ai"]
    assert not any(item.get("slot") == "pose" for item in payload["state"]["statuses"]["ai"])
    note = payload["state"]["final_note"]
    assert note["target"] == "ai"
    assert note["final_pose"] == "跪趴"
    assert "跪趴" in note["text"]
    assert "请尽情享受你们的ooxx吧" in note["text"]

    payload = run_command("final_note_sent", save_path=path)
    assert payload["state"]["final_note"]["sent"] is True


def test_player_winner_can_append_final_status() -> None:
    path = save_path()
    run_command("new_game seed=append-final", save_path=path)

    def setup_finish(state):
        state["turn_actor"] = "player"
        state["positions"]["player"] = 35
        state["statuses"]["player"] = [{"slot": "prop", "label": "道具惩罚", "value": "赢家旧状态"}]
        state["statuses"]["ai"] = []

    mutate_state(path, setup_finish)
    payload = run_command("roll 1", save_path=path)
    assert payload["state"]["winner"] == "player"
    assert payload["state"]["statuses"]["ai"] == []
    assert "没有遗留状态" in payload["state"]["final_note"]["text"]

    payload = run_command("append_final_status prop 眼罩 level=3", save_path=path)
    appended_prop = next((item for item in payload["state"]["statuses"]["ai"] if item.get("slot") == "prop" and item.get("value") == "眼罩"), None)
    assert appended_prop is not None
    assert appended_prop["duration_type"] == "final_note"
    assert appended_prop["level"] == 1
    assert "眼罩" in payload["state"]["final_note"]["target_status"]
    assert "眼罩（3档）" not in payload["state"]["final_note"]["target_status"]
    assert "到终点前有效" not in payload["state"]["final_note"]["target_status"]
    assert "对方当前状态：道具惩罚：眼罩" in payload["state"]["final_note"]["text"]
    assert "到终点前有效" not in payload["state"]["final_note"]["text"]
    payload = run_command("append_final_status prop 跳蛋 level=3", save_path=path)
    assert "跳蛋（3档）" in payload["state"]["final_note"]["target_status"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["statuses"]["ai"][0]["duration_type"] = "until_finish"
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    migrated = run_command("status", save_path=path)
    migrated_prop = next((item for item in migrated["state"]["statuses"]["ai"] if item.get("slot") == "prop" and item.get("value") == "眼罩"), None)
    assert migrated_prop and migrated_prop["duration_type"] == "final_note"
    assert "到终点前有效" not in migrated["state"]["final_note"]["target_status"]

    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["statuses"]["ai"].extend([
        {
            "slot": "prop",
            "label": "道具惩罚",
            "value": "震动乳夹",
            "duration_type": "actions",
            "remaining_actions": 3,
            "blocks_action": True,
            "level": 2,
        },
        {
            "slot": "limit",
            "label": "限制",
            "value": "不准抬头",
            "duration_type": "until_clear",
        },
    ])
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    payload = run_command("status", save_path=path)
    assert "震动乳夹（2档）" in payload["state"]["final_note"]["target_status"]
    assert "不准抬头" in payload["state"]["final_note"]["target_status"]
    assert "停步剩余" not in payload["state"]["final_note"]["target_status"]
    assert "待解除" not in payload["state"]["final_note"]["target_status"]
    assert "停步剩余" not in payload["state"]["final_note"]["text"]
    assert "待解除" not in payload["state"]["final_note"]["text"]

    payload = run_command("remove_final_status prop 跳蛋", save_path=path)
    assert not any(item.get("slot") == "prop" and item.get("value") == "跳蛋" for item in payload["state"]["statuses"]["ai"])
    assert "跳蛋" not in payload["state"]["final_note"]["target_status"]

    payload = run_command("append_final_status limit 不准提前结束", save_path=path)
    assert any(item.get("slot") == "limit" and item.get("value") == "不准提前结束" for item in payload["state"]["statuses"]["ai"])
    assert "不准提前结束" in payload["state"]["final_note"]["target_status"]
    rejected_slot = run_command("append_final_status pose 骑乘位", save_path=path)
    assert "道具惩罚或限制" in rejected_slot["player_text"]

    run_command("final_note_sent", save_path=path)
    rejected = run_command("append_final_status limit 追加限制", save_path=path)
    rejected_remove = run_command("remove_final_status prop 眼罩", save_path=path)
    assert "已经发送" in rejected["player_text"]
    assert "已经发送" in rejected_remove["player_text"]


def test_ended_save_migration_creates_final_note() -> None:
    path = save_path()
    run_command("new_game seed=ended-migration", save_path=path)

    def setup_old_ended_save(state):
        state["game_over"] = True
        state["winner"] = "player"
        state["theme_profile"] = {"theme": "感官剥夺", "lead": "ai", "direction": "ai", "direction_label": "对方主导"}
        state["statuses"]["player"] = [{"slot": "limit", "label": "限制", "value": "winner old status"}]
        state["statuses"]["ai"] = [{"slot": "prop", "label": "道具惩罚", "value": "避孕套"}]
        state["final_note"] = {"winner": "player", "target": "ai", "theme": "感官剥夺", "sent": False}

    mutate_state(path, setup_old_ended_save)
    payload = run_command("status", save_path=path)
    assert payload["state"]["statuses"]["player"] == []
    assert payload["state"]["statuses"]["ai"] == []
    assert payload["state"]["final_note"]["target"] == "ai"
    assert payload["state"]["final_note"]["theme"] != "感官剥夺"
    assert "请尽情享受你们的ooxx吧" in payload["state"]["final_note"]["text"]
    assert "避孕套" not in payload["player_text"]


def test_tool_adapter_returns_ai_readable_text_not_json() -> None:
    path = save_path()
    text = execute_tool({"command": "new_game seed=adapter", "save_path": str(path)})
    assert text
    assert not text.lstrip().startswith("{")
    assert '"state"' not in text
    assert "进度：对方 0/36 | 你 0/36" in text

    run_command("roll 3", save_path=path)
    text = execute_tool({"command": "roll 2", "save_path": str(path)})
    assert "你掷出 2" in text
    assert "轮到：对方" in text


if __name__ == "__main__":
    test_new_game_and_manual_roll()
    test_reset_self_cell()
    test_blocked_action_is_consumed_without_deadlock()
    test_both_blocked_actions_are_consumed_without_deadlock()
    test_review_task_submit_reject_approve()
    test_choice_penalty_filters_unavailable_upgrade()
    test_pass_card_skips_pending_penalty()
    test_pass_without_card_is_rejected()
    test_duplicate_prop_is_not_stacked()
    test_corpus_pruned_terms()
    test_theme_specific_limit_pool()
    test_theme_preferred_status_pools()
    test_actor_prop_safety_filters()
    test_review_penalty_pool_and_final_pose_choices()
    test_final_pose_is_note_material()
    test_truth_question_flow()
    test_same_cell_duel_flow()
    test_ai_triggered_duel_still_player_first()
    test_finish_generates_final_note()
    test_player_winner_can_append_final_status()
    test_ended_save_migration_creates_final_note()
    test_tool_adapter_returns_ai_readable_text_not_json()
    print("ok")

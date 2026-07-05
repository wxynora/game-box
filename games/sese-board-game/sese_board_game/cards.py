from __future__ import annotations

from typing import Any


THEMES: tuple[dict[str, str], ...] = (
    {"id": "teacher_student", "name": "Teacher / Student", "lead": "ai"},
    {"id": "boss_subordinate", "name": "Boss / Subordinate", "lead": "ai"},
    {"id": "maid_master", "name": "Maid / Master", "lead": "ai"},
    {"id": "lady_butler", "name": "Lady / Butler", "lead": "player"},
    {"id": "doctor_checkup", "name": "Doctor Checkup", "lead": "ai"},
    {"id": "secretary_boss", "name": "Secretary / Boss", "lead": "ai"},
    {"id": "tutor_student", "name": "Tutor / Student", "lead": "ai"},
    {"id": "knight_princess", "name": "Knight / Princess", "lead": "ai"},
    {"id": "vampire_human", "name": "Vampire / Human", "lead": "player"},
)


SLOTS: dict[str, dict[str, Any]] = {
    "theme": {
        "label": "Theme",
        "options": [item["name"] for item in THEMES],
    },
    "prop": {
        "label": "Prop Penalty",
        "options": (
            "blindfold",
            "collar",
            "ribbon restraint",
            "maid outfit",
            "gloves",
            "tie",
            "bell collar",
            "feather wand",
        ),
    },
    "limit": {
        "label": "Rule",
        "options": (
            "must ask before moving closer",
            "must answer honestly",
            "must obey the current theme",
            "must keep the assigned role",
            "must narrate reactions clearly",
            "must wait for the other player's approval",
        ),
    },
    "task": {
        "label": "Task",
        "options": (
            "make one theme-matched request",
            "write three in-character lines",
            "describe what you want from the other player",
            "offer one roleplay bargain",
            "pick one status for the other player to inspect",
        ),
    },
    "pose": {
        "label": "Pose",
        "options": (
            "kneeling",
            "hands behind back",
            "sitting still",
            "standing at attention",
            "head lowered",
            "waiting posture",
        ),
    },
    "place": {
        "label": "Place",
        "options": (
            "classroom",
            "office",
            "bedroom",
            "hallway",
            "clinic room",
            "castle balcony",
            "moonlit room",
        ),
    },
}


REWARD_CARD_PASS = "pass"
REWARD_CARD_LABELS = {
    REWARD_CARD_PASS: "Pass Card",
}


REVIEW_PENALTY_CARDS: tuple[dict[str, Any], ...] = (
    {
        "id": "reverse_invitation",
        "name": "Reverse Invitation",
        "type": "review",
        "task": "Submit a theme-matched request for something you want the other player to do.",
        "submission": "Write a complete request, not only keywords.",
        "pass_result": "The task is complete after the other player approves it.",
        "reject_prompt": "The other player says the request is too vague. Submit a more specific version.",
        "pass_allowed": True,
    },
    {
        "id": "ranked_confession",
        "name": "Ranked Confession",
        "type": "review",
        "task": "List five current weaknesses or sensitive states from mildest to strongest.",
        "submission": "Write a clear ordered list with enough detail for the other player to judge.",
        "pass_result": "The task is complete after the other player approves it.",
        "reject_prompt": "The other player says the confession is not specific enough. Submit again.",
        "pass_allowed": True,
    },
    {
        "id": "embarrassing_lines",
        "name": "Embarrassing Lines",
        "type": "review",
        "task": "Write three theme-matched pleading or coaxing lines for the other player.",
        "submission": "Submit three full lines.",
        "pass_result": "The task is complete after the other player approves it.",
        "reject_prompt": "The other player says the lines are not committed enough. Submit again.",
        "pass_allowed": True,
    },
    {
        "id": "personal_statement",
        "name": "Personal Statement",
        "type": "review",
        "task": "Write a theme-matched private statement for the other player to review.",
        "submission": "Write one complete paragraph.",
        "pass_result": "The task is complete after the other player approves it.",
        "reject_prompt": "The other player says the statement is not detailed enough. Submit again.",
        "pass_allowed": True,
    },
)


CHOICE_PENALTY_CARDS: tuple[dict[str, Any], ...] = (
    {
        "id": "prop_or_rule",
        "name": "Prop or Rule",
        "type": "choice",
        "prompt": "Choose one penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop", "label": "Add a prop penalty", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
            {"id": "add_limit", "label": "Add a rule", "effect": {"kind": "add_status", "slot": "limit", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "new_or_upgrade_prop",
        "name": "New or Upgrade",
        "type": "choice",
        "prompt": "Choose one prop penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop", "label": "Add a prop penalty", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
            {"id": "upgrade_prop_level", "label": "Increase an existing prop penalty by one level", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
        ),
    },
    {
        "id": "back_or_prop",
        "name": "Back or Prop",
        "type": "choice",
        "prompt": "Choose one penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "move_back_2", "label": "Move back 2 cells", "effect": {"kind": "move", "steps": -2}},
            {"id": "add_prop", "label": "Add a prop penalty", "effect": {"kind": "add_status", "slot": "prop", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "lose_action_or_upgrade",
        "name": "Pause or Upgrade",
        "type": "choice",
        "prompt": "Choose one penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "lose_action", "label": "Lose 1 action", "effect": {"kind": "add_block", "slot": "prop", "actions": 1}},
            {"id": "upgrade_prop_level", "label": "Increase an existing prop penalty by one level", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
        ),
    },
    {
        "id": "pose_or_place",
        "name": "Pose or Place",
        "type": "choice",
        "prompt": "Choose one state penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "add_pose", "label": "Add a pose state", "effect": {"kind": "add_status", "slot": "pose", "duration_type": "until_finish"}},
            {"id": "add_place", "label": "Add a place state", "effect": {"kind": "add_status", "slot": "place", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "rule_or_task",
        "name": "Rule or Task",
        "type": "choice",
        "prompt": "Choose one penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "add_limit", "label": "Add a rule", "effect": {"kind": "add_status", "slot": "limit", "duration_type": "until_clear"}},
            {"id": "add_task", "label": "Add a task state", "effect": {"kind": "add_status", "slot": "task", "duration_type": "until_clear"}},
        ),
    },
    {
        "id": "heavy_prop_or_back",
        "name": "Heavy Choice",
        "type": "choice",
        "prompt": "Choose one heavier penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "add_prop_and_lose_action", "label": "Add a prop penalty and lose 1 action", "effect": {"kind": "add_status_and_block", "slot": "prop", "actions": 1}},
            {"id": "move_back_3", "label": "Move back 3 cells", "effect": {"kind": "move", "steps": -3}},
        ),
    },
    {
        "id": "upgrade_or_pose",
        "name": "Upgrade or Pose",
        "type": "choice",
        "prompt": "Choose one penalty.",
        "pass_allowed": True,
        "choices": (
            {"id": "upgrade_prop_level", "label": "Increase an existing prop penalty by one level", "requires": {"status_slot": "prop"}, "effect": {"kind": "upgrade_status_level", "slot": "prop", "delta": 1}},
            {"id": "add_pose", "label": "Add a pose state", "effect": {"kind": "add_status", "slot": "pose", "duration_type": "until_finish"}},
        ),
    },
)

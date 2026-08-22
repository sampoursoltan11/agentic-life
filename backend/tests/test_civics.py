"""Pure-logic tests for the civic machinery's validation rules."""
from app.world.civics import _valid_rule_body, _valid_sanction_body

RULES = [
    {"id": "violence", "text": "Do not attack.", "penalty": -6},
    {"id": "theft", "text": "Do not steal.", "penalty": -3},
]
AGENTS = {"pim", "greta"}
LOCATIONS = {"tavern", "town_hall"}


def test_rule_add_valid():
    body = {"op": "add", "rule_id": "curfew", "text": "Be home by midnight.", "penalty": -1}
    assert _valid_rule_body(body, RULES) is None


def test_rule_add_rejects_duplicate_and_bad_ids():
    assert _valid_rule_body({"op": "add", "rule_id": "theft", "text": "x" * 20}, RULES)
    assert _valid_rule_body({"op": "add", "rule_id": "Bad Id!", "text": "x" * 20}, RULES)
    assert _valid_rule_body({"op": "add", "rule_id": "ok_rule", "text": "short"}, RULES)


def test_rule_add_rejects_positive_penalty():
    body = {"op": "add", "rule_id": "bonus", "text": "Reward my friends please.", "penalty": 5}
    assert _valid_rule_body(body, RULES)


def test_rule_change_and_remove_require_existing_rule():
    assert _valid_rule_body({"op": "change", "rule_id": "nope"}, RULES)
    assert _valid_rule_body({"op": "change", "rule_id": "theft"}, RULES) is None
    assert _valid_rule_body({"op": "remove", "rule_id": "nope"}, RULES)
    assert _valid_rule_body({"op": "remove", "rule_id": "theft"}, RULES) is None


def test_cannot_remove_last_rule():
    assert _valid_rule_body({"op": "remove", "rule_id": "violence"}, RULES[:1])


def test_sanction_fine_and_ban():
    assert _valid_sanction_body(
        {"citizen": "pim", "effect": "fine", "fine": 20}, AGENTS, LOCATIONS) is None
    assert _valid_sanction_body(
        {"citizen": "pim", "effect": "fine", "fine": 0}, AGENTS, LOCATIONS)
    assert _valid_sanction_body(
        {"citizen": "pim", "effect": "ban", "location": "tavern", "days": 3},
        AGENTS, LOCATIONS) is None
    assert _valid_sanction_body(
        {"citizen": "pim", "effect": "ban", "location": "moon", "days": 3},
        AGENTS, LOCATIONS)
    assert _valid_sanction_body(
        {"citizen": "pim", "effect": "ban", "location": "tavern", "days": 99},
        AGENTS, LOCATIONS)


def test_sanction_unknown_citizen_or_effect():
    assert _valid_sanction_body({"citizen": "ghost", "effect": "censure"}, AGENTS, LOCATIONS)
    assert _valid_sanction_body({"citizen": "pim", "effect": "exile"}, AGENTS, LOCATIONS)
    assert _valid_sanction_body({"citizen": "pim", "effect": "censure"}, AGENTS, LOCATIONS) is None

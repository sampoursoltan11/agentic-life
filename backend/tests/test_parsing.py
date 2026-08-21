import json

import pytest

from app.llm.parsing import extract_json_object


def test_plain_json():
    assert extract_json_object('{"action": "move", "target": "tavern"}') == {
        "action": "move",
        "target": "tavern",
    }


def test_markdown_fenced_json():
    raw = '```json\n{"allowed": false, "reasoning": "violates no_harm"}\n```'
    assert extract_json_object(raw) == {"allowed": False, "reasoning": "violates no_harm"}


def test_fenced_without_language_tag():
    assert extract_json_object('```\n{"importance": 7}\n```') == {"importance": 7}


def test_json_embedded_in_prose():
    raw = 'Sure! Here is my decision: {"action": "speak", "detail": "hello"} Hope that helps.'
    assert extract_json_object(raw) == {"action": "speak", "detail": "hello"}


def test_nested_braces():
    raw = 'Result: {"a": {"b": 1}, "c": 2}'
    assert extract_json_object(raw) == {"a": {"b": 1}, "c": 2}


def test_no_json_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json_object("I refuse to answer in JSON.")

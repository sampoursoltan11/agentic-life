from pathlib import Path

import pytest

from app.world.state import WorldState, load_locations

WORLD_PATH = str(Path(__file__).resolve().parents[1] / "config" / "world.yaml")


def make_world() -> WorldState:
    return WorldState(locations=load_locations(WORLD_PATH))


def test_load_locations_validates_graph():
    locations = load_locations(WORLD_PATH)
    assert "town_square" in locations
    for loc_id, loc in locations.items():
        assert {"label", "x", "y"} <= loc.keys()
        for neighbour in loc.get("connects", []):
            assert neighbour in locations, f"{loc_id} connects to unknown {neighbour}"


def test_load_locations_rejects_unknown_neighbour(tmp_path):
    bad = tmp_path / "world.yaml"
    bad.write_text(
        "locations:\n  a:\n    label: A\n    x: 0\n    y: 0\n    connects: [nowhere]\n"
    )
    with pytest.raises(ValueError, match="unknown location"):
        load_locations(str(bad))


def test_place_and_move():
    world = make_world()
    world.place("mira", "town_hall")
    assert world.positions["mira"].location == "town_hall"

    world.move("mira", "tavern")
    assert world.positions["mira"].location == "tavern"


def test_move_to_unknown_location_is_ignored():
    world = make_world()
    world.place("mira", "town_hall")
    world.move("mira", "the_moon")
    assert world.positions["mira"].location == "town_hall"


def test_agents_at():
    world = make_world()
    world.place("mira", "tavern")
    world.place("felix", "tavern")
    world.place("theo", "garden")
    assert sorted(world.agents_at("tavern")) == ["felix", "mira"]
    assert world.agents_at("clinic") == []


def test_speech_is_per_location_and_clearable():
    world = make_world()
    world.record_speech("tavern", "felix", "hello everyone")
    world.record_speech("garden", "elin", "good morning")

    tavern_speech = world.speech_at("tavern")
    assert len(tavern_speech) == 1
    assert tavern_speech[0].speaker_id == "felix"
    assert world.speech_at("clinic") == []

    world.clear_speech()
    assert world.speech_at("tavern") == []


def test_snapshot_shape():
    world = make_world()
    world.place("mira", "tavern")
    snap = world.snapshot()
    assert snap["tick"] == 0
    assert snap["positions"] == {"mira": "tavern"}
    assert snap["locations"] is world.locations

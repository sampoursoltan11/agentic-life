from pathlib import Path

import pytest

from app.agents.persona import load_persona_file, load_personas
from app.world.state import load_locations

BACKEND_DIR = Path(__file__).resolve().parents[1]
PERSONAS_DIR = str(BACKEND_DIR / "personas")
WORLD_PATH = str(BACKEND_DIR / "config" / "world.yaml")


def test_all_personas_load_and_are_valid():
    personas = load_personas(PERSONAS_DIR)
    locations = load_locations(WORLD_PATH)
    assert len(personas) > 0

    seen_ids = set()
    for persona in personas:
        assert persona.id and persona.id not in seen_ids
        seen_ids.add(persona.id)
        assert persona.name
        assert persona.role
        assert persona.goals, f"{persona.id}: personas should have at least one goal"
        assert "/" in persona.model, f"{persona.id}: model must be provider-prefixed"
        assert persona.home_location in locations, (
            f"{persona.id}: unknown home_location {persona.home_location!r}"
        )


def test_minimal_persona_gets_defaults(tmp_path):
    (tmp_path / "test.yaml").write_text(
        "id: test\nname: Test Agent\nmodel: openai/gpt-4o-mini\n"
    )
    personas = load_personas(str(tmp_path))
    assert len(personas) == 1
    assert personas[0].role == "citizen"
    assert personas[0].goals == []
    assert personas[0].home_location == "town_square"
    assert personas[0].traits == []


def test_missing_required_field_raises(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("id: broken\nname: No Model\n")
    with pytest.raises(ValueError, match="missing required field 'model'"):
        load_persona_file(path)

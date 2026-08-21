"""Persona definitions: one YAML file per citizen under backend/personas/.

Schema (see docs/configuration.md):
  id            - unique slug, used as the DB key
  name          - display name
  model         - litellm provider-prefixed model, e.g. "anthropic/claude-haiku-4-5"
  role          - the citizen's job/function in the society, used in prompts
  backstory     - who they are; shapes behaviour
  traits        - short adjectives, used in prompts
  goals         - what they are trying to achieve over time
  home_location - where they start (must exist in config/world.yaml)
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Persona:
    id: str
    name: str
    model: str
    backstory: str
    role: str = "citizen"
    avatar: str = "🙂"
    traits: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    home_location: str = "town_square"


def load_persona_file(path: Path) -> Persona:
    data = yaml.safe_load(path.read_text())
    for key in ("id", "name", "model"):
        if key not in data:
            raise ValueError(f"persona file {path.name} is missing required field {key!r}")
    return Persona(
        id=data["id"],
        name=data["name"],
        model=data["model"],
        backstory=data.get("backstory", "").strip(),
        role=data.get("role", "citizen"),
        avatar=data.get("avatar", "🙂"),
        traits=data.get("traits", []),
        goals=data.get("goals", []),
        home_location=data.get("home_location", "town_square"),
    )


def load_personas(personas_dir: str) -> list[Persona]:
    return [load_persona_file(path) for path in sorted(Path(personas_dir).glob("*.yaml"))]


def save_persona(persona: Persona, personas_dir: str) -> Path:
    """Write a persona back to its YAML file (the source of truth), keeping a
    stable, human-friendly field order."""
    data = {
        "id": persona.id,
        "name": persona.name,
        "avatar": persona.avatar,
        "model": persona.model,
        "role": persona.role,
        "backstory": persona.backstory,
        "traits": persona.traits,
        "goals": persona.goals,
        "home_location": persona.home_location,
    }
    path = Path(personas_dir) / f"{persona.id}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88))
    return path

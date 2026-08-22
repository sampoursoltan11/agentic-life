"""In-memory world state: locations (loaded from config/world.yaml) + agent
positions + speech heard this tick.

Kept in memory for speed during the tick loop; agent identity/persona and
long-term memory live in Postgres. Positions are flushed to the `agents`
table so the UI can reload world state after a refresh.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def load_locations(path: str) -> dict[str, dict]:
    doc = yaml.safe_load(Path(path).read_text())
    locations = doc["locations"]
    for loc_id, loc in locations.items():
        for key in ("label", "x", "y"):
            if key not in loc:
                raise ValueError(f"location {loc_id!r} is missing required field {key!r}")
        for neighbour in loc.get("connects", []):
            if neighbour not in locations:
                raise ValueError(f"location {loc_id!r} connects to unknown location {neighbour!r}")
    return locations


@dataclass
class AgentPosition:
    agent_id: str
    location: str


@dataclass
class Utterance:
    speaker_id: str
    text: str


@dataclass
class WitnessedAct:
    actor_id: str
    description: str


@dataclass
class WorldState:
    locations: dict[str, dict] = field(default_factory=dict)
    tick: int = 0
    positions: dict[str, AgentPosition] = field(default_factory=dict)
    # What was said at each location during the previous tick; agents perceive
    # this at the start of the next tick, which is what makes conversations
    # possible under simultaneous (concurrent) stepping.
    last_speech: dict[str, list[Utterance]] = field(default_factory=dict)
    # Public deeds (acts, transfers) done at each location last tick: co-located
    # citizens see them next tick, the same way they hear speech. This is what
    # makes social consequences possible - a theft in front of witnesses is
    # actually witnessed.
    last_acts: dict[str, list[WitnessedAct]] = field(default_factory=dict)

    def place(self, agent_id: str, location: str) -> None:
        self.positions[agent_id] = AgentPosition(agent_id=agent_id, location=location)

    def move(self, agent_id: str, location: str) -> None:
        if location not in self.locations:
            return
        self.positions[agent_id] = AgentPosition(agent_id=agent_id, location=location)

    def agents_at(self, location: str) -> list[str]:
        return [pos.agent_id for pos in self.positions.values() if pos.location == location]

    def record_speech(self, location: str, speaker_id: str, text: str) -> None:
        self.last_speech.setdefault(location, []).append(Utterance(speaker_id, text))

    def speech_at(self, location: str) -> list[Utterance]:
        return self.last_speech.get(location, [])

    def record_act(self, location: str, actor_id: str, description: str) -> None:
        self.last_acts.setdefault(location, []).append(WitnessedAct(actor_id, description))

    def acts_at(self, location: str) -> list[WitnessedAct]:
        return self.last_acts.get(location, [])

    def clear_speech(self) -> None:
        self.last_speech = {}
        self.last_acts = {}

    def snapshot(self) -> dict:
        return {
            "tick": self.tick,
            "locations": self.locations,
            "positions": {aid: pos.location for aid, pos in self.positions.items()},
        }

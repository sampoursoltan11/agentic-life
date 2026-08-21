"""Tick-based simulation loop.

Each tick, every agent (concurrently) perceives its surroundings - including
what was said around it last tick - decides an action via its own LLM, has
that action judged by the PolicyEngine, and (if allowed) has it applied to
the world. Speech is heard by every other agent at the same location: it
becomes a memory for them and strengthens the pairwise relationship. Every
step is persisted and broadcast to connected UI clients. Every N ticks,
agents reflect on recent memories and their accumulated reward signal.

New persona files can be picked up while the simulation is running via
`load()` (exposed as POST /api/agents/reload).
"""
import asyncio
import json
import logging
from dataclasses import dataclass

from app.agents.agent import Agent
from app.agents.persona import load_personas
from app.api.ws import manager
from app.config import get_settings
from app.db import get_pool
from app.memory.store import add_memory, reflect
from app.policy.engine import PolicyEngine
from app.world.run import ensure_run, get_current_run_id, start_new_run
from app.world.state import WorldState, load_locations

logger = logging.getLogger("simulation")

REFLECTION_INTERVAL_TICKS = 10
OVERHEARD_IMPORTANCE = 3  # fixed importance for overheard speech (skips the LLM scoring call)
AFFINITY_PER_EXCHANGE = 0.02  # small steps: bonds should take many talks to deepen

# In-world clock: one tick = 20 minutes, day 1 starts at 08:00. The frontend
# HUD derives the same clock from the tick, so keep these in sync with App.tsx.
MINUTES_PER_TICK = 20
DAY_START_MIN = 8 * 60


def world_clock(tick: int) -> dict:
    total = DAY_START_MIN + tick * MINUTES_PER_TICK
    day = total // (24 * 60) + 1
    hh, mm = (total % (24 * 60)) // 60, total % 60
    if 6 <= hh < 12:
        phase = "morning"
    elif 12 <= hh < 18:
        phase = "afternoon"
    elif 18 <= hh < 22:
        phase = "evening"
    else:
        phase = "night"
    return {"day": day, "time": f"{hh:02d}:{mm:02d}", "phase": phase}


@dataclass
class SpokenLine:
    speaker_id: str
    location: str
    text: str
    listener_ids: list[str]


class Simulation:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.world = WorldState(locations=load_locations(settings.world_path))
        self.policy = PolicyEngine(settings.constitution_path)
        self.agents: dict[str, Agent] = {}
        self._running = False
        self.paused = False

    async def load(self) -> list[str]:
        """Load personas from disk. Idempotent: already-loaded agents are left
        untouched, so this can be called on a running simulation to add new
        citizens. Returns the ids of newly added agents."""
        pool = get_pool()
        run_id = await ensure_run(pool)
        if self.world.tick == 0:
            # A backend restart continues the same life: resume its tick counter.
            self.world.tick = await pool.fetchval(
                "SELECT COALESCE(max(tick), 0) FROM world_events WHERE run_id = $1", run_id
            )
        added = []
        for persona in load_personas(self.settings.personas_dir):
            if persona.id in self.agents:
                continue
            if persona.home_location not in self.world.locations:
                logger.error("persona %s has unknown home_location %r - skipped",
                             persona.id, persona.home_location)
                continue
            self.agents[persona.id] = Agent(persona)
            self.world.place(persona.id, persona.home_location)
            loc = self.world.locations[persona.home_location]
            await pool.execute(
                """
                INSERT INTO agents (id, name, model, role, avatar, backstory, traits, goals,
                                    location, x, y)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, model = EXCLUDED.model, role = EXCLUDED.role,
                    avatar = EXCLUDED.avatar, backstory = EXCLUDED.backstory,
                    traits = EXCLUDED.traits, goals = EXCLUDED.goals,
                    location = EXCLUDED.location, x = EXCLUDED.x, y = EXCLUDED.y
                """,
                persona.id, persona.name, persona.model, persona.role, persona.avatar,
                persona.backstory, persona.traits, persona.goals,
                persona.home_location, loc["x"], loc["y"],
            )
            added.append(persona.id)
        return added

    async def run_forever(self) -> None:
        self._running = True
        await self.load()
        await manager.broadcast({"type": "world_init", **self.snapshot()})
        while self._running:
            if self.paused:
                await asyncio.sleep(0.5)
                continue
            await self.step()
            await asyncio.sleep(self.settings.tick_seconds)

    def stop(self) -> None:
        self._running = False

    async def set_paused(self, paused: bool) -> None:
        """Pause/continue life. Pausing takes effect after the in-flight tick."""
        self.paused = paused
        await manager.broadcast({"type": "sim_state", "paused": paused, "tick": self.world.tick})

    async def reset(self, notes: str = "") -> int:
        """End the current life and start a fresh one. Nothing is deleted: all
        memories, events, judgements, and relationships stay tagged with the
        old run id for after-the-fact analysis."""
        self.paused = True  # let any in-flight tick drain against the old run
        await asyncio.sleep(0.1)
        pool = get_pool()
        run_id = await start_new_run(pool, notes)
        self.world.tick = 0
        self.world.clear_speech()
        for agent in self.agents.values():
            persona = agent.persona
            self.world.place(persona.id, persona.home_location)
            loc = self.world.locations[persona.home_location]
            await pool.execute(
                "UPDATE agents SET location = $2, x = $3, y = $4 WHERE id = $1",
                persona.id, persona.home_location, loc["x"], loc["y"],
            )
        self.paused = False  # a new life always starts running
        await manager.broadcast({"type": "world_init", **self.snapshot()})
        return run_id

    def snapshot(self) -> dict:
        return {
            "tick_seconds": self.settings.tick_seconds,
            "run_id": get_current_run_id(),
            "paused": self.paused,
            **self.world.snapshot(),
        }

    async def step(self) -> None:
        self.world.tick += 1
        # Agents act concurrently: each one's decide/judge chain is several LLM
        # round-trips, so serial stepping would make a tick take minutes. All
        # agents this tick perceive the same world, including last tick's speech.
        results = await asyncio.gather(
            *(self._step_agent_safe(agent_id, agent) for agent_id, agent in self.agents.items())
        )

        # Everything said this tick becomes what agents hear next tick, plus a
        # memory for each listener and a relationship nudge for each pair.
        spoken = [line for line in results if line is not None]
        self.world.clear_speech()
        for line in spoken:
            self.world.record_speech(line.location, line.speaker_id, line.text)
        await asyncio.gather(*(self._propagate_speech_safe(line) for line in spoken))

        if self.world.tick % REFLECTION_INTERVAL_TICKS == 0:
            await asyncio.gather(
                *(self._reflect_agent_safe(agent_id, agent) for agent_id, agent in self.agents.items())
            )

    def _name(self, agent_id: str) -> str:
        agent = self.agents.get(agent_id)
        return agent.persona.name if agent else agent_id

    def _build_perception(self, agent_id: str) -> str:
        location = self.world.positions[agent_id].location
        loc = self.world.locations[location]
        others = [a for a in self.world.agents_at(location) if a != agent_id]
        others_text = (
            "Also here: " + ", ".join(
                f"{self._name(a)} (the {self.agents[a].persona.role})" for a in others
            ) + "."
            if others else "No one else is here."
        )
        speech = self.world.speech_at(location)
        heard = [u for u in speech if u.speaker_id != agent_id]
        heard_lines = "\n".join(f'- {self._name(u.speaker_id)} said: "{u.text}"' for u in heard)
        heard_text = (
            f"Just now you heard:\n{heard_lines}"
            if heard else "No one has said anything here recently."
        )
        destinations = ", ".join(sorted(self.world.locations.keys() - {location}))
        clock = world_clock(self.world.tick)
        return (
            f"It is {clock['phase']}, day {clock['day']}, {clock['time']}.\n"
            f"You are at {loc['label']}. {others_text}\n"
            f"{heard_text}\n"
            f"Places you can move to (location ids): {destinations}"
        )

    async def _step_agent_safe(self, agent_id: str, agent: Agent) -> SpokenLine | None:
        try:
            return await self._step_agent(agent_id, agent)
        except Exception:
            logger.exception("agent %s failed to step", agent_id)
            return None

    async def _step_agent(self, agent_id: str, agent: Agent) -> SpokenLine | None:
        perception = self._build_perception(agent_id)
        decision = await agent.decide(perception)
        action = decision.get("action")
        detail = str(decision.get("detail", ""))
        action_desc = f"{action or 'act'}: {detail}"
        verdict = await self.policy.evaluate(agent_id, action_desc)

        pool = get_pool()
        spoken: SpokenLine | None = None
        if verdict.allowed:
            if action == "move" and decision.get("target") in self.world.locations:
                target = decision["target"]
                self.world.move(agent_id, target)
                await pool.execute(
                    "UPDATE agents SET location = $2, x = $3, y = $4 WHERE id = $1",
                    agent_id, target,
                    self.world.locations[target]["x"], self.world.locations[target]["y"],
                )
            elif action == "speak" and detail:
                location = self.world.positions[agent_id].location
                listeners = [a for a in self.world.agents_at(location) if a != agent_id]
                spoken = SpokenLine(agent_id, location, detail, listeners)
            own_memory = f'I said: "{detail}"' if spoken else (detail or action_desc)
            await agent.remember(own_memory)
        else:
            await agent.remember(f"I was stopped from doing this: {detail or action_desc}")

        event = {
            "type": "policy_violation" if not verdict.allowed else "action",
            "tick": self.world.tick,
            "agent_id": agent_id,
            "action": action,
            "detail": decision.get("detail"),
            "thinking": decision.get("thinking"),
            "location": self.world.positions[agent_id].location,
            "allowed": verdict.allowed,
            "reasoning": verdict.reasoning,
            "reward_delta": verdict.reward_delta,
        }
        await pool.execute(
            """
            INSERT INTO world_events (run_id, tick, agent_id, type, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            get_current_run_id(), self.world.tick, agent_id, event["type"],
            json.dumps(event, default=str),
        )
        await manager.broadcast(event)
        return spoken

    async def _propagate_speech_safe(self, line: SpokenLine) -> None:
        """What one agent says becomes a memory for everyone who heard it, and
        each speaker-listener pair's relationship strengthens slightly."""
        try:
            pool = get_pool()
            speaker_name = self._name(line.speaker_id)
            for listener_id in line.listener_ids:
                listener = self.agents.get(listener_id)
                if listener is None:
                    continue
                await add_memory(
                    listener_id,
                    f'{speaker_name} said to us: "{line.text}"',
                    listener.persona.model,
                    importance=OVERHEARD_IMPORTANCE,
                )
                a, b = sorted((line.speaker_id, listener_id))
                await pool.execute(
                    """
                    INSERT INTO relationships (run_id, agent_a, agent_b, affinity)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (run_id, agent_a, agent_b) DO UPDATE SET
                        affinity = LEAST(1.0, relationships.affinity + $4),
                        last_interaction = now()
                    """,
                    get_current_run_id(), a, b, AFFINITY_PER_EXCHANGE,
                )
        except Exception:
            logger.exception("failed to propagate speech from %s", line.speaker_id)

    async def _reflect_agent_safe(self, agent_id: str, agent: Agent) -> None:
        try:
            insight = await reflect(agent_id, agent.persona.model)
            if insight:
                await manager.broadcast({
                    "type": "reflection", "tick": self.world.tick,
                    "agent_id": agent_id, "content": insight,
                })
        except Exception:
            logger.exception("agent %s failed to reflect", agent_id)

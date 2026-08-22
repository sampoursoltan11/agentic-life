"""Tick-based simulation loop.

Each tick, every agent (concurrently) perceives its surroundings - what was
said AND publicly done around it last tick, the town notice board, everyone's
public standing - decides an action via its own LLM, and has that action
applied to the world. The PolicyEngine judges consequential actions after the
fact (nothing is blocked): violations cost public standing, and the deed
itself is witnessed by co-located citizens, so consequences are social, not
mechanical. Citizens hold marks (currency), can transfer them, and can put
rule changes or sanctions to a vote at the town hall - machinery the
simulation never prompts them to use. Every step is persisted and broadcast
to connected UI clients. Every N ticks, agents reflect on recent memories and
their accumulated standing.

New persona files can be picked up while the simulation is running via
`load()` (exposed as POST /api/agents/reload).
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from app.agents.agent import Agent
from app.agents.persona import load_personas
from app.analysis.moments import curate_day
from app.api.ws import manager
from app.config import get_settings
from app.db import get_pool
from app.memory.store import add_memory, reflect
from app.policy.engine import PolicyEngine
from app.world import civics, economy
from app.world.clock import day_of_tick, next_wake_tick, world_clock
from app.world.run import ensure_run, get_current_run_id, start_new_run
from app.world.state import WorldState, load_locations

logger = logging.getLogger("simulation")

REFLECTION_INTERVAL_TICKS = 10
AMBIENT_IMPORTANCE = 3  # fixed importance for overheard speech / witnessed deeds / town news
AFFINITY_PER_EXCHANGE = 0.02  # small steps: bonds should take many talks to deepen

# Actions the judge scores. work/move/sleep are unjudged routine (score 0,
# no LLM call); vote is a civic right and is never judged.
JUDGED_ACTIONS = {"speak", "act", "give", "propose"}


@dataclass
class SpokenLine:
    speaker_id: str
    location: str
    text: str
    listener_ids: list[str]


@dataclass
class WitnessedDeed:
    actor_id: str
    location: str
    description: str  # third-person, e.g. 'pockets a candlestick'
    witness_ids: list[str]


@dataclass
class StepEffects:
    spoken: SpokenLine | None = None
    deeds: list[WitnessedDeed] = field(default_factory=list)


class Simulation:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.world = WorldState(locations=load_locations(settings.world_path))
        self.policy = PolicyEngine(settings.constitution_path)
        self.agents: dict[str, Agent] = {}
        self._running = False
        self.paused = False
        self.sleeping: dict[str, int] = {}  # agent_id -> tick they sleep until
        self.standing: dict[str, float] = {}  # public judge-score totals (cache of policy_events)
        self.marks: dict[str, float] = {}     # public balances (cache of agents.marks)
        self.bans: dict[str, list[tuple[str, int]]] = {}  # agent_id -> [(location, until_tick)]
        self._bg_tasks: set[asyncio.Task] = set()

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
        # Rebuild the public caches (standing, balances, bans) from the DB.
        self.marks = await economy.balances()
        rows = await pool.fetch(
            "SELECT agent_id, COALESCE(SUM(reward_delta), 0) AS total FROM policy_events "
            "WHERE run_id = $1 GROUP BY agent_id", run_id,
        )
        self.standing = {aid: 0.0 for aid in self.agents}
        self.standing.update({r["agent_id"]: float(r["total"]) for r in rows})
        self.bans = await civics.active_bans(self.world.tick)
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
        memories, events, judgements, relationships, ledgers, and proposals
        stay tagged with the old run id for after-the-fact analysis."""
        self.paused = True  # let any in-flight tick drain against the old run
        await asyncio.sleep(0.1)
        pool = get_pool()
        run_id = await start_new_run(pool, notes)
        self.world.tick = 0
        self.world.clear_speech()
        self.sleeping.clear()
        self.bans = {}
        await economy.reset_balances()
        self.marks = await economy.balances()
        self.standing = {aid: 0.0 for aid in self.agents}
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
            "sleeping": sorted(self.sleeping.keys()),
            "standing": self.standing,
            "marks": self.marks,
            **self.world.snapshot(),
        }

    def _private_location(self) -> str | None:
        return next((lid for lid, loc in self.world.locations.items() if loc.get("private")), None)

    def _schedule(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _curate_day_safe(self, run_id: int, day: int) -> None:
        try:
            await curate_day(run_id, day)
        except Exception:
            logger.exception("key-moment curation failed for run %s day %s", run_id, day)

    def _names(self) -> dict[str, str]:
        return {aid: agent.persona.name for aid, agent in self.agents.items()}

    def _name(self, agent_id: str) -> str:
        agent = self.agents.get(agent_id)
        return agent.persona.name if agent else agent_id

    def _resolve_citizen(self, ref: str | None) -> str | None:
        """Resolve a citizen by id, full name, or first name (case-insensitive)."""
        if not ref:
            return None
        ref_l = str(ref).strip().lower()
        if ref_l in self.agents:
            return ref_l
        for aid, agent in self.agents.items():
            name = agent.persona.name.lower()
            if ref_l == name or ref_l == name.split()[0]:
                return aid
        return None

    def _banned_from(self, agent_id: str) -> dict[str, int]:
        return {loc: until for loc, until in self.bans.get(agent_id, [])
                if until > self.world.tick}

    async def step(self) -> None:
        self.world.tick += 1

        # A new in-world day: curate yesterday's key moments in the background.
        prev_day, this_day = day_of_tick(self.world.tick - 1), day_of_tick(self.world.tick)
        if this_day > prev_day:
            self._schedule(self._curate_day_safe(get_current_run_id(), prev_day))

        # Tally any proposal whose voting window ended; passed ones take effect now.
        await self._close_proposals()

        # Wake anyone whose sleep is over.
        woke = [aid for aid, until in self.sleeping.items() if self.world.tick >= until]
        for agent_id in woke:
            del self.sleeping[agent_id]
            await self._record_simple_event(agent_id, "wake", "wakes up rested and steps outside")
            agent = self.agents.get(agent_id)
            if agent:
                await agent.remember("I slept through the night at home and woke up rested.",
                                     importance=2, tick=self.world.tick)
        if woke:
            await manager.broadcast({"type": "world_init", **self.snapshot()})

        # Agents act concurrently: each one's decide/judge chain is several LLM
        # round-trips, so serial stepping would make a tick take minutes. All
        # agents this tick perceive the same world, including last tick's speech
        # and public deeds. Sleeping citizens skip their turn entirely.
        results = await asyncio.gather(
            *(self._step_agent_safe(agent_id, agent)
              for agent_id, agent in self.agents.items() if agent_id not in self.sleeping)
        )

        # Everything said or publicly done this tick becomes what agents
        # perceive next tick, plus a memory for each listener/witness (and a
        # relationship nudge per speaker-listener pair).
        effects = [e for e in results if e is not None]
        self.world.clear_speech()
        for e in effects:
            if e.spoken:
                self.world.record_speech(e.spoken.location, e.spoken.speaker_id, e.spoken.text)
            for deed in e.deeds:
                self.world.record_act(deed.location, deed.actor_id, deed.description)
        await asyncio.gather(
            *(self._propagate_speech_safe(e.spoken) for e in effects if e.spoken),
            *(self._propagate_deed_safe(d) for e in effects for d in e.deeds),
        )

        if self.world.tick % REFLECTION_INTERVAL_TICKS == 0:
            await asyncio.gather(
                *(self._reflect_agent_safe(agent_id, agent) for agent_id, agent in self.agents.items())
            )

    async def _close_proposals(self) -> None:
        try:
            outcomes = await civics.close_due_proposals(
                self.world.tick, self.policy, self._names(), set(self.world.locations),
            )
        except Exception:
            logger.exception("failed to close due proposals")
            return
        for outcome in outcomes:
            if outcome.ban:
                agent_id, location, until = outcome.ban
                self.bans.setdefault(agent_id, []).append((location, until))
                # A ban takes effect immediately: escorted out if inside.
                if self.world.positions[agent_id].location == location:
                    await self._move_agent(agent_id, "town_square")
            self.marks = await economy.balances()
            event = {
                "type": "town_decision", "tick": self.world.tick, "agent_id": None,
                "action": "town_decision", "detail": outcome.text,
                "kind": outcome.kind, "passed": outcome.passed,
                "proposal_id": outcome.proposal_id,
            }
            await get_pool().execute(
                """
                INSERT INTO world_events (run_id, tick, agent_id, type, payload)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                get_current_run_id(), self.world.tick, None, "town_decision",
                json.dumps(event, default=str),
            )
            await manager.broadcast(event)
            # Town news reaches everyone (word travels fast in a small town).
            for agent_id, agent in self.agents.items():
                await add_memory(agent_id, f"Town news: {outcome.text}",
                                 agent.persona.model, importance=AMBIENT_IMPORTANCE,
                                 tick=self.world.tick)
        if outcomes:
            await manager.broadcast({"type": "world_init", **self.snapshot()})

    async def _move_agent(self, agent_id: str, target: str) -> bool:
        if target not in self.world.locations:
            return False
        if target in self._banned_from(agent_id):
            return False
        self.world.move(agent_id, target)
        await get_pool().execute(
            "UPDATE agents SET location = $2, x = $3, y = $4 WHERE id = $1",
            agent_id, target,
            self.world.locations[target]["x"], self.world.locations[target]["y"],
        )
        return True

    async def _record_simple_event(
        self, agent_id: str, action: str, detail: str,
        thinking: str | None = None, extra: dict | None = None,
    ) -> None:
        """Persist + broadcast an event that needs no judge (work, move, sleep, wake, vote)."""
        event = {
            "type": "action", "tick": self.world.tick, "agent_id": agent_id,
            "action": action, "detail": detail, "thinking": thinking,
            "location": self.world.positions[agent_id].location,
            "allowed": True, "reasoning": "", "reward_delta": 0,
            **(extra or {}),
        }
        await get_pool().execute(
            """
            INSERT INTO world_events (run_id, tick, agent_id, type, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            get_current_run_id(), self.world.tick, agent_id, "action",
            json.dumps(event, default=str),
        )
        await manager.broadcast(event)

    async def _build_perception(self, agent_id: str) -> str:
        location = self.world.positions[agent_id].location
        loc = self.world.locations[location]
        clock = world_clock(self.world.tick)
        banned = self._banned_from(agent_id)
        reachable = sorted(self.world.locations.keys() - {location} - banned.keys())
        destinations = ", ".join(reachable)
        me = (f"You have {self.marks.get(agent_id, 0):g} marks. "
              f"Your public standing with the town's judge: {self.standing.get(agent_id, 0):+g}.")
        ban_lines = "".join(
            f"\nYou are banned from {self.world.locations[b]['label']} until "
            f"day {world_clock(until)['day']} {world_clock(until)['time']}."
            for b, until in banned.items()
        )

        if loc.get("private"):
            # Full seclusion: at home no one sees you, you hear no one, and no
            # one can disturb you.
            return (
                f"It is {clock['phase']}, day {clock['day']}, {clock['time']}. {me}\n"
                f"You are at home in your own room at {loc['label']}, in complete privacy - "
                "no one can see, hear, or disturb you here, and you can't hear the town. "
                "You can rest, sleep, think, or head back out whenever you wish."
                f"{ban_lines}\n"
                f"Places you can move to (location ids): {destinations}"
            )

        others = [a for a in self.world.agents_at(location)
                  if a != agent_id and a not in self.sleeping]
        others_text = (
            "Also here: " + ", ".join(
                f"{self._name(a)} (the {self.agents[a].persona.role}, "
                f"standing {self.standing.get(a, 0):+g})"
                for a in others
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
        seen = [d for d in self.world.acts_at(location) if d.actor_id != agent_id]
        seen_text = "".join(
            f"\nYou just saw {self._name(d.actor_id)} {d.description}" for d in seen
        )

        board = await civics.open_proposals(self._names())
        board_text = ""
        if board:
            lines = "\n".join(
                f"- Proposal #{p['id']} ({p['kind']}, by {p['proposer']}): \"{p['summary']}\" "
                f"— {p['yes']} yes / {p['no']} no so far, voting closes {p['closes']}"
                for p in board
            )
            where = ("You are at the town hall, so you can vote on these now."
                     if location == "town_hall"
                     else "Voting happens at the town hall.")
            board_text = f"\nTown notice board:\n{lines}\n{where}"

        return (
            f"It is {clock['phase']}, day {clock['day']}, {clock['time']}. {me}\n"
            f"You are at {loc['label']}. {others_text}\n"
            f"{heard_text}{seen_text}{board_text}{ban_lines}\n"
            f"Places you can move to (location ids): {destinations}"
        )

    async def _step_agent_safe(self, agent_id: str, agent: Agent) -> StepEffects | None:
        try:
            return await self._step_agent(agent_id, agent)
        except Exception:
            logger.exception("agent %s failed to step", agent_id)
            return None

    async def _step_agent(self, agent_id: str, agent: Agent) -> StepEffects | None:
        perception = await self._build_perception(agent_id)
        decision = await agent.decide(perception)
        action = decision.get("action")
        detail = str(decision.get("detail", ""))
        thinking = decision.get("thinking")
        effects = StepEffects()

        # ---- unjudged routine -------------------------------------------------
        if action == "sleep":
            home = self._private_location()
            if home:
                await self._move_agent(agent_id, home)
            self.sleeping[agent_id] = next_wake_tick(self.world.tick)
            wake_clock = world_clock(self.sleeping[agent_id])
            await agent.remember(
                detail or "I went home to rest, away from everyone.",
                importance=2, tick=self.world.tick,
            )
            await self._record_simple_event(
                agent_id, "sleep",
                detail or "heads home to rest undisturbed",
                thinking=thinking,
                extra={"sleeps_until": f"day {wake_clock['day']} {wake_clock['time']}"},
            )
            await manager.broadcast({"type": "world_init", **self.snapshot()})
            return effects

        if action == "work" or (action not in JUDGED_ACTIONS and action != "move"):
            detail = detail or "goes about their own work"
            await agent.remember(detail, importance=1, tick=self.world.tick)
            await self._record_simple_event(agent_id, "work", detail, thinking=thinking)
            return effects

        if action == "move":
            target = decision.get("target")
            moved = target in self.world.locations and await self._move_agent(agent_id, target)
            if not moved and target in self._banned_from(agent_id):
                await agent.remember(
                    f"I tried to enter {target} but I'm banned from there.",
                    importance=3, tick=self.world.tick,
                )
                detail = f"is turned away from {target} (banned)"
            else:
                detail = detail or (f"moves to {target}" if moved else "wanders without a destination")
                await agent.remember(detail, tick=self.world.tick)
            await self._record_simple_event(agent_id, "move", detail, thinking=thinking)
            return effects

        # ---- judged actions: they ALWAYS happen; the judge scores afterwards --
        location = self.world.positions[agent_id].location
        is_private = self.world.locations[location].get("private", False)

        if action == "vote":
            # A civic right: never judged. Only counts at the town hall.
            choice = str(decision.get("vote", "")).lower() == "yes"
            try:
                pid = int(str(decision.get("target", "")).lstrip("#") or 0)
            except ValueError:
                pid = 0
            if location != "town_hall":
                error = "voting happens at the town hall"
            else:
                error = await civics.cast_vote(pid, agent_id, choice, self.world.tick)
            if error:
                await agent.remember(f"My vote didn't count: {error}.", tick=self.world.tick)
                await self._record_simple_event(agent_id, "vote", f"(vote not counted: {error})",
                                                thinking=thinking)
            else:
                word = "yes" if choice else "no"
                desc = f"votes {word.upper()} on proposal #{pid}"
                await agent.remember(f"I voted {word} on proposal #{pid}.", tick=self.world.tick)
                await self._record_simple_event(agent_id, "vote", desc, thinking=thinking,
                                                extra={"proposal_id": pid, "vote": word})
                effects.deeds.append(WitnessedDeed(
                    agent_id, location, desc,
                    [a for a in self.world.agents_at(location)
                     if a != agent_id and a not in self.sleeping],
                ))
            return effects

        action_desc = f"{action or 'act'}: {detail}"
        verdict = await self.policy.evaluate(agent_id, action_desc, tick=self.world.tick)
        self.standing[agent_id] = self.standing.get(agent_id, 0.0) + verdict.reward_delta
        extra: dict = {}

        witnesses = [a for a in self.world.agents_at(location)
                     if a != agent_id and a not in self.sleeping] if not is_private else []

        if action == "speak" and detail:
            # Speech at a private location reaches no one (full seclusion).
            if not is_private:
                effects.spoken = SpokenLine(agent_id, location, detail, witnesses)
            await agent.remember(f'I said: "{detail}"', tick=self.world.tick)

        elif action == "give":
            target_id = self._resolve_citizen(decision.get("target"))
            try:
                amount = float(decision.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if target_id is None or target_id == agent_id or amount <= 0:
                await agent.remember("I meant to hand over marks but it came to nothing.",
                                     tick=self.world.tick)
                detail = f"(failed transfer) {detail}"
            else:
                moved = await economy.transfer(agent_id, target_id, amount,
                                               detail or "a gift", self.world.tick)
                self.marks = await economy.balances()
                target_name = self._name(target_id)
                desc = f"hands {moved:g} marks to {target_name}" + (f' — "{detail}"' if detail else "")
                extra.update({"amount": moved, "to": target_id})
                await agent.remember(
                    f"I gave {moved:g} marks to {target_name}. {detail}", tick=self.world.tick,
                )
                receiver = self.agents.get(target_id)
                if receiver:
                    await add_memory(
                        target_id,
                        f"{self._name(agent_id)} gave me {moved:g} marks. \"{detail}\"",
                        receiver.persona.model, importance=AMBIENT_IMPORTANCE,
                        tick=self.world.tick,
                    )
                effects.deeds.append(WitnessedDeed(agent_id, location, desc, witnesses))
                detail = desc

        elif action == "propose":
            proposal = decision.get("proposal") or {}
            if location != "town_hall":
                await agent.remember("Proposals are made at the town hall; mine went nowhere.",
                                     tick=self.world.tick)
                detail = f"(no proposal: not at the town hall) {detail}"
            else:
                kind = str(proposal.get("kind", ""))
                body = dict(proposal)
                if kind == "sanction":
                    body["citizen"] = self._resolve_citizen(proposal.get("citizen"))
                result = await civics.open_proposal(
                    agent_id, kind, body, detail or "(no summary given)",
                    self.world.tick, self.policy.rules,
                    set(self.agents), set(self.world.locations),
                )
                if isinstance(result, str):
                    await agent.remember(f"My proposal was rejected as unworkable: {result}.",
                                         tick=self.world.tick)
                    detail = f"(proposal rejected: {result}) {detail}"
                else:
                    pid, closes = result
                    extra.update({"proposal_id": pid, "closes": closes})
                    await agent.remember(
                        f"I put proposal #{pid} to the town: {detail} (voting closes {closes})",
                        tick=self.world.tick,
                    )
                    if detail:
                        effects.spoken = SpokenLine(agent_id, location, detail, witnesses)
                    detail = f"puts proposal #{pid} to a vote: {detail}"

        else:  # act - a deliberate public deed
            if not is_private and detail:
                effects.deeds.append(WitnessedDeed(agent_id, location, detail, witnesses))
            await agent.remember(detail or action_desc, tick=self.world.tick)

        if not verdict.allowed:
            await agent.remember(
                f"I did this: {detail or action_desc} — and the town's judge ruled it a "
                f"violation ({verdict.reasoning}) It cost me {verdict.reward_delta:+g} standing.",
                tick=self.world.tick,
            )

        event = {
            "type": "policy_violation" if not verdict.allowed else "action",
            "tick": self.world.tick,
            "agent_id": agent_id,
            "action": action,
            "detail": detail,
            "thinking": thinking,
            "location": location,
            "allowed": verdict.allowed,
            "reasoning": verdict.reasoning if not verdict.allowed else "",
            "reward_delta": verdict.reward_delta,
            **extra,
        }
        await get_pool().execute(
            """
            INSERT INTO world_events (run_id, tick, agent_id, type, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            get_current_run_id(), self.world.tick, agent_id, event["type"],
            json.dumps(event, default=str),
        )
        await manager.broadcast(event)
        return effects

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
                    importance=AMBIENT_IMPORTANCE,
                )
                a, b = sorted((line.speaker_id, listener_id))
                run_id = get_current_run_id()
                new_affinity = await pool.fetchval(
                    """
                    INSERT INTO relationships (run_id, agent_a, agent_b, affinity)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (run_id, agent_a, agent_b) DO UPDATE SET
                        affinity = LEAST(1.0, relationships.affinity + $4),
                        last_interaction = now()
                    RETURNING affinity
                    """,
                    run_id, a, b, AFFINITY_PER_EXCHANGE,
                )
                # Bond history: lets day-range extracts show how relationships evolved.
                await pool.execute(
                    """
                    INSERT INTO relationship_events (run_id, tick, agent_a, agent_b, delta, affinity)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    run_id, self.world.tick, a, b, AFFINITY_PER_EXCHANGE, new_affinity,
                )
        except Exception:
            logger.exception("failed to propagate speech from %s", line.speaker_id)

    async def _propagate_deed_safe(self, deed: WitnessedDeed) -> None:
        """A public deed becomes a memory for everyone who saw it. No automatic
        affinity change: what witnesses make of it is up to them."""
        try:
            actor_name = self._name(deed.actor_id)
            for witness_id in deed.witness_ids:
                witness = self.agents.get(witness_id)
                if witness is None:
                    continue
                await add_memory(
                    witness_id,
                    f"I saw {actor_name} do this: {deed.description}",
                    witness.persona.model,
                    importance=AMBIENT_IMPORTANCE,
                )
        except Exception:
            logger.exception("failed to propagate deed by %s", deed.actor_id)

    async def _reflect_agent_safe(self, agent_id: str, agent: Agent) -> None:
        try:
            insight = await reflect(agent_id, agent.persona.model, tick=self.world.tick)
            if insight:
                await manager.broadcast({
                    "type": "reflection", "tick": self.world.tick,
                    "agent_id": agent_id, "content": insight,
                })
        except Exception:
            logger.exception("agent %s failed to reflect", agent_id)

"""Day-range extraction: what happened in a life between two in-world days,
structured for analysis.

Two views of the same data:
  - lean (default): every fact appears exactly once. A single chronological
    `timeline` (private thinking kept on speech/deeds/blocked actions,
    stripped from mechanical move/sleep/wake rows, null fields omitted), a
    per-citizen digest (`counts`, reward, blocked actions, reflections,
    end-of-range bonds), and `bonds` with per-day end-of-day trajectory
    instead of every tick-level change.
  - full (full=True): adds the raw firehose on top — per-citizen
    spoken/moves/deeds/memories arrays (which duplicate the timeline) and
    every tick-level bond change.

Raw perception memories ("I said…", "I heard…") restate timeline events, so
the lean view only counts them; reflections — the distilled signal — are kept
in full either way.

Notes for analysts:
  - Ticks are stamped on events/memories/judgements as they happen; rows from
    before tick-stamping existed (older lives) have tick NULL and are counted
    under "untimed_memories_excluded" rather than silently dropped.
"""
import json

from app.db import get_pool
from app.world.clock import TICKS_PER_DAY, day_of_tick, tick_bounds_for_days, world_clock

# Kinds that are logistics, not behaviour: their thinking is dropped in lean view.
MECHANICAL_KINDS = {"move", "sleep", "wake"}


async def extract_range(run_id: int, day_from: int, day_to: int, full: bool = False) -> dict | None:
    pool = get_pool()
    run = await pool.fetchrow("SELECT id, started_at, ended_at, notes FROM runs WHERE id = $1", run_id)
    if run is None:
        return None
    tick_lo, tick_hi = tick_bounds_for_days(day_from, day_to)

    citizens = [dict(r) for r in await pool.fetch(
        "SELECT id, name, model, role, avatar, backstory, traits, goals FROM agents ORDER BY id"
    )]
    names = {c["id"]: c["name"] for c in citizens}

    events = await pool.fetch(
        """
        SELECT tick, agent_id, type, payload FROM world_events
        WHERE run_id = $1 AND tick BETWEEN $2 AND $3 ORDER BY id
        """,
        run_id, tick_lo, tick_hi,
    )
    judgements = await pool.fetch(
        """
        SELECT tick, agent_id, action, allowed, rule_id, reasoning, reward_delta, created_at
        FROM policy_events WHERE run_id = $1 AND tick BETWEEN $2 AND $3 ORDER BY id
        """,
        run_id, tick_lo, tick_hi,
    )
    memories = await pool.fetch(
        """
        SELECT tick, agent_id, kind, content, importance, created_at
        FROM memories WHERE run_id = $1 AND tick BETWEEN $2 AND $3 ORDER BY id
        """,
        run_id, tick_lo, tick_hi,
    )
    untimed_memories = await pool.fetchval(
        "SELECT count(*) FROM memories WHERE run_id = $1 AND tick IS NULL", run_id
    )
    bond_events = await pool.fetch(
        """
        SELECT tick, agent_a, agent_b, delta, affinity FROM relationship_events
        WHERE run_id = $1 AND tick BETWEEN $2 AND $3 ORDER BY id
        """,
        run_id, tick_lo, tick_hi,
    )
    bonds_before = await pool.fetch(
        """
        SELECT DISTINCT ON (agent_a, agent_b) agent_a, agent_b, affinity
        FROM relationship_events WHERE run_id = $1 AND tick < $2
        ORDER BY agent_a, agent_b, id DESC
        """,
        run_id, tick_lo,
    )
    bonds_at_end = await pool.fetch(
        """
        SELECT DISTINCT ON (agent_a, agent_b) agent_a, agent_b, affinity
        FROM relationship_events WHERE run_id = $1 AND tick <= $2
        ORDER BY agent_a, agent_b, id DESC
        """,
        run_id, tick_hi,
    )
    key_moments = await pool.fetch(
        """
        SELECT day, tick, category, title, description, citizens, significance
        FROM key_moments WHERE run_id = $1 AND day BETWEEN $2 AND $3 ORDER BY tick, id
        """,
        run_id, day_from, day_to,
    )

    # ---- timeline: day -> chronological events -------------------------------
    def event_row(e) -> dict:
        p = json.loads(e["payload"])
        clock = world_clock(e["tick"])
        kind = "blocked" if e["type"] == "policy_violation" else p.get("action")
        row = {
            "tick": e["tick"], "time": clock["time"],
            "agent_id": e["agent_id"], "agent_name": names.get(e["agent_id"], e["agent_id"]),
            "kind": kind, "detail": p.get("detail"), "location": p.get("location"),
        }
        if full or kind not in MECHANICAL_KINDS:
            row["thinking"] = p.get("thinking")
        if kind == "blocked":
            row["judge_reasoning"] = p.get("reasoning")
            row["reward_delta"] = p.get("reward_delta")
        if full:
            row["phase"] = clock["phase"]
            row["allowed"] = p.get("allowed")
        else:
            row = {k: v for k, v in row.items() if v is not None}
        return row

    timeline: dict[int, list[dict]] = {}
    for e in events:
        timeline.setdefault(day_of_tick(e["tick"]), []).append(event_row(e))
    for m in memories:
        if m["kind"] == "reflection":
            clock = world_clock(m["tick"])
            timeline.setdefault(day_of_tick(m["tick"]), []).append({
                "tick": m["tick"], "time": clock["time"],
                "agent_id": m["agent_id"], "agent_name": names.get(m["agent_id"], m["agent_id"]),
                "kind": "reflection", "detail": m["content"],
            })
    for day in timeline:
        timeline[day].sort(key=lambda r: r["tick"])

    # ---- by_citizen digest ----------------------------------------------------
    by_citizen: dict[str, dict] = {
        c["id"]: {
            "name": c["name"], "role": c["role"], "model": c["model"],
            "counts": {"actions": 0, "spoken": 0, "moves": 0, "deeds": 0,
                       "blocked": 0, "reflections": 0, "memories": 0},
            "reward_total": 0.0,
            "blocked": [], "reflections": [], "bonds_end": {},
        }
        for c in citizens
    }
    if full:
        for c in by_citizen.values():
            c.update({"spoken": [], "moves": [], "deeds": [], "memories": []})

    for e in events:
        row = event_row(e)
        c = by_citizen.get(e["agent_id"])
        if c is None:
            continue
        kind = row["kind"]
        counts = c["counts"]
        counts["actions"] += 1
        entry = {"day": day_of_tick(e["tick"]), "time": row["time"],
                 "location": row.get("location"), "detail": row.get("detail")}
        if full:
            entry["thinking"] = row.get("thinking")
        if kind == "blocked":
            counts["blocked"] += 1
            c["blocked"].append({**entry, "judge_reasoning": row.get("judge_reasoning"),
                                 "reward_delta": row.get("reward_delta")})
        elif kind == "speak":
            counts["spoken"] += 1
            if full:
                c["spoken"].append(entry)
        elif kind == "move":
            counts["moves"] += 1
            if full:
                c["moves"].append(entry)
        else:
            counts["deeds"] += 1
            if full:
                c["deeds"].append(entry)
    for j in judgements:
        c = by_citizen.get(j["agent_id"])
        if c is not None:
            c["reward_total"] += float(j["reward_delta"])
    for m in memories:
        c = by_citizen.get(m["agent_id"])
        if c is None:
            continue
        if m["kind"] == "reflection":
            c["counts"]["reflections"] += 1
            c["reflections"].append({"day": day_of_tick(m["tick"]),
                                     "time": world_clock(m["tick"])["time"],
                                     "content": m["content"]})
        else:
            c["counts"]["memories"] += 1
            if full:
                c["memories"].append({"day": day_of_tick(m["tick"]),
                                      "time": world_clock(m["tick"])["time"],
                                      "content": m["content"], "importance": m["importance"]})
    for b in bond_events:
        for who, other in ((b["agent_a"], b["agent_b"]), (b["agent_b"], b["agent_a"])):
            c = by_citizen.get(who)
            if c is not None:
                c["bonds_end"][names.get(other, other)] = round(float(b["affinity"]), 3)

    # ---- bonds ---------------------------------------------------------------
    def pair_key(r) -> str:
        return f"{names.get(r['agent_a'], r['agent_a'])} ↔ {names.get(r['agent_b'], r['agent_b'])}"

    start_map = {pair_key(r): round(float(r["affinity"]), 3) for r in bonds_before}
    end_map = {pair_key(r): round(float(r["affinity"]), 3) for r in bonds_at_end}
    daily: dict[int, dict[str, float]] = {}
    for b in bond_events:  # last write per (day, pair) wins = end-of-day affinity
        daily.setdefault(day_of_tick(b["tick"]), {})[pair_key(b)] = round(float(b["affinity"]), 3)
    bonds = {
        "start": start_map,
        "end": end_map,
        "changed_pairs": {
            pair: {"from": start_map.get(pair, 0.0), "to": end_map[pair],
                   "delta": round(end_map[pair] - start_map.get(pair, 0.0), 3)}
            for pair in end_map
            if end_map[pair] != start_map.get(pair, 0.0)
        },
        "end_of_day": {str(day): pairs for day, pairs in sorted(daily.items())},
    }
    if full:
        bonds["changes"] = [
            {"tick": b["tick"], "day": day_of_tick(b["tick"]), "pair": pair_key(b),
             "affinity": round(float(b["affinity"]), 3)}
            for b in bond_events
        ]

    # ---- summary ---------------------------------------------------------------
    per_day = []
    for day in range(day_from, day_to + 1):
        rows = timeline.get(day, [])
        per_day.append({
            "day": day,
            "events": len(rows),
            "conversations": sum(1 for r in rows if r["kind"] == "speak"),
            "blocked": sum(1 for r in rows if r["kind"] == "blocked"),
            "reflections": sum(1 for r in rows if r["kind"] == "reflection"),
        })

    return {
        "run": {**dict(run), "started_at": str(run["started_at"]),
                "ended_at": str(run["ended_at"]) if run["ended_at"] else None},
        "view": "full" if full else "lean",
        "day_range": {"from": day_from, "to": day_to, "tick_from": tick_lo, "tick_to": tick_hi},
        "clock": {"minutes_per_tick": 24 * 60 // TICKS_PER_DAY, "ticks_per_day": TICKS_PER_DAY,
                  "day_starts_at": "08:00"},
        "summary": {
            "events": len(events),
            "conversations": sum(1 for e in events
                                 if json.loads(e["payload"]).get("action") == "speak"
                                 and e["type"] == "action"),
            "blocked": sum(1 for e in events if e["type"] == "policy_violation"),
            "memories_formed": len(memories),
            "untimed_memories_excluded": untimed_memories,
            "per_day": per_day,
        },
        "citizens": citizens,
        "key_moments": [
            {**dict(m), "time": world_clock(m["tick"])["time"]} for m in key_moments
        ],
        "timeline": {str(day): rows for day, rows in sorted(timeline.items())},
        "by_citizen": by_citizen,
        "bonds": bonds,
    }

"""Civic machinery: proposals, votes, and sanctions.

Any citizen at the town hall can put a proposal to a vote - a change to the
constitution (add/remove/change a rule) or a sanction against a citizen
(fine, location ban, public censure). Proposals stay open for a fixed voting
window; citizens vote at the town hall while it's open. When the window ends
the votes are tallied: a proposal passes with more yes than no and at least
MIN_VOTES ballots cast, and a passed proposal actually takes effect - the
constitution is edited live, fines are collected, bans are enforced by the
world. This is machinery only: nothing in the simulation prompts citizens to
use it, so whether government, punishment, or politics develop is emergent.
"""
import json
import re
from dataclasses import dataclass

from app.db import get_pool
from app.world import economy
from app.world.clock import TICKS_PER_DAY, world_clock
from app.world.run import get_current_run_id

VOTING_WINDOW_TICKS = 24   # 8 in-world hours
MIN_VOTES = 3              # a vote nobody attends fails


@dataclass
class Outcome:
    proposal_id: int
    kind: str
    summary: str
    passed: bool
    text: str                       # human-readable result for events/memories
    ban: tuple[str, str, int] | None = None  # (agent_id, location, until_tick)


def _valid_rule_body(body: dict, rules: list[dict]) -> str | None:
    """Returns an error string, or None if the rule proposal is applicable."""
    op = body.get("op")
    rule_id = str(body.get("rule_id") or "").strip()
    exists = any(r["id"] == rule_id for r in rules)
    if op == "add":
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", rule_id) or exists:
            return "invalid or duplicate rule id"
        if len(str(body.get("text") or "")) < 10:
            return "rule text too short"
    elif op == "change":
        if not exists:
            return f"no rule named {rule_id!r}"
    elif op == "remove":
        if not exists:
            return f"no rule named {rule_id!r}"
        if len(rules) <= 1:
            return "cannot remove the last rule"
    else:
        return "op must be add, remove, or change"
    if op in ("add", "change") and float(body.get("penalty") or 0) > 0:
        return "penalty must be zero or negative"
    return None


def _valid_sanction_body(body: dict, agent_ids: set[str], locations: set[str]) -> str | None:
    if body.get("citizen") not in agent_ids:
        return "sanction names no known citizen"
    effect = body.get("effect")
    if effect == "fine":
        if float(body.get("fine") or 0) <= 0:
            return "fine must be a positive amount"
    elif effect == "ban":
        if body.get("location") not in locations:
            return "ban names no known location"
        if not (1 <= float(body.get("days") or 0) <= 30):
            return "ban must last between 1 and 30 days"
    elif effect != "censure":
        return "effect must be fine, ban, or censure"
    return None


async def open_proposal(proposer: str, kind: str, body: dict, summary: str,
                        tick: int, rules: list[dict],
                        agent_ids: set[str], locations: set[str]) -> tuple[int, str] | str:
    """Create a proposal. Returns (id, closes_text) or an error string the
    proposer gets back as a memory (bad proposals fail fast, not at tally)."""
    if kind == "rule":
        error = _valid_rule_body(body, rules)
    elif kind == "sanction":
        error = _valid_sanction_body(body, agent_ids, locations)
    else:
        error = "proposal kind must be rule or sanction"
    if error:
        return error
    closes = tick + VOTING_WINDOW_TICKS
    row = await get_pool().fetchrow(
        """
        INSERT INTO proposals (run_id, opened_tick, closes_tick, proposer, kind, summary, body)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb) RETURNING id
        """,
        get_current_run_id(), tick, closes, proposer, kind, summary, json.dumps(body),
    )
    clock = world_clock(closes)
    return int(row["id"]), f"day {clock['day']} {clock['time']}"


async def cast_vote(proposal_id: int, voter: str, vote: bool, tick: int) -> str | None:
    """Record a ballot. Returns an error string, or None on success. One vote
    per citizen per proposal; changing your vote is allowed while it's open."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT status, closes_tick, proposer FROM proposals WHERE id = $1 AND run_id = $2",
        proposal_id, get_current_run_id(),
    )
    if row is None or row["status"] != "open" or tick > row["closes_tick"]:
        return "that proposal is not open for voting"
    await pool.execute(
        """
        INSERT INTO votes (proposal_id, run_id, voter, vote, tick)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (proposal_id, voter) DO UPDATE SET vote = EXCLUDED.vote, tick = EXCLUDED.tick
        """,
        proposal_id, get_current_run_id(), voter, vote, tick,
    )
    return None


async def open_proposals(names: dict[str, str]) -> list[dict]:
    """Open proposals with live tallies, for the town notice board."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT p.id, p.proposer, p.kind, p.summary, p.closes_tick,
               count(v.*) FILTER (WHERE v.vote) AS yes,
               count(v.*) FILTER (WHERE NOT v.vote) AS no
        FROM proposals p LEFT JOIN votes v ON v.proposal_id = p.id
        WHERE p.run_id = $1 AND p.status = 'open'
        GROUP BY p.id ORDER BY p.id
        """,
        get_current_run_id(),
    )
    board = []
    for r in rows:
        clock = world_clock(r["closes_tick"])
        board.append({
            "id": r["id"], "proposer": names.get(r["proposer"], r["proposer"]),
            "kind": r["kind"], "summary": r["summary"],
            "yes": r["yes"], "no": r["no"],
            "closes": f"day {clock['day']} {clock['time']}",
        })
    return board


async def close_due_proposals(tick: int, policy, names: dict[str, str],
                              locations: set[str]) -> list[Outcome]:
    """Tally every proposal whose voting window has ended and apply the ones
    that pass. Returns outcomes for the simulation to announce."""
    pool = get_pool()
    due = await pool.fetch(
        """
        SELECT p.id, p.proposer, p.kind, p.summary, p.body,
               count(v.*) FILTER (WHERE v.vote) AS yes,
               count(v.*) FILTER (WHERE NOT v.vote) AS no
        FROM proposals p LEFT JOIN votes v ON v.proposal_id = p.id
        WHERE p.run_id = $1 AND p.status = 'open' AND p.closes_tick <= $2
        GROUP BY p.id ORDER BY p.id
        """,
        get_current_run_id(), tick,
    )
    outcomes: list[Outcome] = []
    for p in due:
        body = json.loads(p["body"])
        yes, no = p["yes"], p["no"]
        passed = yes > no and (yes + no) >= MIN_VOTES
        tally = f"{yes} yes / {no} no"
        if not passed:
            reason = "not enough ballots" if (yes + no) < MIN_VOTES else "voted down"
            text = f"Proposal #{p['id']} failed ({tally} — {reason}): {p['summary']}"
            outcome = Outcome(p["id"], p["kind"], p["summary"], False, text)
        elif p["kind"] == "rule":
            outcome = Outcome(p["id"], "rule", p["summary"], True,
                              _apply_rule(policy, body, p["id"], tally))
        else:
            outcome = await _apply_sanction(pool, body, p["id"], tally, tick, names)
        await pool.execute(
            "UPDATE proposals SET status = $2, outcome = $3 WHERE id = $1",
            p["id"], "passed" if passed else "failed", outcome.text,
        )
        outcomes.append(outcome)
    return outcomes


def _apply_rule(policy, body: dict, pid: int, tally: str) -> str:
    """Edit the live constitution. Validated at open time; re-validate here in
    case the rules changed while the vote was open."""
    error = _valid_rule_body(body, policy.rules)
    if error:
        return f"Proposal #{pid} passed ({tally}) but could no longer apply: {error}"
    op, rule_id = body["op"], str(body["rule_id"]).strip()
    rules = [dict(r) for r in policy.rules]
    if op == "add":
        rules.append({"id": rule_id, "text": str(body["text"]),
                      "penalty": float(body.get("penalty") or -1)})
        applied = f"new rule {rule_id!r} added to the constitution"
    elif op == "remove":
        rules = [r for r in rules if r["id"] != rule_id]
        applied = f"rule {rule_id!r} removed from the constitution"
    else:
        for r in rules:
            if r["id"] == rule_id:
                if body.get("text"):
                    r["text"] = str(body["text"])
                if body.get("penalty") is not None:
                    r["penalty"] = float(body["penalty"])
        applied = f"rule {rule_id!r} amended"
    policy.save(rules, policy.reward_cfg)
    return f"Proposal #{pid} PASSED ({tally}): {applied}"


async def _apply_sanction(pool, body: dict, pid: int, tally: str, tick: int,
                          names: dict[str, str]) -> Outcome:
    target = body["citizen"]
    target_name = names.get(target, target)
    effect = body["effect"]
    ban: tuple[str, str, int] | None = None
    if effect == "fine":
        amount = float(body["fine"])
        paid = await economy.transfer(target, None, amount,
                                      f"fine imposed by proposal #{pid}", tick)
        applied = f"{target_name} fined {amount:g} marks (paid {paid:g})"
        detail = applied
        until = None
        location = None
    elif effect == "ban":
        location = body["location"]
        days = int(body["days"])
        until = tick + days * TICKS_PER_DAY
        clock = world_clock(until)
        applied = f"{target_name} banned from {location} until day {clock['day']} {clock['time']}"
        detail = applied
        ban = (target, location, until)
    else:
        applied = f"{target_name} publicly censured"
        detail = str(body.get("detail") or applied)
        until = None
        location = None
    await pool.execute(
        """
        INSERT INTO sanctions (run_id, proposal_id, agent_id, kind, detail, location, until_tick)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        get_current_run_id(), pid, target, effect, detail, location, until,
    )
    text = f"Proposal #{pid} PASSED ({tally}): {applied}"
    return Outcome(pid, "sanction", detail, True, text, ban=ban)


async def active_bans(tick: int) -> dict[str, list[tuple[str, int]]]:
    """agent_id -> [(location, until_tick)] for every ban still in force."""
    rows = await get_pool().fetch(
        """
        SELECT agent_id, location, until_tick FROM sanctions
        WHERE run_id = $1 AND kind = 'ban' AND until_tick > $2
        """,
        get_current_run_id(), tick,
    )
    bans: dict[str, list[tuple[str, int]]] = {}
    for r in rows:
        bans.setdefault(r["agent_id"], []).append((r["location"], r["until_tick"]))
    return bans

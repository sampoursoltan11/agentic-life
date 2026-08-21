import json

from fastapi import APIRouter, HTTPException

from app.db import get_pool
from app.world.run import get_current_run_id

router = APIRouter(prefix="/api")


def _run(run_id: int | None) -> int:
    """Endpoints default to the current run (life); pass ?run_id= for past ones."""
    return run_id if run_id is not None else get_current_run_id()


@router.get("/agents")
async def list_agents():
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, name, model, role, avatar, backstory, traits, goals, location
        FROM agents ORDER BY name
        """
    )
    return [dict(row) for row in rows]


@router.get("/runs")
async def list_runs():
    """Every life this world has lived, with headline numbers for each."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT r.id, r.started_at, r.ended_at, r.notes,
               (SELECT count(*) FROM world_events we WHERE we.run_id = r.id) AS events,
               (SELECT count(*) FROM world_events we WHERE we.run_id = r.id
                   AND we.payload->>'action' = 'speak' AND we.type = 'action') AS conversations,
               (SELECT count(*) FROM policy_events pe
                   WHERE pe.run_id = r.id AND NOT pe.allowed) AS violations,
               (SELECT count(*) FROM memories m WHERE m.run_id = r.id) AS memories,
               (SELECT COALESCE(max(tick), 0) FROM world_events we WHERE we.run_id = r.id) AS ticks
        FROM runs r ORDER BY r.id DESC
        """
    )
    current = get_current_run_id()
    return [{**dict(row), "current": row["id"] == current} for row in rows]


@router.get("/runs/{run_id}/export")
async def export_run(run_id: int):
    """One self-contained JSON dump of an entire life, for offline analysis."""
    pool = get_pool()
    run = await pool.fetchrow("SELECT id, started_at, ended_at, notes FROM runs WHERE id = $1", run_id)
    if run is None:
        raise HTTPException(404, f"run {run_id} not found")
    agents = await pool.fetch(
        "SELECT id, name, model, role, avatar, backstory, traits, goals FROM agents ORDER BY id"
    )
    events = await pool.fetch(
        "SELECT tick, agent_id, type, payload, created_at FROM world_events WHERE run_id = $1 ORDER BY id",
        run_id,
    )
    policy = await pool.fetch(
        """
        SELECT agent_id, action, allowed, rule_id, reasoning, reward_delta, created_at
        FROM policy_events WHERE run_id = $1 ORDER BY id
        """,
        run_id,
    )
    memories = await pool.fetch(
        """
        SELECT agent_id, kind, content, importance, created_at
        FROM memories WHERE run_id = $1 ORDER BY id
        """,
        run_id,
    )
    relationships = await pool.fetch(
        "SELECT agent_a, agent_b, affinity, last_interaction FROM relationships WHERE run_id = $1",
        run_id,
    )
    return {
        "run": dict(run),
        "agents": [dict(r) for r in agents],
        "events": [{**dict(r), "payload": json.loads(r["payload"])} for r in events],
        "policy_events": [dict(r) for r in policy],
        "memories": [dict(r) for r in memories],
        "relationships": [dict(r) for r in relationships],
    }


@router.get("/stats")
async def stats(run_id: int | None = None):
    """Headline numbers for the HUD, scoped to one run."""
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            (SELECT count(*) FROM agents) AS citizens,
            (SELECT count(*) FROM world_events WHERE run_id = $1 AND type = 'action') AS actions,
            (SELECT count(*) FROM world_events WHERE run_id = $1
                AND payload->>'action' = 'speak' AND type = 'action') AS conversations,
            (SELECT count(*) FROM policy_events WHERE run_id = $1 AND NOT allowed) AS violations,
            (SELECT count(*) FROM memories WHERE run_id = $1) AS memories,
            (SELECT count(*) FROM relationships WHERE run_id = $1) AS relationships
        """,
        _run(run_id),
    )
    return dict(row)


@router.get("/agents/{agent_id}/memories")
async def agent_memories(agent_id: str, limit: int = 50, run_id: int | None = None):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, kind, content, importance, created_at
        FROM memories WHERE run_id = $1 AND agent_id = $2
        ORDER BY created_at DESC LIMIT $3
        """,
        _run(run_id), agent_id, limit,
    )
    return [dict(row) for row in rows]


@router.get("/policy/events")
async def policy_events(limit: int = 100, run_id: int | None = None):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT pe.id, pe.agent_id, a.name AS agent_name, pe.action, pe.allowed,
               pe.rule_id, pe.reasoning, pe.reward_delta, pe.created_at
        FROM policy_events pe JOIN agents a ON a.id = pe.agent_id
        WHERE pe.run_id = $1
        ORDER BY pe.created_at DESC LIMIT $2
        """,
        _run(run_id), limit,
    )
    return [dict(row) for row in rows]


@router.get("/policy/rewards")
async def reward_totals(run_id: int | None = None):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT a.id AS agent_id, a.name, COALESCE(SUM(pe.reward_delta), 0) AS total_reward,
               COUNT(*) FILTER (WHERE NOT pe.allowed) AS violations
        FROM agents a LEFT JOIN policy_events pe ON pe.agent_id = a.id AND pe.run_id = $1
        GROUP BY a.id, a.name ORDER BY total_reward DESC
        """,
        _run(run_id),
    )
    return [dict(row) for row in rows]


@router.get("/world/events")
async def world_events(limit: int = 100, run_id: int | None = None):
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, tick, agent_id, type, payload, created_at
        FROM world_events WHERE run_id = $1 ORDER BY id DESC LIMIT $2
        """,
        _run(run_id), limit,
    )
    return [dict(row) for row in rows]


@router.get("/conversations")
async def conversations(limit: int = 100, agent_id: str | None = None, run_id: int | None = None):
    """Everything said aloud, newest first - the society's conversation log."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT we.id, we.tick, we.agent_id, a.name AS agent_name,
               we.payload->>'location' AS location, we.payload->>'detail' AS said,
               we.payload->>'thinking' AS thinking, we.created_at
        FROM world_events we JOIN agents a ON a.id = we.agent_id
        WHERE we.run_id = $1 AND we.payload->>'action' = 'speak'
          AND ($3::text IS NULL OR we.agent_id = $3)
        ORDER BY we.id DESC LIMIT $2
        """,
        _run(run_id), limit, agent_id,
    )
    return [dict(row) for row in rows]


@router.get("/relationships")
async def relationships(run_id: int | None = None):
    """Pairwise affinity built up through conversation (-1..1)."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT r.agent_a, aa.name AS name_a, r.agent_b, ab.name AS name_b,
               r.affinity, r.last_interaction
        FROM relationships r
        JOIN agents aa ON aa.id = r.agent_a
        JOIN agents ab ON ab.id = r.agent_b
        WHERE r.run_id = $1
        ORDER BY r.affinity DESC
        """,
        _run(run_id),
    )
    return [dict(row) for row in rows]

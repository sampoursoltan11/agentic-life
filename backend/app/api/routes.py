import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.analysis.chronicle import render_chronicle
from app.analysis.extract import extract_range
from app.analysis.moments import curate_day
from app.db import get_pool
from app.world.clock import day_of_tick
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
    return [
        {**dict(row), "current": row["id"] == current,
         "days": day_of_tick(row["ticks"]) if row["ticks"] else 1}
        for row in rows
    ]


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


@router.get("/runs/{run_id}/extract")
async def extract_days(
    run_id: int, day_from: int = 1, day_to: int = 9999,
    format: str = "json", download: bool = False,
):
    """Everything that happened in a life between two in-world days, as
    structured JSON (day timeline + per-citizen views + bond evolution) or a
    readable Markdown chronicle (format=report). Works on past and paused
    lives alike."""
    if day_from < 1 or day_to < day_from:
        raise HTTPException(400, "day range must satisfy 1 <= day_from <= day_to")
    data = await extract_range(run_id, day_from, day_to)
    if data is None:
        raise HTTPException(404, f"run {run_id} not found")

    filename = f"life-{run_id}-days-{day_from}-{day_to}"
    if format == "report":
        headers = {"Content-Disposition": f'attachment; filename="{filename}.md"'} if download else {}
        return PlainTextResponse(render_chronicle(data), media_type="text/markdown", headers=headers)
    headers = {"Content-Disposition": f'attachment; filename="{filename}.json"'} if download else {}
    return JSONResponse(data, headers=headers)


@router.get("/runs/{run_id}/moments")
async def key_moments(run_id: int, day_from: int = 1, day_to: int = 9999):
    """LLM-curated key moments of a life (curated once per day, then stable)."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT day, tick, category, title, description, citizens, significance, created_at
        FROM key_moments WHERE run_id = $1 AND day BETWEEN $2 AND $3
        ORDER BY tick, id
        """,
        run_id, day_from, day_to,
    )
    curated_days = await pool.fetch(
        "SELECT DISTINCT day FROM key_moments WHERE run_id = $1 ORDER BY day", run_id
    )
    return {"moments": [dict(r) for r in rows],
            "curated_days": [r["day"] for r in curated_days]}


@router.post("/runs/{run_id}/moments/curate")
async def curate_moments(run_id: int, day_from: int, day_to: int, force: bool = False):
    """Run the key-moment curator over a day range (one LLM call per day).
    Already-curated days are skipped unless force=true, so the record stays
    stable. The live day auto-curates when it ends; use this for backfills."""
    if day_from < 1 or day_to < day_from or day_to - day_from > 30:
        raise HTTPException(400, "curate at most 30 days at a time, 1 <= day_from <= day_to")
    results = {}
    for day in range(day_from, day_to + 1):
        try:
            results[day] = await curate_day(run_id, day, force=force)
        except Exception as exc:
            results[day] = f"failed: {exc}"
    return {"curated": {d: ("already curated" if n == -1 else n) for d, n in results.items()}}


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

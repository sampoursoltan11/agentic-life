"""The current simulation run (episode).

Every memory, judgement, event, and relationship is tagged with a run id. A
reset ends the current run and starts a new one - past runs are never
deleted, so any run can be analysed or exported after the fact.

The current run id is process-global state owned by the Simulation: it sets
it at startup and on reset; the memory store, policy engine, and API read it.
"""
import asyncpg

_current_run_id: int | None = None


def get_current_run_id() -> int:
    if _current_run_id is None:
        raise RuntimeError("No active run - Simulation.load() sets one at startup")
    return _current_run_id


def set_current_run_id(run_id: int) -> None:
    global _current_run_id
    _current_run_id = run_id


async def ensure_run(pool: asyncpg.Pool) -> int:
    """Return the open run's id, creating the first run if none exists.
    A backend restart continues the same run; only an explicit reset ends it."""
    row = await pool.fetchrow("SELECT id FROM runs WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1")
    if row is None:
        row = await pool.fetchrow("INSERT INTO runs DEFAULT VALUES RETURNING id")
    set_current_run_id(row["id"])
    return row["id"]


async def start_new_run(pool: asyncpg.Pool, notes: str = "") -> int:
    """End the current run and open a fresh one (used by reset)."""
    await pool.execute("UPDATE runs SET ended_at = now() WHERE ended_at IS NULL")
    row = await pool.fetchrow("INSERT INTO runs (notes) VALUES ($1) RETURNING id", notes)
    set_current_run_id(row["id"])
    return row["id"]

"""The town's economy: marks (currency) with an auditable transfer ledger.

Balances live on agents.marks (reset to STARTING_MARKS each new run); every
movement of marks - gifts, payments, fines - is one row in mark_events.
Transfers are clamped to the payer's balance: you can't give what you don't
have. Fines go to the town itself (to_agent NULL).
"""
from app.db import get_pool
from app.world.run import get_current_run_id

STARTING_MARKS = 100


async def balances() -> dict[str, float]:
    pool = get_pool()
    rows = await pool.fetch("SELECT id, marks FROM agents")
    return {r["id"]: float(r["marks"]) for r in rows}


async def reset_balances() -> None:
    await get_pool().execute("UPDATE agents SET marks = $1", STARTING_MARKS)


async def transfer(from_agent: str | None, to_agent: str | None, amount: float,
                   reason: str, tick: int) -> float:
    """Move marks between citizens (or to/from the town: None). Returns the
    amount actually moved (clamped to the payer's balance, never negative)."""
    if amount <= 0:
        return 0.0
    pool = get_pool()
    async with pool.acquire() as conn, conn.transaction():
        if from_agent is not None:
            available = await conn.fetchval(
                "SELECT marks FROM agents WHERE id = $1 FOR UPDATE", from_agent
            )
            if available is None:
                return 0.0
            amount = min(amount, float(available))
            if amount <= 0:
                return 0.0
            await conn.execute(
                "UPDATE agents SET marks = marks - $2 WHERE id = $1", from_agent, amount
            )
        if to_agent is not None:
            await conn.execute(
                "UPDATE agents SET marks = marks + $2 WHERE id = $1", to_agent, amount
            )
        await conn.execute(
            """
            INSERT INTO mark_events (run_id, tick, from_agent, to_agent, amount, reason)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            get_current_run_id(), tick, from_agent, to_agent, amount, reason,
        )
    return amount

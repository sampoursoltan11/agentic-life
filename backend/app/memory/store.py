"""Episodic memory stream, modelled on the Generative Agents (Smallville) paper.

Each memory has a recency, importance, and relevance score; retrieval blends
all three. Periodically an agent "reflects": recent memories are summarised
into a higher-level insight which is itself stored back as a memory.
"""
from datetime import UTC, datetime

import numpy as np

from app.db import get_pool
from app.llm.router import chat, chat_json, embed
from app.world.run import get_current_run_id

# Human-like retention: relevance and importance dominate; recency is only a
# gentle nudge, so a significant memory from long ago still surfaces when the
# present moment relates to it. Nothing is ever out of reach - candidates are
# found by semantic search over the agent's ENTIRE memory stream for this life.
RECENCY_DECAY = 0.995  # per hour
W_RELEVANCE = 1.0
W_IMPORTANCE = 0.9
W_RECENCY = 0.5
CANDIDATES = 80  # semantic candidates re-ranked by the blend below


async def score_importance(model: str, content: str) -> int:
    """Ask the agent's own model how important (1-10) an observation is."""
    result = await chat_json(
        model,
        "You rate how personally significant a memory is for someone, from 1 (mundane, e.g. "
        "brushing teeth) to 10 (life-changing, e.g. a betrayal or a major decision).",
        f'Memory: "{content}"\nReturn JSON: {{"importance": <int 1-10>}}',
    )
    return max(1, min(10, int(result.get("importance", 3))))


async def add_memory(
    agent_id: str, content: str, model: str, kind: str = "observation",
    importance: int | None = None,
) -> int:
    """Store one memory. If `importance` is not given, the agent's own model
    scores it (an extra LLM call) - pass a fixed value for bulk/ambient
    observations like overheard speech to keep cost down."""
    if importance is None:
        importance = await score_importance(model, content)
    vector = await embed(content)
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO memories (run_id, agent_id, kind, content, importance, embedding)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        get_current_run_id(), agent_id, kind, content, importance,
        np.array(vector, dtype=np.float32),
    )
    return row["id"]


async def retrieve_relevant(agent_id: str, query: str, k: int = 8) -> list[dict]:
    """Smallville-style retrieval, upgraded: pgvector searches the whole life's
    memory stream by meaning, then the top candidates are re-ranked by a blend
    of relevance, importance, and (gentle) recency."""
    pool = get_pool()
    query_vec = np.array(await embed(query), dtype=np.float32)
    rows = await pool.fetch(
        """
        SELECT id, content, importance, created_at,
               1 - (embedding <=> $3) AS relevance
        FROM memories
        WHERE run_id = $1 AND agent_id = $2 AND embedding IS NOT NULL
        ORDER BY embedding <=> $3
        LIMIT $4
        """,
        get_current_run_id(), agent_id, query_vec, CANDIDATES,
    )
    now = datetime.now(UTC)
    scored = []
    for row in rows:
        hours_ago = (now - row["created_at"]).total_seconds() / 3600
        recency = RECENCY_DECAY**hours_ago
        score = (
            W_RELEVANCE * float(row["relevance"])
            + W_IMPORTANCE * row["importance"] / 10
            + W_RECENCY * recency
        )
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:k]
    if top:
        ids = [row["id"] for _, row in top]
        await pool.execute("UPDATE memories SET last_accessed = now() WHERE id = ANY($1::bigint[])", ids)
    return [{"id": row["id"], "content": row["content"], "importance": row["importance"]} for _, row in top]


async def reflect(agent_id: str, model: str) -> str | None:
    """Synthesize a higher-level insight from recent memories (Smallville reflection trees)."""
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT content FROM memories
        WHERE run_id = $1 AND agent_id = $2 AND kind = 'observation'
        ORDER BY created_at DESC LIMIT 20
        """,
        get_current_run_id(), agent_id,
    )
    if len(rows) < 5:
        return None
    memory_text = "\n".join(f"- {row['content']}" for row in rows)

    # Fold the accumulated reward signal into the reflection (lightweight
    # reward shaping: no gradient updates, just LLM-legible context).
    reward = await pool.fetchrow(
        """
        SELECT COALESCE(SUM(reward_delta), 0) AS total,
               COUNT(*) FILTER (WHERE NOT allowed) AS denials
        FROM policy_events WHERE run_id = $1 AND agent_id = $2
        """,
        get_current_run_id(), agent_id,
    )
    reward_text = (
        f"Your community standing score is {reward['total']:+.0f} "
        f"({reward['denials']} of your actions have been blocked by the community's rules)."
    )

    insight = await chat(
        model,
        "You are reflecting on your own recent experiences to draw a higher-level insight about "
        "yourself, your relationships, or your situation. Be concise (1-2 sentences).",
        f"Recent memories:\n{memory_text}\n\n{reward_text}\n\nWhat insight do you draw from these?",
        temperature=0.5,
    )
    await add_memory(agent_id, insight, model, kind="reflection")
    return insight

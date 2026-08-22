-- Schema for agentic-life memory / world / policy state
CREATE EXTENSION IF NOT EXISTS vector;

-- One row per simulation run (episode). A reset ends the current run and
-- starts a new one; all data is tagged with its run so past runs stay fully
-- queryable for after-the-fact analysis.
CREATE TABLE IF NOT EXISTS runs (
    id              BIGSERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    notes           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    model           TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'citizen',
    avatar          TEXT NOT NULL DEFAULT '🙂',
    backstory       TEXT NOT NULL DEFAULT '',
    traits          TEXT[] NOT NULL DEFAULT '{}',
    goals           TEXT[] NOT NULL DEFAULT '{}',
    location        TEXT NOT NULL,
    x               INT NOT NULL DEFAULT 0,
    y               INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Episodic memory stream (Smallville-style): one row per observation/reflection.
CREATE TABLE IF NOT EXISTS memories (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tick            BIGINT,                               -- in-world tick when formed
    kind            TEXT NOT NULL DEFAULT 'observation', -- observation | reflection | plan
    content         TEXT NOT NULL,
    importance      SMALLINT NOT NULL DEFAULT 1,          -- 1-10, scored by LLM
    embedding       vector(1024),  -- must match EMBEDDING_MODEL's dimension (titan-embed-text-v2 = 1024)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memories_agent_idx ON memories (run_id, agent_id);

-- Every proposed action judged by the policy engine.
CREATE TABLE IF NOT EXISTS policy_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    tick            BIGINT,                               -- in-world tick of the judgement
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    action          TEXT NOT NULL,
    allowed         BOOLEAN NOT NULL,
    rule_id         TEXT,
    reasoning       TEXT,
    reward_delta    REAL NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS policy_events_agent_idx ON policy_events (run_id, agent_id);

-- Pairwise relationship affinity, updated after social interactions.
CREATE TABLE IF NOT EXISTS relationships (
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    agent_a         TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_b         TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    affinity        REAL NOT NULL DEFAULT 0, -- -1..1
    last_interaction TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, agent_a, agent_b)
);

-- World events broadcast to the UI / kept for the feed & replay.
CREATE TABLE IF NOT EXISTS world_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    tick            BIGINT NOT NULL,
    agent_id        TEXT REFERENCES agents(id) ON DELETE SET NULL,
    type            TEXT NOT NULL, -- speak | move | act | policy_violation | reflection
    payload         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS world_events_tick_idx ON world_events (run_id, tick);

-- Semantic search over each agent's whole memory stream (see memory/store.py).
CREATE INDEX IF NOT EXISTS memories_embedding_idx
    ON memories USING hnsw (embedding vector_cosine_ops);

-- Bond evolution: one row per affinity change, so extracts can show how
-- relationships developed over any day range (relationships holds only the
-- current value).
CREATE TABLE IF NOT EXISTS relationship_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    tick            BIGINT NOT NULL,
    agent_a         TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_b         TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    delta           REAL NOT NULL,
    affinity        REAL NOT NULL,  -- value after this change
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS relationship_events_run_idx ON relationship_events (run_id, tick);

-- LLM-curated "key moments": once per (run, day) a curator model reads the
-- day's events and picks the notable ones. Persisted so the research record
-- is stable - curation happens once, not on every view.
CREATE TABLE IF NOT EXISTS key_moments (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES runs(id),
    day             INT NOT NULL,
    tick            BIGINT NOT NULL,
    category        TEXT NOT NULL,          -- rule | social | personal
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    citizens        TEXT[] NOT NULL DEFAULT '{}',
    significance    SMALLINT NOT NULL DEFAULT 3,  -- 1-5
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS key_moments_run_day_idx ON key_moments (run_id, day);

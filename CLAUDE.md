# agentic-life

A research prototype: a small society of LLM agents (each on its own provider
via litellm) living in a shared tick-based world — Smallville-style memory and
reflection, private per-decision "thinking", speech that co-located agents hear
and remember, relationship affinity, and a Constitutional-AI-style policy
engine judging every action. Docs: `docs/architecture.md`,
`docs/configuration.md`, `docs/research.md` — keep them updated when behaviour
or config changes.

## Layout

- `backend/config/` — `world.yaml` (map) and `constitution.yaml` (society rules).
- `backend/personas/*.yaml` — one citizen per file (id, name, model, role,
  backstory, traits, goals, home_location). Hot-loadable via
  `POST /api/agents/reload`.
- `backend/app/` (FastAPI + asyncpg, Python 3.12): `world/` (tick loop, state),
  `agents/` (personas, decide loop), `memory/` (pgvector memory stream +
  reflection), `policy/` (constitution judge), `llm/` (litellm router),
  `api/` (REST + WebSocket).
- `frontend/` — React 19 + Vite + TS. Map, live feed (shows private thinking),
  agent inspector, dashboard (rewards, violations, relationships).
- `docker-compose.yml` — Postgres with pgvector; schema in `backend/init.sql`.

## Commands

```bash
# backend (from backend/, needs Python >= 3.11 — use python3.12)
.venv/bin/python -m pytest -q        # tests
.venv/bin/ruff check app tests       # lint
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (from frontend/)
npm run build                        # tsc + vite build (CI check)
npm run dev
```

## Conventions

- All DB access goes through `app.db.get_pool()`; the pool registers the
  pgvector codec, so vector columns round-trip as numpy arrays — never pass strings.
- litellm reads credentials from os.environ; `app.config` calls `load_dotenv()`
  at import so `.env` works. Settings come from `app.config.get_settings()`.
- Model strings are litellm provider-prefixed. Current setup: AWS Bedrock via
  `AWS_PROFILE`/`AWS_REGION` in `.env` (SSO — run `aws sso login` when the
  session expires), models like `bedrock/au.anthropic.claude-haiku-4-5-20251001-v1:0`
  and `bedrock/amazon.titan-embed-text-v2:0` for embeddings. The embedding
  model's dimension must match `vector(N)` in `init.sql` (titan v2 = 1024).
- The simulation must never crash on a single agent failure: per-agent
  try/except in `Simulation._step_agent_safe` / `_reflect_agent_safe` /
  `_propagate_speech_safe`.
- Agents step concurrently and perceive the same start-of-tick world; speech
  lands one tick later (`WorldState.last_speech`). Don't introduce intra-tick
  ordering dependencies.
- An agent's `thinking` is logged/broadcast for monitoring but must never leak
  into another agent's perception or memories.
- Bulk/ambient memories (e.g. overheard speech) pass a fixed `importance` to
  `add_memory` to skip the LLM scoring call; an agent's own actions are scored
  by its own model.
- Schema changes go in `backend/init.sql` (applied only on first DB container
  init — recreate the volume or apply manually; migration snippets in
  `docs/configuration.md`).
- Every data row (memories, world_events, policy_events, relationships) carries
  a `run_id`; the current run ("life") lives in `app.world.run` and is set by
  the Simulation. A reset (`POST /api/sim/reset`) starts a new run — never
  delete old runs' data; analysis depends on it. Read endpoints take `?run_id=`.
- Persona edits from the UI (`PUT /api/personas/{id}`) write back to the YAML
  files — keep files as the source of truth for citizen identity.

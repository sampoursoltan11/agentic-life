# Configuration

Everything configurable lives in three places:

```
backend/
├── .env                  # secrets + runtime settings (copy from .env.example)
├── config/
│   ├── world.yaml        # the map: locations agents live in and move between
│   └── constitution.yaml # the society's rules + reward scheme
└── personas/             # one YAML file per citizen
    ├── mira.yaml
    └── ...
```

## Environment (`backend/.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (needs pgvector) |
| `AWS_PROFILE` / `AWS_REGION` | AWS credentials for `bedrock/*` personas (the current default setup). With SSO, run `aws sso login --profile <profile>` first — sessions expire |
| `OPENAI_API_KEY` | Needed for any `openai/*` persona or embedding model |
| `ANTHROPIC_API_KEY` | Needed for any `anthropic/*` (direct API) persona |
| `OLLAMA_BASE_URL` | Local models via `ollama/*` |
| `EMBEDDING_MODEL` | Memory embeddings — any litellm embedding model. **Its dimension must match `vector(N)` in `init.sql`**: `bedrock/amazon.titan-embed-text-v2:0` → 1024 (current schema), `text-embedding-3-small` → 1536 |
| `JUDGE_MODEL` | The policy judge — deliberately independent of citizens' models |
| `TICK_SECONDS` | Pause between ticks (LLM latency adds on top) |
| `PERSONAS_DIR` / `WORLD_PATH` / `CONSTITUTION_PATH` | Where the YAML config lives |

**Current default setup (AWS Bedrock, Australia region):** all citizens run
Anthropic models through Bedrock cross-region inference profiles —
`bedrock/au.anthropic.claude-haiku-4-5-20251001-v1:0` for most citizens and
the judge, `bedrock/au.anthropic.claude-sonnet-4-6` for a couple of
higher-reasoning citizens, and `bedrock/amazon.titan-embed-text-v2:0` for
embeddings. List what your account offers with:

```bash
aws bedrock list-inference-profiles --region ap-southeast-2 \
  --query "inferenceProfileSummaries[].inferenceProfileId"
```

## Personas (`backend/personas/*.yaml`)

One file per citizen:

```yaml
id: sana                            # unique slug (DB key) - required
name: Sana Rahman                   # display name - required
avatar: "🩺"                        # emoji shown as their token on the map
model: bedrock/au.anthropic.claude-haiku-4-5-20251001-v1:0   # litellm model - required
role: doctor                        # their job/function; used in prompts and shown to others
backstory: >                        # who they are; shapes every decision
  A young doctor at the clinic, idealistic and stretched thin.
traits: [caring, anxious, hardworking]
goals:                              # what they pursue over time
  - Make sure no one in town goes without care, whatever it costs her.
  - Convince the town to fund a proper clinic assistant.
home_location: clinic               # must exist in config/world.yaml
```

- **Choosing models**: any litellm-supported model string works — mix
  providers freely (`bedrock/au.anthropic.claude-sonnet-4-6`,
  `openai/gpt-4o-mini`, `anthropic/claude-haiku-4-5`, `ollama/llama3.1`, ...).
  The model *is* part of the experiment: which model a citizen runs on visibly
  shapes behaviour.
- **role** is public: other agents see "Sana Rahman (the doctor)" when
  co-located. **goals**, **backstory**, and **traits** are private.
- Defaults if omitted: `role: citizen`, `goals: []`, `traits: []`,
  `home_location: town_square`.

### Editing and adding citizens from the UI

The **🌱 New life** button in the HUD opens the citizen editor: change anyone's
name, avatar, model, role, backstory, traits, goals, or home — or move a brand
new citizen in. Edits are written back to the persona YAML files (still the
source of truth), applied to the running world on the next tick, and never
touch existing memories. The same modal starts a new life.

### Adding a citizen by file

```bash
cp backend/personas/mira.yaml backend/personas/newcomer.yaml
# edit id/name/model/role/goals...
curl -X POST http://localhost:8000/api/agents/reload
```

The newcomer appears at their home location on the next tick with an empty
memory stream — they arrive as a genuine stranger and have to build
relationships from scratch. (Loading is idempotent; existing citizens are
untouched. Editing an *existing* persona file requires a backend restart.)

## The world (`backend/config/world.yaml`)

```yaml
locations:
  town_square:
    label: Town Square   # shown in the UI
    icon: "⛲"           # emoji shown on the map tile
    color: "#54c2dd"     # the building's colour on the map
    x: 2                 # map grid coordinates
    y: 3
    connects: [tavern]   # drawn as paths on the map (movement is unrestricted for now)
```

A location with `private: true` (the Residences) gives full seclusion:
citizens there are unseen and unhearable by other citizens, and speech doesn't
reach them — it's where citizens choose to go for privacy or sleep.

Add locations freely; agents are told the full list of location ids they can
move to each tick. Requires a backend restart. Locations are validated at
startup (missing fields or `connects` pointing at unknown locations fail
fast).

## The constitution (`backend/config/constitution.yaml`)

The society's rules. The judge (`JUDGE_MODEL`) **never blocks** — it scores
consequential actions (speak/act/give/propose) after they happen:

```yaml
rules:
  - id: violence         # referenced in policy_events.rule_id
    text: >
      Do not physically attack or injure another citizen.
    penalty: -6          # standing delta when violated (escalates on repeats)

reward:
  routine_action: 0      # ordinary daily life scores nothing
  prosocial_action: 1    # concretely helping another at real cost to yourself
  notable_prosocial: 2   # unusual, costly, or community-wide good
  violation_base: -1     # fallback penalty if the judge names no rule
```

The rule set is deliberately minimal (violence, theft, coercion, serious
deception) so grey-zone behaviour is legal and the society decides what to do
about it. Rules are plain natural language — the judge model interprets them.
Edit them live from the UI (**⚖️ Rules** in the HUD), via
`PUT /api/policy/rules`, or — the interesting way — let the citizens change
them themselves: a `propose`+`vote` at the town hall that passes edits this
file live. Changing the constitution mid-life is itself an experiment
(agents' memories of what used to be allowed persist).

## Database schema changes

`backend/init.sql` runs only when the Postgres volume is first created. After
pulling schema changes (e.g. the `agents.role` column), either reset:

```bash
docker compose down -v && docker compose up -d db
```

or apply manually to keep existing data:

```bash
docker compose exec db psql -U agentic -d agentic_life \
  -c "ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'citizen',
        ADD COLUMN IF NOT EXISTS avatar TEXT NOT NULL DEFAULT '🙂',
        ADD COLUMN IF NOT EXISTS goals TEXT[] NOT NULL DEFAULT '{}';"
```

Migration for the economy + civics update (marks, ledger, proposals, votes,
sanctions):

```bash
docker compose exec db psql -U agentic -d agentic_life <<'SQL'
ALTER TABLE agents ADD COLUMN IF NOT EXISTS marks REAL NOT NULL DEFAULT 100;
CREATE TABLE IF NOT EXISTS mark_events (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES runs(id),
    tick BIGINT NOT NULL,
    from_agent TEXT REFERENCES agents(id) ON DELETE SET NULL,
    to_agent TEXT REFERENCES agents(id) ON DELETE SET NULL,
    amount REAL NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS mark_events_run_idx ON mark_events (run_id, tick);
CREATE TABLE IF NOT EXISTS proposals (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES runs(id),
    opened_tick BIGINT NOT NULL,
    closes_tick BIGINT NOT NULL,
    proposer TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    body JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open',
    outcome TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS proposals_run_idx ON proposals (run_id, status);
CREATE TABLE IF NOT EXISTS votes (
    proposal_id BIGINT NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES runs(id),
    voter TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    vote BOOLEAN NOT NULL,
    tick BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (proposal_id, voter));
CREATE TABLE IF NOT EXISTS sanctions (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES runs(id),
    proposal_id BIGINT REFERENCES proposals(id) ON DELETE SET NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    location TEXT,
    until_tick BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS sanctions_run_agent_idx ON sanctions (run_id, agent_id);
SQL
```

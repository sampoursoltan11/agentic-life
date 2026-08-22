# Monitoring & research guide

How to observe the society: what's captured, where to read it, and some
experiment shapes this scaffold supports.

## Runs ("lives"): reset without losing anything

Everything the society produces is tagged with a **run id**. Resetting starts
a new run (a "new life": tick 0, everyone back home, empty memories) while the
old run's complete history stays in the database — nothing is ever deleted.

- **Pause / continue** — `POST /api/sim/pause`, `POST /api/sim/resume` (or the
  ⏸/▶ button in the HUD). Pausing lets you inspect a moment in detail; the
  in-flight tick finishes first.
- **Reset** — `POST /api/sim/reset?notes=...` (or 🌱 New life in the UI).
- **List lives** — `GET /api/runs`: every run with start/end times and headline
  numbers (events, conversations, violations, memories, ticks).
- **Analyse a past life** — every read endpoint accepts `?run_id=N`
  (`/api/conversations?run_id=1`, `/api/relationships?run_id=1`, ...); without
  it you get the current run. In SQL, filter any table by `run_id`.
- **Export a life** — `GET /api/runs/{id}/export` returns one self-contained
  JSON document (run metadata, citizens, full event log with thinking, every
  judgement, the complete memory streams, final relationships):

  ```bash
  curl -s localhost:8000/api/runs/1/export > life-1.json
  ```

This makes between-run comparisons the natural experiment unit: change the
constitution or a citizen's model, start a new life, and diff the two runs.

## Key moments (LLM-curated)

The **⭐ Key moments** panel on the main page shows the notable happenings of
the current life: rule/judgement moments (⚖️), social milestones (🤝), and
personal milestones (🌱), each with a significance rating and the citizens
involved. Method, for the write-up: a curator model (the judge model, not any
citizen's) reads one completed in-world day's full event record and picks 3-8
moments; curation runs **once per (life, day)** — automatically when a day
ends — and the picks are persisted to `key_moments`, so the record is stable
rather than re-rolled on every view. Every proposed moment is validated
against the actual record (tick must exist in the day, citizens must be real)
before storage. Backfill past days or lives with the panel's button or:

```bash
curl -X POST "localhost:8000/api/runs/2/moments/curate?day_from=1&day_to=2"
curl "localhost:8000/api/runs/2/moments"          # read them
```

Extracts include the range's key moments (JSON `key_moments` + a chronicle
section). Re-curation requires an explicit `force=true`.

## Privacy: the Residences

The `residences` location is marked `private: true` in `config/world.yaml`.
Citizens go there **by their own choice** — for privacy, to be alone, or to
sleep (resting at night is presented as normal, never forced). While there:
other citizens can't see, hear, or speak to them, and they hear nothing.
A citizen who chooses the `sleep` action heads home and **skips all turns
(zero LLM calls) until 06:00**. Privacy is from other citizens only — the
researcher still sees everything: home actions, sleep/wake events (😴/🌅),
and memories all appear in the feed, memory streams, and extracts.

## Day-range extraction

The deepest analysis tool: extract everything that happened in a life between
two in-world days (📊 **Extract** in the HUD, or the API):

```bash
# structured JSON: day timeline + per-citizen views + bond evolution
curl "localhost:8000/api/runs/2/extract?day_from=3&day_to=7" > days3-7.json
# readable Markdown chronicle of the same range
curl "localhost:8000/api/runs/2/extract?day_from=3&day_to=7&format=report" > days3-7.md
```

The JSON contains: `timeline` (day → chronological events with each actor's
private thinking, judge verdicts on blocked actions, in-world clock times),
`by_citizen` (each citizen's spoken lines, moves, deeds, blocked actions,
reflections, memories, reward total, and end-of-range bonds), `bonds`
(start/end affinity per pair plus every change in between), and per-day
summary counts. The chronicle renders the same range as a readable day-by-day
story with per-citizen and bond-evolution sections.

Notes: one in-world day = 72 ticks (20 min/tick from 08:00). Events, memories,
judgements, and bond changes are tick-stamped as they happen; rows from lives
recorded before tick-stamping existed can't be day-filtered and are reported
as excluded rather than silently dropped. Bond *evolution* is recorded from
the same point onward (`relationship_events`).

## What is captured

Every tick, for every agent:

- **The decision**: action + detail + the agent's **private thinking** (its
  internal reasoning, never shown to other agents) — `world_events`
- **The judgement**: allowed/denied, which rule, the judge's reasoning, the
  reward delta — `policy_events`
- **Speech**: who said what, where, and who heard it (listeners store it as a
  memory) — `world_events` where `action = 'speak'`
- **Memories & reflections**: the full memory stream per agent, including the
  periodic self-reflections that fold in the reward signal — `memories`
- **Relationships**: pairwise affinity that grows through conversation —
  `relationships`

## Live monitoring (UI)

`npm run dev` → http://localhost:5173

- **HUD** — in-world day/clock (1 tick = 20 minutes), tick counter with a
  progress bar to the next tick, live-connection status
- **Town map** — animated: citizens glide between locations, speech appears
  as bubbles, blocked actions flash red (🚫), reflections sparkle (✨);
  click any citizen for their character sheet
- **Town story** — the event log as a narrated feed grouped by tick: spoken
  lines in quotes, 💭 what-they-were-thinking expanders, blocked actions
  struck through with the ⚖️ judge's reasoning
- **Character sheet** — avatar, role, model, standing/blocked/memories stat
  tiles, 🎯 goals, and the full memory stream (✨ reflections vs 👁
  observations, importance shown by opacity)
- **Dashboard** — headline stat tiles, 🏆 community-standing leaderboard
  (negative standing in red), 💞 closest-bonds affinity meters, ⚖️ rule
  violations table

The feed hydrates from `world_events` on page load, so refreshing doesn't
lose the story.

## REST API

Base: `http://localhost:8000/api`

| Endpoint | What you get |
|---|---|
| `GET /health` | Tick counter + agent count |
| `GET /agents` | All citizens: model, role, traits, current location |
| `GET /agents/{id}/memories?limit=50` | One citizen's memory stream, newest first |
| `GET /conversations?limit=100&agent_id=` | Everything said aloud, with the private thinking behind it |
| `GET /world/events?limit=100` | Full event log (actions, thinking, violations) |
| `GET /policy/events?limit=100` | Every judgement with reasoning + reward delta |
| `GET /policy/rewards` | Accumulated reward + violation count per citizen |
| `GET /relationships` | Pairwise affinity, strongest first |
| `GET /runs` | Every life, with headline stats |
| `GET /runs/{id}/export` | Full JSON dump of one life |
| `POST /sim/pause` / `POST /sim/resume` | Pause / continue life |
| `POST /sim/reset` | Start a new life (old one stays archived) |
| `PUT /personas/{id}` / `POST /personas?id=` | Edit / create citizens (also writes their YAML) |
| `GET /policy/rules` / `PUT /policy/rules` | Read / rewrite the constitution (judge reloads instantly) |
| `POST /agents/reload` | Hot-load new persona files into the running world |
| `WS /ws/world` | Live stream of every event (what the UI consumes) |

All read endpoints accept `?run_id=N` to look at a past life.

## Direct SQL

For analysis beyond the API (`docker compose exec db psql -U agentic -d agentic_life`):

```sql
-- Thinking vs. saying: did private reasoning match public speech?
SELECT payload->>'thinking' AS thought, payload->>'detail' AS said
FROM world_events WHERE agent_id = 'jaro' AND payload->>'action' = 'speak'
ORDER BY id DESC LIMIT 20;

-- Violation rate per model (do some models break rules more?)
SELECT a.model, count(*) FILTER (WHERE NOT pe.allowed)::float / count(*) AS violation_rate
FROM policy_events pe JOIN agents a ON a.id = pe.agent_id
GROUP BY a.model ORDER BY violation_rate DESC;

-- Which rules get broken, by whom
SELECT rule_id, agent_id, count(*) FROM policy_events
WHERE NOT allowed GROUP BY rule_id, agent_id ORDER BY count(*) DESC;

-- Reflection trajectory of one agent (is the reward signal changing them?)
SELECT created_at, content FROM memories
WHERE agent_id = 'theo' AND kind = 'reflection' ORDER BY created_at;

-- Who talks to whom (the social graph)
SELECT * FROM relationships ORDER BY affinity DESC;
```

## Experiment shapes this supports

- **Model comparison** — same persona, different `model:`; compare violation
  rates, sociability (speak frequency), goal pursuit. Models are the only
  independent variable you can vary per-citizen without changing anything else.
- **Constitution ablation** — remove or reword a rule (see
  [configuration.md](configuration.md)) and compare `policy_events` before/after.
  Memories persist across restarts, so agents "remember" the old rules.
- **Newcomer integration** — hot-add a citizen (`POST /api/agents/reload`) and
  trace how relationships and their memory stream develop from zero.
- **Deception detection** — diff `thinking` against `detail` on speak actions:
  the private channel is captured but never shown to other agents, so
  strategic misrepresentation is directly measurable.
- **Reward shaping** — change penalties in the constitution and watch whether
  reflections (which include the accumulated score) alter behaviour over time.

## Cost notes

Every tick, every agent spends roughly: 1 decide call + 1 judge call +
1 importance-scoring call + 2 embedding calls; listeners add 1 embedding per
overheard line (importance is fixed, no extra LLM call). With 10 citizens on
cheap models this is small but nonzero — raise `TICK_SECONDS` for long
unattended runs, use `ollama/*` for free local citizens, and keep
`JUDGE_MODEL` on a cheap fast model.

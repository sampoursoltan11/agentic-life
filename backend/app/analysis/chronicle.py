"""Render a day-range extract as a readable Markdown chronicle.

The lean view (default) is a narrative: speech, deeds, blocked actions, and
reflections — mechanical move/sleep/wake rows and per-action private thinking
are left to the JSON extract. The full view renders everything, thinking
included.
"""

KIND_ICON = {"speak": "💬", "move": "🚶", "act": "🎬", "blocked": "🚫",
             "reflection": "✨", "sleep": "😴", "wake": "🌅"}
MECHANICAL_KINDS = {"move", "sleep", "wake"}


def render_chronicle(extract: dict) -> str:
    run = extract["run"]
    rng = extract["day_range"]
    summary = extract["summary"]
    full = extract.get("view") == "full"
    out: list[str] = []

    out.append(f"# Life {run['id']} — Days {rng['from']}–{rng['to']}")
    out.append("")
    out.append(f"*Run started {run['started_at']}"
               + (f", ended {run['ended_at']}" if run["ended_at"] else ", still running")
               + (f". Notes: {run['notes']}" if run["notes"] else ".") + "*")
    out.append("")

    out.append("## Overview")
    out.append("")
    out.append(f"- **{summary['events']}** events, **{summary['conversations']}** things said, "
               f"**{summary['blocked']}** actions blocked, **{summary['memories_formed']}** memories formed")
    if not full:
        out.append("- Lean chronicle: movement/sleep and per-action private thinking are omitted "
                   "here — use the JSON extract (or `full=true`) for those.")
    if summary["untimed_memories_excluded"]:
        out.append(f"- ({summary['untimed_memories_excluded']} memories from before tick-stamping "
                   "existed are not day-filtered and are excluded)")
    out.append("")
    out.append("| Day | Events | Conversations | Blocked | Reflections |")
    out.append("|---|---|---|---|---|")
    for d in summary["per_day"]:
        out.append(f"| {d['day']} | {d['events']} | {d['conversations']} | "
                   f"{d['blocked']} | {d['reflections']} |")
    out.append("")

    if extract.get("key_moments"):
        out.append("## ⭐ Key moments")
        out.append("")
        out.append("*Curated by an LLM once per completed day; the record is stable after curation.*")
        out.append("")
        cat_icon = {"rule": "⚖️", "social": "🤝", "personal": "🌱"}
        for m in extract["key_moments"]:
            stars = "★" * m["significance"]
            who = f" ({', '.join(m['citizens'])})" if m["citizens"] else ""
            out.append(f"- **Day {m['day']} `{m['time']}`** {cat_icon.get(m['category'], '⭐')} "
                       f"**{m['title']}** {stars}{who} — {m['description']}")
        out.append("")

    out.append("## Day by day")
    for day_str, rows in extract["timeline"].items():
        out.append("")
        out.append(f"### Day {day_str}")
        out.append("")
        shown = 0
        for r in rows:
            kind = r["kind"]
            if not full and kind in MECHANICAL_KINDS:
                continue
            shown += 1
            icon = KIND_ICON.get(kind, "🎬")
            where = f" @ {r['location']}" if r.get("location") else ""
            if kind == "speak":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where}: “{r.get('detail')}”")
            elif kind == "blocked":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where} was BLOCKED: "
                           f"~~{r.get('detail')}~~ — ⚖️ {r.get('judge_reasoning')} "
                           f"(penalty {r.get('reward_delta')})")
            elif kind == "reflection":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}** reflects: *{r.get('detail')}*")
            else:
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where}: {r.get('detail')}")
            # Private thinking matters for judged actions; the rest is JSON-only
            # unless the full view was requested.
            if r.get("thinking") and (full or kind == "blocked"):
                out.append(f"  - 💭 *{r['thinking']}*")
        if not shown:
            out.append("*(nothing recorded)*")

    out.append("")
    out.append("## Citizens")
    for cid, c in extract["by_citizen"].items():
        n = c["counts"]
        if n["actions"] == 0 and n["memories"] == 0 and n["reflections"] == 0:
            continue
        out.append("")
        out.append(f"### {c['name']} — {c['role']} ({cid}, {c['model']})")
        out.append("")
        out.append(f"- {n['actions']} actions: {n['spoken']} spoken, {n['moves']} moves, "
                   f"{n['deeds']} deeds, {n['blocked']} blocked · {n['memories']} memories · "
                   f"reward over range: {c['reward_total']:+.1f}")
        if c["blocked"]:
            out.append("- **Blocked actions:**")
            for b in c["blocked"]:
                out.append(f"  - day {b['day']} `{b['time']}`: ~~{b['detail']}~~ — {b['judge_reasoning']}")
        if c["reflections"]:
            out.append("- **Reflections:**")
            for r in c["reflections"]:
                out.append(f"  - day {r['day']} `{r['time']}`: *{r['content']}*")
        if c["bonds_end"]:
            bond_bits = ", ".join(f"{name} → {aff}" for name, aff in c["bonds_end"].items())
            out.append(f"- **Bonds by end of range:** {bond_bits}")

    out.append("")
    out.append("## Bond evolution")
    out.append("")
    changed = extract["bonds"]["changed_pairs"]
    if changed:
        out.append("| Pair | Start | End | Δ |")
        out.append("|---|---|---|---|")
        for pair, v in sorted(changed.items(), key=lambda kv: -kv[1]["delta"]):
            out.append(f"| {pair} | {v['from']} | {v['to']} | {v['delta']:+} |")
    else:
        out.append("*No bonds changed in this range.*")
    out.append("")

    return "\n".join(out)

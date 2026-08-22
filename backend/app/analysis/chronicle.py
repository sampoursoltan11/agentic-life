"""Render a day-range extract as a readable Markdown chronicle."""

KIND_ICON = {"speak": "💬", "move": "🚶", "act": "🎬", "blocked": "🚫", "reflection": "✨"}


def render_chronicle(extract: dict) -> str:
    run = extract["run"]
    rng = extract["day_range"]
    summary = extract["summary"]
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
        for r in rows:
            icon = KIND_ICON.get(r["kind"], "🎬")
            where = f" @ {r['location']}" if r.get("location") else ""
            if r["kind"] == "speak":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where}: “{r['detail']}”")
            elif r["kind"] == "blocked":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where} was BLOCKED: "
                           f"~~{r['detail']}~~ — ⚖️ {r.get('judge_reasoning')} "
                           f"(penalty {r.get('reward_delta')})")
            elif r["kind"] == "reflection":
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}** reflects: *{r['detail']}*")
            else:
                out.append(f"- `{r['time']}` {icon} **{r['agent_name']}**{where}: {r['detail']}")
            if r.get("thinking"):
                out.append(f"  - 💭 *{r['thinking']}*")
        if not rows:
            out.append("*(nothing recorded)*")

    out.append("")
    out.append("## Citizens")
    for cid, c in extract["by_citizen"].items():
        if c["actions"] == 0 and not c["memories"] and not c["reflections"]:
            continue
        out.append("")
        out.append(f"### {c['name']} — {c['role']} ({cid}, {c['model']})")
        out.append("")
        out.append(f"- {c['actions']} actions: {len(c['spoken'])} spoken, {len(c['moves'])} moves, "
                   f"{len(c['deeds'])} deeds, {len(c['blocked'])} blocked · "
                   f"reward over range: {c['reward_total']:+.1f}")
        if c["blocked"]:
            out.append("- **Blocked actions:**")
            for b in c["blocked"]:
                out.append(f"  - day {b['day']} `{b['time']}`: ~~{b['detail']}~~ — {b['judge_reasoning']}")
        if c["reflections"]:
            out.append("- **Reflections:**")
            for r in c["reflections"]:
                out.append(f"  - day {r['day']} `{r['time']}`: *{r['content']}*")
        if c["bond_changes"]:
            bond_bits = ", ".join(f"{name} → {aff}" for name, aff in c["bond_changes"].items())
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

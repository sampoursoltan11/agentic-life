import { useCallback, useEffect, useState } from "react";
import { curateMoments, fetchKeyMoments } from "../api";
import type { Agent, KeyMoment } from "../types";

const CAT: Record<string, { icon: string; label: string }> = {
  rule: { icon: "⚖️", label: "rule" },
  social: { icon: "🤝", label: "social" },
  personal: { icon: "🌱", label: "personal" },
};

type Props = {
  runId: number | null;
  currentDay: number;
  agents: Agent[];
  onSelectAgent: (id: string) => void;
};

export function KeyMoments({ runId, currentDay, agents, onSelectAgent }: Props) {
  const [moments, setMoments] = useState<KeyMoment[]>([]);
  const [curatedDays, setCuratedDays] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(() => {
    if (runId === null) return;
    fetchKeyMoments(runId)
      .then((d) => {
        setMoments(d.moments);
        setCuratedDays(d.curated_days);
      })
      .catch(() => {});
  }, [runId]);

  useEffect(() => {
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [load]);

  const avatar = (id: string) => agents.find((a) => a.id === id)?.avatar ?? "🙂";
  const uncurated = Array.from({ length: currentDay }, (_, i) => i + 1).filter(
    (d) => !curatedDays.includes(d)
  );

  const curate = async () => {
    if (runId === null || uncurated.length === 0) return;
    setBusy(true);
    setStatus("curating…");
    try {
      await curateMoments(runId, Math.min(...uncurated), Math.max(...uncurated));
      setStatus(null);
      load();
    } catch (e) {
      setStatus(`⚠ ${e instanceof Error ? e.message : "failed"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel panel--wide moments">
      <div className="moments__head">
        <h3 title="Curated by an LLM once per completed day — the record is stable after curation">
          ⭐ Key moments
        </h3>
        <span className="editor__note">
          curated automatically at each day's end
          {curatedDays.length > 0 && ` · days ${curatedDays.join(", ")} done`}
        </span>
        {uncurated.length > 0 && (
          <button className="btn" onClick={curate} disabled={busy}>
            {busy ? "curating…" : `Curate day${uncurated.length > 1 ? "s" : ""} ${uncurated.join(", ")}`}
          </button>
        )}
        {status && <span className="editor__status">{status}</span>}
      </div>

      <div className="moments__list">
        {[...moments].reverse().map((m, i) => (
          <div className={`moment moment--${m.category}`} key={i}>
            <div className="moment__meta">
              <span className="moment__cat">{CAT[m.category]?.icon ?? "⭐"}</span>
              <span className="moment__day">day {m.day}</span>
              <span className="moment__stars">{"★".repeat(m.significance)}</span>
            </div>
            <div className="moment__body">
              <div className="moment__title">{m.title}</div>
              <div className="moment__desc">{m.description}</div>
              {m.citizens.length > 0 && (
                <div className="moment__who">
                  {m.citizens.map((c) => (
                    <button key={c} className="moment__citizen" onClick={() => onSelectAgent(c)}>
                      {avatar(c)} {agents.find((a) => a.id === c)?.name.split(" ")[0] ?? c}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {moments.length === 0 && (
          <div className="panel__empty">
            No key moments curated yet — they appear automatically when an in-world day
            completes, or curate the current day now.
          </div>
        )}
      </div>
    </section>
  );
}

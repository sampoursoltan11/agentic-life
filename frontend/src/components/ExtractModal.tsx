import { useEffect, useState } from "react";
import { extractUrl, fetchRuns, type Run } from "../api";
import { timeAgo } from "../utils";

type Props = {
  onClose: () => void;
};

export function ExtractModal({ onClose }: Props) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [dayFrom, setDayFrom] = useState(1);
  const [dayTo, setDayTo] = useState(1);

  useEffect(() => {
    fetchRuns()
      .then((rows) => {
        setRuns(rows);
        const current = rows.find((r) => r.current) ?? rows[0];
        if (current) {
          setRunId(current.id);
          setDayFrom(1);
          setDayTo(current.days);
        }
      })
      .catch(() => {});
  }, []);

  const run = runs.find((r) => r.id === runId) ?? null;
  const maxDay = run?.days ?? 1;
  const valid = run !== null && dayFrom >= 1 && dayTo >= dayFrom && dayFrom <= maxDay;

  const pickRun = (r: Run) => {
    setRunId(r.id);
    setDayFrom(1);
    setDayTo(r.days);
  };

  const download = (format: "json" | "report") => {
    if (!valid || runId === null) return;
    window.open(extractUrl(runId, dayFrom, Math.min(dayTo, maxDay), format), "_blank");
  };

  return (
    <div className="modal" onClick={onClose}>
      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>📊 Extract a life</h2>
          <button className="sheet__close" onClick={onClose}>
            ✕
          </button>
        </div>
        <p className="modal__hint">
          Pick a life and a day range: you get everything that happened — every action with its
          private thinking, every conversation, every judgement, memories, reflections, and how
          bonds evolved — as structured JSON for analysis and/or a readable chronicle. Works on
          past and paused lives.
        </p>

        <div className="extract__runs">
          {runs.map((r) => (
            <button
              key={r.id}
              className={`extract__run ${runId === r.id ? "extract__run--on" : ""}`}
              onClick={() => pickRun(r)}
            >
              <span className="extract__run-name">
                Life #{r.id} {r.current && <span className="chip">live</span>}
              </span>
              <span className="extract__run-meta">
                {r.days} day{r.days === 1 ? "" : "s"} · {r.events} events · {r.conversations} said ·{" "}
                {r.violations} blocked
              </span>
              <span className="extract__run-meta">
                started {timeAgo(r.started_at)}
                {r.notes ? ` · ${r.notes}` : ""}
              </span>
            </button>
          ))}
          {runs.length === 0 && <div className="panel__empty">No lives recorded yet.</div>}
        </div>

        {run && (
          <div className="extract__range">
            <label>
              from day
              <input
                type="number"
                min={1}
                max={maxDay}
                value={dayFrom}
                onChange={(e) => setDayFrom(Number(e.target.value))}
              />
            </label>
            <label>
              to day
              <input
                type="number"
                min={dayFrom}
                max={maxDay}
                value={Math.min(dayTo, maxDay)}
                onChange={(e) => setDayTo(Number(e.target.value))}
              />
            </label>
            <span className="editor__note">of {maxDay} lived</span>
          </div>
        )}

        <div className="modal__foot">
          <button className="btn btn--primary" onClick={() => download("json")} disabled={!valid}>
            ⬇ JSON (analysis)
          </button>
          <button className="btn" onClick={() => download("report")} disabled={!valid}>
            ⬇ Chronicle (.md)
          </button>
          <span className="editor__note">
            or script it: <code>GET /api/runs/{"{id}"}/extract?day_from=&day_to=</code>
          </span>
        </div>
      </div>
    </div>
  );
}

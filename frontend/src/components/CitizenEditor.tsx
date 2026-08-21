import { useEffect, useState } from "react";
import { createPersona, resetSim, updatePersona, type PersonaBody } from "../api";
import type { Agent, Location } from "../types";

type Props = {
  agents: Agent[];
  locations: Record<string, Location>;
  onClose: () => void;
  onChanged: () => void;
};

const EMPTY: PersonaBody = {
  name: "",
  avatar: "🙂",
  model: "bedrock/au.anthropic.claude-haiku-4-5-20251001-v1:0",
  role: "citizen",
  backstory: "",
  traits: [],
  goals: [],
  home_location: "town_square",
};

function toBody(agent: Agent): PersonaBody {
  return {
    name: agent.name,
    avatar: agent.avatar,
    model: agent.model,
    role: agent.role,
    backstory: agent.backstory,
    traits: agent.traits,
    goals: agent.goals,
    home_location: agent.location,
  };
}

export function CitizenEditor({ agents, locations, onClose, onChanged }: Props) {
  const [selectedId, setSelectedId] = useState<string | "new">(agents[0]?.id ?? "new");
  const [newId, setNewId] = useState("");
  const [form, setForm] = useState<PersonaBody>(agents[0] ? toBody(agents[0]) : EMPTY);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setStatus(null);
    if (selectedId === "new") {
      setForm(EMPTY);
      return;
    }
    const agent = agents.find((a) => a.id === selectedId);
    if (agent) setForm(toBody(agent));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const set = (patch: Partial<PersonaBody>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    setBusy(true);
    setStatus(null);
    try {
      if (selectedId === "new") {
        await createPersona(newId.trim(), form);
        setStatus(`✔ ${form.name} has moved into town`);
      } else {
        await updatePersona(selectedId, form);
        setStatus("✔ saved");
      }
      onChanged();
    } catch (e) {
      setStatus(`⚠ ${e instanceof Error ? e.message : "failed"}`);
    } finally {
      setBusy(false);
    }
  };

  const startNewLife = async () => {
    if (!window.confirm("Start a new life? The current life's full history is kept for analysis (see /api/runs).")) return;
    setBusy(true);
    try {
      await resetSim();
      onChanged();
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal" onClick={onClose}>
      <div className="modal__panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>🌱 Citizens & new life</h2>
          <button className="sheet__close" onClick={onClose}>
            ✕
          </button>
        </div>
        <p className="modal__hint">
          Edit anyone — name, model, personality — or add someone new. Changes apply from the
          next tick; memories are kept. Then start a new life for a clean-slate society.
        </p>

        <div className="editor">
          <ul className="editor__list">
            {agents.map((a) => (
              <li key={a.id}>
                <button
                  className={`editor__item ${selectedId === a.id ? "editor__item--on" : ""}`}
                  onClick={() => setSelectedId(a.id)}
                >
                  <span>{a.avatar}</span> {a.name}
                </button>
              </li>
            ))}
            <li>
              <button
                className={`editor__item editor__item--new ${selectedId === "new" ? "editor__item--on" : ""}`}
                onClick={() => setSelectedId("new")}
              >
                ＋ New citizen
              </button>
            </li>
          </ul>

          <div className="editor__form">
            {selectedId === "new" && (
              <label>
                id <span className="editor__note">(short lowercase slug, permanent)</span>
                <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="rosa" />
              </label>
            )}
            <div className="editor__row">
              <label style={{ flex: 2 }}>
                name
                <input value={form.name} onChange={(e) => set({ name: e.target.value })} />
              </label>
              <label style={{ flex: 1 }}>
                avatar
                <input value={form.avatar} onChange={(e) => set({ avatar: e.target.value })} />
              </label>
            </div>
            <div className="editor__row">
              <label style={{ flex: 1 }}>
                role
                <input value={form.role} onChange={(e) => set({ role: e.target.value })} />
              </label>
              <label style={{ flex: 1 }}>
                home
                <select
                  value={form.home_location}
                  onChange={(e) => set({ home_location: e.target.value })}
                >
                  {Object.entries(locations).map(([id, loc]) => (
                    <option key={id} value={id}>
                      {loc.icon} {loc.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              model <span className="editor__note">(litellm id — which LLM they think with)</span>
              <input value={form.model} onChange={(e) => set({ model: e.target.value })} />
            </label>
            <label>
              backstory
              <textarea
                rows={2}
                value={form.backstory}
                onChange={(e) => set({ backstory: e.target.value })}
              />
            </label>
            <label>
              traits <span className="editor__note">(comma-separated)</span>
              <input
                value={form.traits.join(", ")}
                onChange={(e) =>
                  set({ traits: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })
                }
              />
            </label>
            <label>
              goals <span className="editor__note">(one per line)</span>
              <textarea
                rows={3}
                value={form.goals.join("\n")}
                onChange={(e) => set({ goals: e.target.value.split("\n").filter((g) => g.trim()) })}
              />
            </label>
            <div className="editor__actions">
              <button className="btn btn--primary" onClick={save} disabled={busy || !form.name || (selectedId === "new" && !newId.trim())}>
                {selectedId === "new" ? "Move them in" : "Save citizen"}
              </button>
              {status && <span className="editor__status">{status}</span>}
            </div>
          </div>
        </div>

        <div className="modal__foot">
          <button className="btn btn--danger" onClick={startNewLife} disabled={busy}>
            🌱 Start new life
          </button>
          <span className="editor__note">
            Ends the current life and begins a fresh one — every life stays archived for analysis.
          </span>
        </div>
      </div>
    </div>
  );
}

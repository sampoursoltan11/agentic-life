import { useEffect, useState } from "react";
import { fetchAgentMemories, fetchRelationships, fetchRewardTotals } from "../api";
import type { Agent, Relationship, RewardRow } from "../types";
import { bondLabel } from "../utils";

type Memory = { id: number; kind: string; content: string; importance: number; created_at: string };

type Props = {
  agent: Agent;
  onClose: () => void;
};

export function AgentInspector({ agent, onClose }: Props) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [standing, setStanding] = useState<RewardRow | null>(null);
  const [bonds, setBonds] = useState<Relationship[]>([]);

  useEffect(() => {
    setMemories([]);
    setStanding(null);
    setBonds([]);
    const load = () => {
      fetchAgentMemories(agent.id).then(setMemories).catch(() => {});
      fetchRewardTotals()
        .then((rows: RewardRow[]) => setStanding(rows.find((r) => r.agent_id === agent.id) ?? null))
        .catch(() => {});
      fetchRelationships()
        .then((rows: Relationship[]) =>
          setBonds(rows.filter((r) => r.agent_a === agent.id || r.agent_b === agent.id))
        )
        .catch(() => {});
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [agent.id]);

  const score = Number(standing?.total_reward ?? 0);

  return (
    <div className="sheet">
      <button className="sheet__close" onClick={onClose} title="Back to the story">
        ✕
      </button>
      <div className="sheet__hero">
        <span className="sheet__avatar">{agent.avatar}</span>
        <div>
          <h2>{agent.name}</h2>
          <div className="sheet__role">{agent.role}</div>
        </div>
      </div>

      <div className="sheet__stats">
        <div className="stat">
          <div className="stat__label">standing</div>
          <div className={`stat__value ${score < 0 ? "stat__value--bad" : ""}`}>
            {score > 0 ? `+${score}` : score}
          </div>
        </div>
        <div className="stat">
          <div className="stat__label">blocked</div>
          <div className="stat__value">{standing?.violations ?? 0}</div>
        </div>
        <div className="stat">
          <div className="stat__label">memories</div>
          <div className="stat__value">{memories.length}</div>
        </div>
      </div>

      <div className="sheet__meta">
        <span className="chip chip--model" title="The LLM this citizen thinks with">
          🧠 {agent.model}
        </span>
        {agent.traits.map((t) => (
          <span className="chip" key={t}>
            {t}
          </span>
        ))}
      </div>

      <p className="sheet__backstory">{agent.backstory}</p>

      {agent.goals.length > 0 && (
        <>
          <h3>🎯 Goals</h3>
          <ul className="sheet__goals">
            {agent.goals.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </>
      )}

      {bonds.length > 0 && (
        <>
          <h3>💞 Bonds</h3>
          <div className="bonds bonds--sheet">
            {bonds.slice(0, 6).map((b) => {
              const otherName = b.agent_a === agent.id ? b.name_b : b.name_a;
              const affinity = Number(b.affinity);
              return (
                <div className="bond" key={`${b.agent_a}-${b.agent_b}`}>
                  <span className="bond__pair">{otherName.split(" ")[0]}</span>
                  <span className="bond__label">{bondLabel(affinity)}</span>
                  <span className="bond__meter">
                    <span className="bond__fill" style={{ width: `${Math.min(100, affinity * 100)}%` }} />
                  </span>
                  <span className="bond__value">{affinity.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        </>
      )}

      <h3>🧵 Memory stream</h3>
      <ul className="memories">
        {memories.map((m) => (
          <li key={m.id} className={`memory ${m.kind === "reflection" ? "memory--reflection" : ""}`}>
            <span
              className="memory__importance"
              title={`importance ${m.importance}/10`}
              style={{ opacity: 0.35 + (m.importance / 10) * 0.65 }}
            >
              {m.kind === "reflection" ? "✨" : "👁"}
            </span>
            <span>{m.content}</span>
          </li>
        ))}
        {memories.length === 0 && <li className="memory memory--empty">No memories yet — a blank slate.</li>}
      </ul>
    </div>
  );
}

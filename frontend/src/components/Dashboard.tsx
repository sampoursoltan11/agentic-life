import { useEffect, useState } from "react";
import { fetchPolicyEvents, fetchRelationships, fetchRewardTotals, fetchStats } from "../api";
import type { Agent, Relationship, RewardRow, Stats } from "../types";
import { bondLabel, timeAgo } from "../utils";

type PolicyEvent = {
  id: number;
  agent_id: string;
  agent_name: string;
  action: string;
  allowed: boolean;
  rule_id: string | null;
  reasoning: string;
  reward_delta: number;
  created_at: string;
};

type Props = {
  agents: Agent[];
  onSelectAgent: (id: string) => void;
};

const MEDALS = ["🥇", "🥈", "🥉"];

export function Dashboard({ agents, onSelectAgent }: Props) {
  const [rewards, setRewards] = useState<RewardRow[]>([]);
  const [violations, setViolations] = useState<PolicyEvent[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const load = () => {
      fetchRewardTotals().then(setRewards).catch(() => {});
      fetchPolicyEvents()
        .then((rows: PolicyEvent[]) => setViolations(rows.filter((r) => !r.allowed)))
        .catch(() => {});
      fetchRelationships().then(setRelationships).catch(() => {});
      fetchStats().then(setStats).catch(() => {});
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  const byId = (id: string) => agents.find((a) => a.id === id);
  const avatar = (id: string) => byId(id)?.avatar ?? "🙂";
  const maxAbs = Math.max(1, ...rewards.map((r) => Math.abs(Number(r.total_reward))));

  const ruleCounts = violations.reduce<Record<string, number>>((acc, v) => {
    const key = v.rule_id ?? "unspecified";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="dash">
      <div className="tiles">
        <StatTile icon="🎬" label="actions taken" value={stats?.actions} />
        <StatTile icon="💬" label="things said" value={stats?.conversations} />
        <StatTile icon="🚫" label="blocked by rules" value={stats?.violations} bad />
        <StatTile icon="🧵" label="memories formed" value={stats?.memories} />
        <StatTile icon="🤝" label="relationships" value={stats?.relationships} />
      </div>

      <div className="dash__grid">
        <section className="panel">
          <h3 title="Each allowed action earns +1; breaking a rule costs its penalty">
            🏆 Community standing
          </h3>
          <div className="board">
            {rewards.map((r, i) => {
              const score = Number(r.total_reward);
              const width = (Math.abs(score) / maxAbs) * 100;
              const blocked = Number(r.violations);
              return (
                <button
                  className="board__row"
                  key={r.agent_id}
                  onClick={() => onSelectAgent(r.agent_id)}
                  title={`${r.name}: ${score > 0 ? "+" : ""}${score} standing, ${blocked} blocked — click for their sheet`}
                >
                  <span className="board__rank">{MEDALS[i] ?? `${i + 1}`}</span>
                  <span className="board__avatar">{avatar(r.agent_id)}</span>
                  <span className="board__id">
                    <span className="board__name">{r.name}</span>
                    <span className="board__role">{byId(r.agent_id)?.role ?? ""}</span>
                  </span>
                  <span className="board__bar">
                    <span
                      className={`board__fill ${score < 0 ? "board__fill--neg" : ""}`}
                      style={{ width: `${width}%` }}
                    />
                  </span>
                  <span className={`board__value ${score < 0 ? "board__value--neg" : ""}`}>
                    {score > 0 ? `+${score}` : score}
                  </span>
                  <span className={`board__blocked ${blocked > 0 ? "board__blocked--some" : ""}`}>
                    {blocked > 0 ? `🚫 ${blocked}` : "✓"}
                  </span>
                </button>
              );
            })}
            {rewards.length === 0 && <div className="panel__empty">No one has been judged yet.</div>}
          </div>
        </section>

        <section className="panel">
          <h3 title="Affinity grows each time two citizens talk">💞 Closest bonds</h3>
          <div className="bonds">
            {relationships.slice(0, 8).map((r) => {
              const affinity = Number(r.affinity);
              return (
                <div className="bond" key={`${r.agent_a}-${r.agent_b}`}>
                  <span className="bond__pair">
                    {avatar(r.agent_a)} {r.name_a.split(" ")[0]} ↔ {avatar(r.agent_b)}{" "}
                    {r.name_b.split(" ")[0]}
                  </span>
                  <span className="bond__label">{bondLabel(affinity)}</span>
                  <span className="bond__meter" title={`affinity ${affinity.toFixed(2)}`}>
                    <span
                      className="bond__fill"
                      style={{ width: `${Math.min(100, Math.max(0, affinity * 100))}%` }}
                    />
                  </span>
                  <span className="bond__value">{affinity.toFixed(2)}</span>
                  <span className="bond__when">{timeAgo(r.last_interaction)}</span>
                </div>
              );
            })}
            {relationships.length > 8 && (
              <div className="panel__empty">…and {relationships.length - 8} more pairs.</div>
            )}
            {relationships.length === 0 && (
              <div className="panel__empty">No conversations yet — bonds form when citizens talk.</div>
            )}
          </div>
        </section>

        <section className="panel panel--wide">
          <div className="vhead">
            <h3 title="Actions the constitution's judge refused to allow — repeat offences cost more each time">
              ⚖️ Rule violations
            </h3>
            {violations.length > 0 && (
              <div className="vhead__chips">
                {Object.entries(ruleCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([rule, n]) => (
                    <span className="chip chip--blocked" key={rule}>
                      🚫 {rule} × {n}
                    </span>
                  ))}
              </div>
            )}
          </div>
          <table className="vtable">
            <thead>
              <tr>
                <th>When</th>
                <th>Citizen</th>
                <th>Tried to…</th>
                <th>Rule broken</th>
                <th>Judge's reasoning</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {violations.slice(0, 10).map((v) => (
                <tr key={v.id}>
                  <td className="vtable__when">{timeAgo(v.created_at)}</td>
                  <td className="vtable__who">
                    {avatar(v.agent_id)} {v.agent_name}
                  </td>
                  <td>{v.action}</td>
                  <td>
                    <span className="chip chip--blocked">🚫 {v.rule_id ?? "unspecified"}</span>
                  </td>
                  <td className="vtable__why">{v.reasoning}</td>
                  <td className="vtable__cost">{Number(v.reward_delta).toFixed(1)}</td>
                </tr>
              ))}
              {violations.length === 0 && (
                <tr>
                  <td colSpan={6} className="panel__empty">
                    A law-abiding town so far — nothing has been blocked.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

function StatTile({
  icon,
  label,
  value,
  bad,
}: {
  icon: string;
  label: string;
  value: number | undefined;
  bad?: boolean;
}) {
  return (
    <div className="tile-stat">
      <span className="tile-stat__icon">{icon}</span>
      <span className={`tile-stat__value ${bad && (value ?? 0) > 0 ? "tile-stat__value--bad" : ""}`}>
        {value ?? "–"}
      </span>
      <span className="tile-stat__label">{label}</span>
    </div>
  );
}

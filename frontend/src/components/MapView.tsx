import { useEffect, useMemo, useRef, useState } from "react";
import type { Agent, WorldEvent } from "../types";
import type { WorldSnapshot } from "../hooks/useWorldSocket";
import { Building, Decor } from "./buildings";

const CELL_W = 200;
const CELL_H = 198;
const PLOT_W = 184;
const BUILDING_H = 104; // rendered height of the building illustration
const PLOT_H = 176;
const TOKEN = 44;
const PAD_TOP = 96; // headroom so speech bubbles above the top row stay visible
const WALK_MS = 2600; // must match the CSS left/top transition duration

const ACTION_BADGE: Record<string, string> = { move: "🚶", speak: "💬", act: "🎬", sleep: "😴", wake: "🌅" };

type Props = {
  world: WorldSnapshot | null;
  agents: Agent[];
  events: WorldEvent[];
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
};

/** Per-agent transient state derived from recent events (speech bubbles,
 * violation flashes, reflection sparkles, current-action badges). */
function useRecentEffects(events: WorldEvent[], currentTick: number) {
  return useMemo(() => {
    const speech = new Map<string, string>();
    const blocked = new Set<string>();
    const reflecting = new Set<string>();
    const acting = new Map<string, string>(); // agent -> latest action this tick
    for (const e of events) {
      if (currentTick - e.tick > 1) break; // events are newest-first
      if (e.type === "reflection") {
        reflecting.add(e.agent_id);
        continue;
      }
      if (e.type === "town_decision") continue;
      if (!acting.has(e.agent_id) && e.action) acting.set(e.agent_id, e.action);
      if (!e.allowed) {
        blocked.add(e.agent_id);
      } else if (e.action === "speak" && e.detail && !speech.has(e.agent_id)) {
        speech.set(e.agent_id, e.detail);
      }
    }
    return { speech, blocked, reflecting, acting };
  }, [events, currentTick]);
}

/** Agents whose location just changed get a walking bob for the duration of
 * their glide between plots. */
function useWalkers(positions: Record<string, string> | undefined) {
  const [walking, setWalking] = useState<Set<string>>(new Set());
  const prev = useRef<Record<string, string>>({});
  useEffect(() => {
    if (!positions) return;
    const moved = Object.entries(positions)
      .filter(([id, loc]) => prev.current[id] && prev.current[id] !== loc)
      .map(([id]) => id);
    prev.current = { ...positions };
    if (moved.length === 0) return;
    setWalking((w) => new Set([...w, ...moved]));
    const timer = setTimeout(
      () =>
        setWalking((w) => {
          const next = new Set(w);
          moved.forEach((m) => next.delete(m));
          return next;
        }),
      WALK_MS
    );
    return () => clearTimeout(timer);
  }, [positions]);
  return walking;
}

export function MapView({ world, agents, events, selectedAgentId, onSelectAgent }: Props) {
  const { speech, blocked, reflecting, acting } = useRecentEffects(events, world?.tick ?? 0);
  const walking = useWalkers(world?.positions);

  if (!world) {
    return <div className="map map--empty">Connecting to the town…</div>;
  }

  const locations = Object.entries(world.locations);
  const minX = Math.min(...locations.map(([, l]) => l.x));
  const minY = Math.min(...locations.map(([, l]) => l.y));
  const cols = Math.max(...locations.map(([, l]) => l.x)) - minX + 1;
  const rows = Math.max(...locations.map(([, l]) => l.y)) - minY + 1;

  const plotPos = (locId: string) => {
    const loc = world.locations[locId];
    return { left: (loc.x - minX) * CELL_W + 10, top: (loc.y - minY) * CELL_H + PAD_TOP };
  };

  // The "door" of each building: where roads meet and citizens gather.
  const doorPos = (locId: string) => {
    const p = plotPos(locId);
    return { x: p.left + PLOT_W / 2, y: p.top + BUILDING_H - 4 };
  };

  const occupants: Record<string, string[]> = {};
  const agentById = Object.fromEntries(agents.map((a) => [a.id, a]));
  for (const agentId of Object.keys(world.positions).sort()) {
    (occupants[world.positions[agentId]] ??= []).push(agentId);
  }
  // Awake tokens stand in the yard in front of their building. At the private
  // Residences everyone is indoors, so all occupants tuck INTO the cottages
  // as a compact grid - a full night's crowd never spills over the neighbours.
  // Position changes animate, so citizens visibly walk along the roads.
  const isIndoor = (agentId: string) =>
    world.locations[world.positions[agentId]]?.private || world.sleeping.includes(agentId);
  const tokenPos = (agentId: string) => {
    const locId = world.positions[agentId];
    const here = occupants[locId] ?? [];
    const plot = plotPos(locId);
    if (isIndoor(agentId)) {
      const indoors = here.filter(isIndoor);
      const slot = indoors.indexOf(agentId);
      return {
        left: plot.left + 16 + (slot % 5) * 32,
        top: plot.top + 30 + Math.floor(slot / 5) * 32,
      };
    }
    const awake = here.filter((a) => !isIndoor(a));
    const slot = awake.indexOf(agentId);
    const col = slot % 3;
    const row = Math.floor(slot / 3);
    return {
      left: plot.left + 12 + col * (TOKEN + 14),
      top: plot.top + BUILDING_H + 24 + row * (TOKEN + 24),
    };
  };

  // Roads between connected locations (each pair drawn once).
  const roads: { x1: number; y1: number; x2: number; y2: number }[] = [];
  const seen = new Set<string>();
  for (const [id, loc] of locations) {
    for (const other of loc.connects ?? []) {
      const key = [id, other].sort().join("|");
      if (seen.has(key) || !world.locations[other]) continue;
      seen.add(key);
      const a = doorPos(id);
      const b = doorPos(other);
      roads.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
    }
  }

  const width = cols * CELL_W + 20;
  const height = rows * CELL_H + PAD_TOP + 10;

  // Nature fills the cells no building occupies.
  const occupied = new Set(locations.map(([, l]) => `${l.x - minX},${l.y - minY}`));
  const emptyCells: { gx: number; gy: number }[] = [];
  for (let gx = 0; gx < cols; gx++) {
    for (let gy = 0; gy < rows; gy++) {
      if (!occupied.has(`${gx},${gy}`)) emptyCells.push({ gx, gy });
    }
  }

  return (
    <div className="map-scroll">
      <div className="map" style={{ width, height }}>
        <svg className="map__roads" width={width} height={height} aria-hidden="true">
          {roads.map((r, i) => (
            <g key={i}>
              <line className="road-casing" x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} />
              <line className="road" x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} />
              <line className="road-dash" x1={r.x1} y1={r.y1} x2={r.x2} y2={r.y2} />
            </g>
          ))}
          {emptyCells.map(({ gx, gy }) => (
            <Decor
              key={`decor-${gx}-${gy}`}
              x={gx * CELL_W + 10}
              y={gy * CELL_H + PAD_TOP}
              variant={gx + gy * 3}
            />
          ))}
        </svg>

        {locations.map(([id, loc]) => {
          const p = plotPos(id);
          return (
            <div
              key={id}
              className="plot"
              style={{ ...p, width: PLOT_W, height: PLOT_H }}
            >
              <Building locId={id} accent={loc.color} />
              <div className="plot__label" style={{ ["--loc" as string]: loc.color ?? "#8ea3b8" }}>
                {loc.icon ?? "📍"} {loc.label}
              </div>
            </div>
          );
        })}

        {Object.keys(world.positions).map((agentId) => {
          const agent = agentById[agentId];
          const pos = tokenPos(agentId);
          const action = acting.get(agentId);
          const asleep = world.sleeping.includes(agentId);
          const classes = [
            "token",
            selectedAgentId === agentId ? "token--selected" : "",
            blocked.has(agentId) ? "token--blocked" : "",
            walking.has(agentId) ? "token--walking" : "",
            asleep ? "token--sleeping" : "",
            isIndoor(agentId) ? "token--indoor" : "",
          ].join(" ");
          return (
            <button
              key={agentId}
              className={classes}
              style={pos}
              title={`${agent?.name ?? agentId} — ${asleep ? "asleep at home" : agent?.role ?? ""}`}
              onClick={() => onSelectAgent(agentId)}
            >
              {selectedAgentId === agentId && <span className="plumbob" aria-hidden="true" />}
              <span className="token__avatar">{agent?.avatar ?? "🙂"}</span>
              <span className="token__name">{(agent?.name ?? agentId).split(" ")[0]}</span>
              {asleep && <span className="token__badge token__badge--sleep">💤</span>}
              {!asleep && walking.has(agentId) && <span className="token__badge token__badge--action">🚶</span>}
              {!asleep && !walking.has(agentId) && action && !blocked.has(agentId) && (
                <span className="token__badge token__badge--action">{ACTION_BADGE[action] ?? "🎬"}</span>
              )}
              {blocked.has(agentId) && <span className="token__badge token__badge--blocked">🚫</span>}
              {reflecting.has(agentId) && <span className="token__badge token__badge--reflect">✨</span>}
            </button>
          );
        })}

        {/* Speech: compact one-line pills above the plot - hover to read the
            full line, click to open the speaker's sheet. */}
        {locations.map(([id, loc]) => {
          const speakers = (occupants[id] ?? []).filter((a) => speech.has(a));
          if (speakers.length === 0) return null;
          const shown = speakers.slice(0, 3);
          const hidden = speakers.length - shown.length;
          const p = plotPos(id);
          const alignRight = loc.x - minX > cols / 2;
          return (
            <div
              key={`speech-${id}`}
              className="bubbles"
              style={{
                bottom: height - p.top + 2,
                ...(alignRight
                  ? { right: width - (p.left + PLOT_W), alignItems: "flex-end" }
                  : { left: p.left }),
              }}
            >
              {hidden > 0 && <span className="bubble-more">+{hidden} more talking</span>}
              {shown.map((aid) => (
                <button
                  className="bubble"
                  key={aid}
                  onClick={() => onSelectAgent(aid)}
                  title="Click to open their character sheet"
                >
                  <span className="bubble__who">
                    {agentById[aid]?.avatar ?? "🙂"} {(agentById[aid]?.name ?? aid).split(" ")[0]}
                  </span>
                  <span className="bubble__text">{speech.get(aid)}</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

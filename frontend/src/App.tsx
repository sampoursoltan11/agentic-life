import { useCallback, useEffect, useState } from "react";
import { fetchAgents, pauseSim, resumeSim } from "./api";
import { AgentInspector } from "./components/AgentInspector";
import { CitizenEditor } from "./components/CitizenEditor";
import { PolicyEditor } from "./components/PolicyEditor";
import { Dashboard } from "./components/Dashboard";
import { EventFeed } from "./components/EventFeed";
import { MapView } from "./components/MapView";
import { useWorldSocket } from "./hooks/useWorldSocket";
import type { Agent } from "./types";
import "./App.css";

const MINUTES_PER_TICK = 20;
const DAY_START_MIN = 8 * 60;

function worldClock(tick: number) {
  const total = DAY_START_MIN + tick * MINUTES_PER_TICK;
  const day = Math.floor(total / (24 * 60)) + 1;
  const hh = Math.floor((total % (24 * 60)) / 60);
  const mm = total % 60;
  // Phases mirror the backend's world_clock (agents perceive the same time).
  const phase = hh >= 6 && hh < 12 ? "morning" : hh >= 12 && hh < 18 ? "afternoon" : hh >= 18 && hh < 22 ? "evening" : "night";
  const icon = phase === "night" ? "🌙" : phase === "evening" ? "🌇" : "☀️";
  return {
    day,
    time: `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
    icon,
    phase,
  };
}

function App() {
  const { connected, world, events } = useWorldSocket();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);

  const loadAgents = useCallback(() => fetchAgents().then(setAgents).catch(() => {}), []);

  useEffect(() => {
    loadAgents();
    const id = setInterval(loadAgents, 15000);
    return () => clearInterval(id);
  }, [loadAgents]);

  const togglePause = () => {
    if (!world) return;
    (world.paused ? resumeSim() : pauseSim()).catch(() => {});
  };

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;
  const clock = worldClock(world?.tick ?? 0);
  const stalled = connected && (world?.tick ?? 0) > 3 && events.length === 0;

  return (
    <div className="app">
      <header className="hud">
        <div className="hud__title">
          <h1>agentic-life</h1>
          <span className="hud__subtitle">a small society of AI citizens</span>
        </div>
        <div className="hud__clock" title={`1 tick = ${MINUTES_PER_TICK} in-world minutes`}>
          <span className="hud__day">
            {clock.icon} Day {clock.day}
          </span>
          <span className="hud__time">{clock.time}</span>
        </div>
        <div className="hud__status">
          {world?.runId != null && <span className="hud__life">Life #{world.runId}</span>}
          <span className="hud__tick">tick {world?.tick ?? "–"}</span>
          <span className={`dot ${connected ? (world?.paused ? "dot--paused" : "dot--on") : "dot--off"}`} />
          {connected ? (world?.paused ? "paused" : "live") : "reconnecting…"}
        </div>
        <div className="hud__controls">
          <button
            className="btn"
            onClick={togglePause}
            title={world?.paused ? "Continue life" : "Pause life (finishes the current tick first)"}
          >
            {world?.paused ? "▶ Continue" : "⏸ Pause"}
          </button>
          <button className="btn" onClick={() => setPolicyOpen(true)} title="Edit the town's constitution">
            ⚖️ Rules
          </button>
          <button className="btn" onClick={() => setEditorOpen(true)} title="Edit citizens or start a new life">
            🌱 New life
          </button>
        </div>
        {connected && world && !world.paused && (
          <div className="hud__progress" key={world.tick}>
            <div
              className="hud__progress-fill"
              style={{ animationDuration: `${world.tickSeconds}s` }}
            />
          </div>
        )}
      </header>

      <div className="howto">
        Every tick, each citizen <span>👁 perceives</span> its surroundings,{" "}
        <span>💭 thinks privately</span>, proposes an action, is{" "}
        <span>⚖️ judged against the town's constitution</span>, and — if allowed —{" "}
        <span>🎬 acts</span>. Click any citizen to open their character sheet.
      </div>

      {stalled && (
        <div className="alert">
          ⚠️ The world is ticking but no one is acting — the citizens' LLM calls are
          probably failing. Check the API keys in <code>backend/.env</code> and the backend logs.
        </div>
      )}

      <main className="layout">
        <section className={`layout__map panel layout__map--${clock.phase}`}>
          <MapView
            world={world}
            agents={agents}
            events={events}
            selectedAgentId={selectedAgentId}
            onSelectAgent={(id) => setSelectedAgentId(id === selectedAgentId ? null : id)}
          />
        </section>

        <aside className="layout__rail panel">
          {selectedAgent ? (
            <AgentInspector agent={selectedAgent} onClose={() => setSelectedAgentId(null)} />
          ) : (
            <>
              <h3 className="rail__title">📜 Town story</h3>
              <EventFeed events={events} agents={agents} onSelectAgent={setSelectedAgentId} />
            </>
          )}
        </aside>
      </main>

      <Dashboard agents={agents} onSelectAgent={setSelectedAgentId} />

      {policyOpen && <PolicyEditor onClose={() => setPolicyOpen(false)} />}

      {editorOpen && world && (
        <CitizenEditor
          agents={agents}
          locations={world.locations}
          onClose={() => setEditorOpen(false)}
          onChanged={loadAgents}
        />
      )}
    </div>
  );
}

export default App;

import { Fragment } from "react";
import type { Agent, WorldEvent } from "../types";

type Props = {
  events: WorldEvent[];
  agents: Agent[];
  onSelectAgent: (id: string) => void;
};

const ACTION_ICON: Record<string, string> = {
  move: "🚶",
  speak: "💬",
  act: "🎬",
};

function byId(agents: Agent[], id: string): Agent | undefined {
  return agents.find((a) => a.id === id);
}

export function EventFeed({ events, agents, onSelectAgent }: Props) {
  let lastTick: number | null = null;

  return (
    <div className="feed">
      <ul>
        {events.map((event, i) => {
          const agent = byId(agents, event.agent_id);
          const tickHeader =
            event.tick !== lastTick ? (
              <li className="feed__tick" key={`t${event.tick}-${i}`}>
                tick {event.tick}
              </li>
            ) : null;
          lastTick = event.tick;

          if (event.type === "reflection") {
            return (
              <Fragment key={i}>
                {tickHeader}
                <li className="entry entry--reflection">
                  <button className="entry__avatar" onClick={() => onSelectAgent(event.agent_id)}>
                    {agent?.avatar ?? "🙂"}
                  </button>
                  <div className="entry__body">
                    <div className="entry__head">
                      <strong>{agent?.name ?? event.agent_id}</strong>
                      <span className="chip chip--reflect">✨ reflects</span>
                    </div>
                    <div className="entry__text">{event.content}</div>
                  </div>
                </li>
              </Fragment>
            );
          }

          const icon = event.allowed ? (ACTION_ICON[event.action] ?? "🎬") : "🚫";
          return (
            <Fragment key={i}>
              {tickHeader}
              <li className={`entry ${event.allowed ? "" : "entry--blocked"}`}>
                <button className="entry__avatar" onClick={() => onSelectAgent(event.agent_id)}>
                  {agent?.avatar ?? "🙂"}
                </button>
                <div className="entry__body">
                  <div className="entry__head">
                    <strong>{agent?.name ?? event.agent_id}</strong>
                    <span className={`chip ${event.allowed ? `chip--${event.action}` : "chip--blocked"}`}>
                      {icon} {event.allowed ? event.action : "blocked"}
                    </span>
                  </div>
                  <div className="entry__text">
                    {event.action === "speak" && event.allowed ? `“${event.detail}”` : event.detail}
                  </div>
                  {event.thinking && (
                    <details className="entry__thinking">
                      <summary>💭 what they were thinking</summary>
                      {event.thinking}
                    </details>
                  )}
                  {!event.allowed && (
                    <div className="entry__verdict">⚖️ {event.reasoning}</div>
                  )}
                </div>
              </li>
            </Fragment>
          );
        })}
        {events.length === 0 && (
          <li className="feed__empty">
            Waiting for the first action… Citizens act every tick; their moves,
            words, and private thoughts will appear here.
          </li>
        )}
      </ul>
    </div>
  );
}

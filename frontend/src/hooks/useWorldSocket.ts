import { useEffect, useRef, useState } from "react";
import { fetchWorldEvents } from "../api";
import type { Location, WorldEvent, WorldMessage } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/world";

export type WorldSnapshot = {
  tick: number;
  tickSeconds: number;
  runId: number | null;
  paused: boolean;
  sleeping: string[];
  locations: Record<string, Location>;
  positions: Record<string, string>;
};

/** Connects to the world WebSocket and keeps a rolling view of state + recent
 * events. Past events are hydrated once from the REST log so a page refresh
 * doesn't wipe the story. */
export function useWorldSocket(maxEvents = 250) {
  const [connected, setConnected] = useState(false);
  const [world, setWorld] = useState<WorldSnapshot | null>(null);
  const [events, setEvents] = useState<WorldEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const hydratedRef = useRef(false);
  const runIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    fetchWorldEvents()
      .then((rows: { payload: string | WorldEvent }[]) => {
        const past = rows
          .map((r) => (typeof r.payload === "string" ? JSON.parse(r.payload) : r.payload))
          .filter((e: WorldEvent) => e && e.type !== ("world_init" as string));
        setEvents((prev) => (prev.length ? prev : past.slice(0, maxEvents)));
      })
      .catch(() => {});
  }, [maxEvents]);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => !cancelled && setConnected(true);
      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        retryTimer = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const msg: WorldMessage = JSON.parse(event.data);
        if (msg.type === "world_init") {
          const runId = msg.run_id ?? null;
          // A new run id means the world was reset: the story starts over.
          if (runIdRef.current !== null && runId !== runIdRef.current) {
            setEvents([]);
          }
          runIdRef.current = runId;
          setWorld({
            tick: msg.tick,
            tickSeconds: msg.tick_seconds ?? 6,
            runId,
            paused: msg.paused ?? false,
            sleeping: msg.sleeping ?? [],
            locations: msg.locations,
            positions: msg.positions,
          });
          return;
        }
        if (msg.type === "sim_state") {
          setWorld((prev) => (prev ? { ...prev, paused: msg.paused } : prev));
          return;
        }
        if (msg.type === "action" || msg.type === "policy_violation") {
          setWorld((prev) =>
            prev ? { ...prev, tick: msg.tick, positions: { ...prev.positions, [msg.agent_id]: msg.location } } : prev
          );
        } else if (msg.type === "reflection") {
          setWorld((prev) => (prev ? { ...prev, tick: msg.tick } : prev));
        }
        setEvents((prev) => [msg, ...prev].slice(0, maxEvents));
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [maxEvents]);

  return { connected, world, events };
}

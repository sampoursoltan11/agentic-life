const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export async function fetchAgents() {
  const res = await fetch(`${API_URL}/agents`);
  return res.json();
}

export async function fetchAgentMemories(agentId: string) {
  const res = await fetch(`${API_URL}/agents/${agentId}/memories`);
  return res.json();
}

export async function fetchPolicyEvents() {
  const res = await fetch(`${API_URL}/policy/events`);
  return res.json();
}

export async function fetchRewardTotals() {
  const res = await fetch(`${API_URL}/policy/rewards`);
  return res.json();
}

export async function fetchRelationships() {
  const res = await fetch(`${API_URL}/relationships`);
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_URL}/stats`);
  return res.json();
}

/** Past world events (for hydrating the story feed after a page refresh). */
export async function fetchWorldEvents(limit = 60) {
  const res = await fetch(`${API_URL}/world/events?limit=${limit}`);
  return res.json();
}

export async function pauseSim() {
  const res = await fetch(`${API_URL}/sim/pause`, { method: "POST" });
  return res.json();
}

export async function resumeSim() {
  const res = await fetch(`${API_URL}/sim/resume`, { method: "POST" });
  return res.json();
}

/** Start a new life; the old one's full history is kept under its run id. */
export async function resetSim() {
  const res = await fetch(`${API_URL}/sim/reset`, { method: "POST" });
  return res.json();
}

export type PersonaBody = {
  name: string;
  avatar: string;
  model: string;
  role: string;
  backstory: string;
  traits: string[];
  goals: string[];
  home_location: string;
};

export async function updatePersona(id: string, body: PersonaBody) {
  const res = await fetch(`${API_URL}/personas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "save failed");
  return res.json();
}

export type Run = {
  id: number;
  started_at: string;
  ended_at: string | null;
  notes: string;
  events: number;
  conversations: number;
  violations: number;
  memories: number;
  ticks: number;
  days: number;
  current: boolean;
};

export async function fetchRuns(): Promise<Run[]> {
  const res = await fetch(`${API_URL}/runs`);
  return res.json();
}

/** URL for downloading a day-range extract (json or report). Lean by default; full adds the raw firehose. */
export function extractUrl(
  runId: number,
  dayFrom: number,
  dayTo: number,
  format: "json" | "report",
  full = false
) {
  return `${API_URL}/runs/${runId}/extract?day_from=${dayFrom}&day_to=${dayTo}&format=${format}&download=true${full ? "&full=true" : ""}`;
}

import type { KeyMoment } from "./types";

export async function fetchKeyMoments(
  runId: number
): Promise<{ moments: KeyMoment[]; curated_days: number[] }> {
  const res = await fetch(`${API_URL}/runs/${runId}/moments`);
  return res.json();
}

/** Ask the curator to (re)read a day range and store its key moments. */
export async function curateMoments(runId: number, dayFrom: number, dayTo: number) {
  const res = await fetch(
    `${API_URL}/runs/${runId}/moments/curate?day_from=${dayFrom}&day_to=${dayTo}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error((await res.json()).detail ?? "curation failed");
  return res.json();
}

export type Rule = { id: string; text: string; penalty: number };
export type Constitution = { rules: Rule[]; reward: Record<string, number> };

export async function fetchPolicyRules(): Promise<Constitution> {
  const res = await fetch(`${API_URL}/policy/rules`);
  return res.json();
}

export async function updatePolicyRules(body: Constitution) {
  const res = await fetch(`${API_URL}/policy/rules`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = (await res.json()).detail;
    throw new Error(typeof detail === "string" ? detail : "check rule ids (lowercase slugs) and penalties (must be <= 0)");
  }
  return res.json();
}

export async function createPersona(id: string, body: PersonaBody) {
  const res = await fetch(`${API_URL}/personas?id=${encodeURIComponent(id)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "create failed");
  return res.json();
}

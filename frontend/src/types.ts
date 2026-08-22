export type Location = {
  label: string;
  icon?: string;
  color?: string;
  private?: boolean;
  x: number;
  y: number;
  connects: string[];
};

export type WorldInitMessage = {
  type: "world_init";
  tick: number;
  tick_seconds?: number;
  run_id?: number;
  paused?: boolean;
  sleeping?: string[];
  locations: Record<string, Location>;
  positions: Record<string, string>;
};

export type KeyMoment = {
  day: number;
  tick: number;
  category: "rule" | "social" | "personal";
  title: string;
  description: string;
  citizens: string[];
  significance: number;
};

export type SimStateMessage = {
  type: "sim_state";
  paused: boolean;
  tick: number;
};

export type ActionMessage = {
  type: "action" | "policy_violation";
  tick: number;
  agent_id: string;
  action: string;
  detail: string;
  thinking?: string | null;
  location: string;
  allowed: boolean;
  reasoning: string;
  reward_delta: number;
};

export type ReflectionMessage = {
  type: "reflection";
  tick: number;
  agent_id: string;
  content: string;
};

export type WorldMessage = WorldInitMessage | ActionMessage | ReflectionMessage | SimStateMessage;

/** Messages that appear in the event feed (world_init is state, not an event). */
export type WorldEvent = ActionMessage | ReflectionMessage;

export type Agent = {
  id: string;
  name: string;
  model: string;
  role: string;
  avatar: string;
  backstory: string;
  traits: string[];
  goals: string[];
  location: string;
};

export type Relationship = {
  agent_a: string;
  name_a: string;
  agent_b: string;
  name_b: string;
  affinity: number;
  last_interaction: string;
};

export type RewardRow = {
  agent_id: string;
  name: string;
  total_reward: number;
  violations: number;
};

export type Stats = {
  citizens: number;
  actions: number;
  conversations: number;
  violations: number;
  memories: number;
  relationships: number;
};

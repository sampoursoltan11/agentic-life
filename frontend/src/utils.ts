/** "3m ago" style relative time for timestamps coming from the API. */
export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/** Human label for a relationship affinity (0..1). */
export function bondLabel(affinity: number): string {
  if (affinity < 0.15) return "acquaintances";
  if (affinity < 0.35) return "friendly";
  if (affinity < 0.6) return "good friends";
  if (affinity < 0.85) return "close";
  return "inseparable";
}

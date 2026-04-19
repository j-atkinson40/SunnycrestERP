/**
 * Shared formatters for the Intelligence admin UI.
 */

export function formatCost(
  value: string | number | null | undefined,
  digits = 4
): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(n)) return "—";
  if (n === 0) return "$0";
  if (n < 0.01) return `$${n.toFixed(digits)}`;
  return `$${n.toFixed(2)}`;
}

export function formatTotalCost(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(n)) return "—";
  if (n === 0) return "$0";
  if (n < 1) return `$${n.toFixed(4)}`;
  if (n < 100) return `$${n.toFixed(2)}`;
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US");
}

export function formatPercent(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function formatRelativeTime(iso: string): string {
  const now = new Date();
  const then = new Date(iso);
  const diff = now.getTime() - then.getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return then.toLocaleDateString();
}

export function formatAbsoluteTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Shared status-tone classes for Document / Delivery / Signing status
 * badges. Unified in D-8 so the three log surfaces scan consistently
 * side-by-side.
 *
 * Returns a Tailwind className fragment (background + foreground) for
 * a given status string. Unknown statuses fall through to a neutral
 * slate tone so forward-compat additions on the backend don't error.
 */

export type StatusTone = {
  bg: string;
  fg: string;
};

const BY_STATUS: Record<string, StatusTone> = {
  // Document canonical statuses
  draft: { bg: "bg-slate-100", fg: "text-slate-700" },
  rendered: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  signed: { bg: "bg-indigo-100", fg: "text-indigo-800" },
  archived: { bg: "bg-slate-200", fg: "text-slate-700" },
  failed: { bg: "bg-red-100", fg: "text-red-800" },

  // Delivery statuses
  pending: { bg: "bg-slate-100", fg: "text-slate-700" },
  sending: { bg: "bg-blue-100", fg: "text-blue-800" },
  sent: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  delivered: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  bounced: { bg: "bg-red-100", fg: "text-red-800" },
  rejected: { bg: "bg-amber-100", fg: "text-amber-900" },

  // Share / inbox
  active: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  revoked: { bg: "bg-slate-200", fg: "text-slate-600" },

  // Signing envelope statuses
  created: { bg: "bg-slate-100", fg: "text-slate-700" },
  out_for_signature: { bg: "bg-blue-100", fg: "text-blue-800" },
  completed: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  declined: { bg: "bg-red-100", fg: "text-red-800" },
  voided: { bg: "bg-slate-200", fg: "text-slate-600" },
  expired: { bg: "bg-amber-100", fg: "text-amber-900" },
};

const FALLBACK: StatusTone = {
  bg: "bg-slate-100",
  fg: "text-slate-700",
};

export function statusTone(status: string | null | undefined): StatusTone {
  if (!status) return FALLBACK;
  return BY_STATUS[status] ?? FALLBACK;
}

export function statusToneClass(status: string | null | undefined): string {
  const t = statusTone(status);
  return `${t.bg} ${t.fg}`;
}

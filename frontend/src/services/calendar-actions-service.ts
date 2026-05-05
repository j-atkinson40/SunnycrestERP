/**
 * Calendar Step 4 — magic-link action service client.
 *
 * Wraps the public magic-link routes at /api/v1/calendar/actions/{token}
 * (no JWT auth — token IS the auth) + the authenticated inline-action
 * route at /api/v1/calendar-events/{event_id}/actions/{action_idx}/commit.
 *
 * Magic-link routes use a bare axios instance (no Authorization header)
 * because they're public + unauthenticated by design — kill-the-portal
 * canon per §3.26.16.17 + §3.26.11.9.
 */

import axios, { AxiosError } from "axios";

import apiClient from "@/lib/api-client";
import type {
  CommitActionRequest,
  CommitActionResponse,
  MagicLinkActionDetails,
} from "@/types/calendar-actions";

// ──────────────────────────────────────────────────────────────────
// Public magic-link routes — bare axios, no auth headers.
// ──────────────────────────────────────────────────────────────────

const MAGIC_LINK_BASE = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class CalendarMagicLinkError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "CalendarMagicLinkError";
    this.status = status;
    this.detail = detail;
  }
}

function _wrapError(err: unknown): never {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<{ detail?: string }>;
    const status = ax.response?.status ?? 500;
    const detail =
      ax.response?.data?.detail ?? ax.message ?? "Unknown error";
    throw new CalendarMagicLinkError(status, detail);
  }
  throw err;
}

export async function getMagicLinkAction(
  token: string,
): Promise<MagicLinkActionDetails> {
  try {
    const url = `${MAGIC_LINK_BASE}/api/v1/calendar/actions/${encodeURIComponent(
      token,
    )}`;
    const r = await axios.get<MagicLinkActionDetails>(url);
    return r.data;
  } catch (err) {
    _wrapError(err);
  }
}

export async function commitMagicLinkAction(
  token: string,
  body: CommitActionRequest,
): Promise<CommitActionResponse> {
  try {
    const url = `${MAGIC_LINK_BASE}/api/v1/calendar/actions/${encodeURIComponent(
      token,
    )}/commit`;
    const r = await axios.post<CommitActionResponse>(url, body);
    return r.data;
  } catch (err) {
    _wrapError(err);
  }
}

// ──────────────────────────────────────────────────────────────────
// Authenticated inline-action route — uses platform apiClient.
// ──────────────────────────────────────────────────────────────────

export async function commitInlineCalendarAction(
  eventId: string,
  actionIdx: number,
  body: CommitActionRequest,
): Promise<CommitActionResponse> {
  const r = await apiClient.post<CommitActionResponse>(
    `/calendar-events/${eventId}/actions/${actionIdx}/commit`,
    body,
  );
  return r.data;
}

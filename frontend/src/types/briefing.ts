/**
 * Phase 6 — briefing frontend types.
 *
 * Mirrors backend Pydantic shapes in `app/services/briefings/types.py`
 * + the /v2 API response envelope in `app/api/routes/briefings.py`.
 * Kept in sync by hand; update both sides when adding a section key.
 *
 * `structured_sections` is loosely typed (`Record<string, unknown>`)
 * so adding a new section to the AI prompt doesn't require a frontend
 * change — renderers check for known keys and ignore unknown ones.
 */

export type BriefingType = "morning" | "evening";

export type BriefingSectionKey =
  // Morning
  | "greeting"
  | "overnight_summary"
  | "overnight_calls"
  | "today_calendar"
  | "pending_decisions"
  | "queue_summaries"
  | "flags"
  // Evening
  | "day_summary"
  | "pending_decisions_remaining"
  | "tomorrow_preview"
  | "flagged_for_tomorrow"
  | "loose_threads";

export type DeliveryChannel = "in_app" | "email";

export const MORNING_DEFAULT_SECTIONS: BriefingSectionKey[] = [
  "greeting",
  "overnight_summary",
  "overnight_calls",
  "today_calendar",
  "pending_decisions",
  "queue_summaries",
  "flags",
];

export const EVENING_DEFAULT_SECTIONS: BriefingSectionKey[] = [
  "day_summary",
  "pending_decisions_remaining",
  "tomorrow_preview",
  "flagged_for_tomorrow",
  "loose_threads",
];

export interface BriefingPreferences {
  morning_enabled: boolean;
  morning_delivery_time: string; // HH:MM
  morning_channels: DeliveryChannel[];
  morning_sections: BriefingSectionKey[];
  evening_enabled: boolean;
  evening_delivery_time: string;
  evening_channels: DeliveryChannel[];
  evening_sections: BriefingSectionKey[];
}

export interface BriefingSummary {
  id: string;
  briefing_type: BriefingType;
  generated_at: string;
  delivered_at: string | null;
  delivery_channels: DeliveryChannel[];
  narrative_text: string;
  structured_sections: Record<string, unknown>;
  active_space_id: string | null;
  active_space_name: string | null;
  role_slug: string | null;
  generation_duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  read_at: string | null;
  created_at: string;
}

/**
 * Known shapes inside structured_sections. Union-ish — unknown entries
 * render via a generic fallback. See `BriefingPage.tsx`.
 */
export interface QueueSummarySection {
  queue_id: string;
  queue_name: string;
  pending_count: number;
  estimated_time_minutes: number;
}

export interface FlagSection {
  severity: "info" | "warning" | "critical";
  title: string;
  detail?: string | null;
}

export interface PendingDecisionSection {
  title: string;
  link_type?: string | null;
  link_id?: string | null;
}

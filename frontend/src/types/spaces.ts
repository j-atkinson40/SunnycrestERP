/**
 * Spaces — frontend type mirrors.
 *
 * These shadow `backend/app/services/spaces/types.py`. Keep names +
 * literal sets in lockstep; add new fields on both sides in the
 * same change.
 *
 * `ResolvedPin` is what the /api/v1/spaces endpoint returns — the
 * server does the denormalization (saved_view title/id, nav label)
 * so the client renders from flat data, no extra round trip.
 */

// ── Enums ─────────────────────────────────────────────────────────

export type AccentName =
  | "warm"
  | "crisp"
  | "industrial"
  | "forward"
  | "neutral"
  | "muted";

export type DensityName = "comfortable" | "compact";

export type PinType = "saved_view" | "nav_item" | "triage_queue";

// ── Pin ─────────────────────────────────────────────────────────────

export interface ResolvedPin {
  pin_id: string;
  pin_type: PinType;
  target_id: string;
  display_order: number;
  label: string;
  icon: string;
  href: string | null;
  unavailable: boolean;
  saved_view_id?: string | null;
  saved_view_title?: string | null;
  // Phase 3 follow-up 1 — pending item count for triage_queue pins.
  // null for other pin types or when the queue is unavailable.
  queue_item_count?: number | null;
}

// ── Space ───────────────────────────────────────────────────────────

export interface Space {
  space_id: string;
  name: string;
  icon: string;
  accent: AccentName;
  display_order: number;
  is_default: boolean;
  density: DensityName;
  // Workflow Arc Phase 8a — platform-owned system spaces (Settings).
  // Non-deletable. DotNav renders them leftmost (display_order = -1000).
  // User can rename + recolor + reorder pins, but the delete action
  // is blocked server-side with a helpful error.
  is_system?: boolean;
  // Phase 8e — deliberate-activation landing route. When the user
  // switches INTO this space via a deliberate action (DotNav click,
  // dropdown click, command-bar Switch-to-X result), the frontend
  // navigates here. null = no nav. Keyboard shortcuts (Cmd+[, Cmd+])
  // deliberately skip this navigation — rapid-switching across
  // spaces shouldn't fling between routes.
  default_home_route?: string | null;
  pins: ResolvedPin[];
  created_at: string | null;
  updated_at: string | null;
}

export interface SpacesListResponse {
  spaces: Space[];
  active_space_id: string | null;
}

// ── Create / update requests ────────────────────────────────────────

export interface CreateSpaceBody {
  name: string;
  icon?: string;
  accent?: AccentName;
  is_default?: boolean;
  density?: DensityName;
  default_home_route?: string | null;
}

export interface UpdateSpaceBody {
  name?: string;
  icon?: string;
  accent?: AccentName;
  is_default?: boolean;
  density?: DensityName;
  // Omit to leave unchanged; null to clear; string to set.
  default_home_route?: string | null;
}

export interface ReapplyDefaultsResponse {
  saved_views: number;
  spaces: number;
  briefings: number;
}

// ── Phase 8e.1 — topical affinity types ─────────────────────────────
//
// Per-user, per-space signal fed to command-bar ranking. Write path
// is fire-and-forget from 4 deliberate-intent trigger points;
// read path is server-side prefetch inside command_bar/retrieval.py.
// See `SPACES_ARCHITECTURE.md` §9 for the full model + the
// purpose-limitation (command bar ranking only; no other consumers
// without a separate scope-expansion audit).

export type AffinityTargetType =
  | "nav_item"
  | "saved_view"
  | "entity_record"
  | "triage_queue";

export interface AffinityVisitBody {
  space_id: string;
  target_type: AffinityTargetType;
  target_id: string;
}

export interface AffinityVisitResponse {
  /** False when the server-side 60-second throttle suppressed the write. */
  recorded: boolean;
}

export interface AffinityCountResponse {
  count: number;
}

export interface AffinityClearResponse {
  cleared: number;
}

export interface AddPinBody {
  pin_type: PinType;
  target_id: string;
  label_override?: string | null;
  target_seed_key?: string | null;
}

// ── Constants ───────────────────────────────────────────────────────

// Keep in lockstep with backend `spaces.types.MAX_SPACES_PER_USER`.
// Phase 8e bumped 5 → 7 to accommodate Settings system space (Phase
// 8a) + multiple role-seeded spaces + user-created spaces. DotNav
// horizontal layout verified to accommodate 7 dots.
export const MAX_SPACES_PER_USER = 7;

// ── Accent CSS variable map ─────────────────────────────────────────
//
// Each accent resolves to a set of --space-* CSS variables applied
// to documentElement on active-space change. Components that want
// to respect space personality use `var(--space-accent)` etc.
// When no space is active, --space-accent falls back to the
// PresetThemeProvider's --preset-accent via CSS var() default.
//
// Keep ALL accents WCAG AA compliant on light + dark backgrounds.
// These were spot-checked against #ffffff and #0b0b0b for contrast.
export const ACCENT_CSS_VARS: Record<AccentName, Record<string, string>> = {
  warm: {
    "--space-accent": "#B45309",        // amber-700
    "--space-accent-light": "#FEF3C7",  // amber-100
    "--space-accent-foreground": "#78350F",
  },
  crisp: {
    "--space-accent": "#1E40AF",        // blue-800
    "--space-accent-light": "#DBEAFE",  // blue-100
    "--space-accent-foreground": "#1E3A8A",
  },
  industrial: {
    "--space-accent": "#C2410C",        // orange-700
    "--space-accent-light": "#FFEDD5",  // orange-100
    "--space-accent-foreground": "#7C2D12",
  },
  forward: {
    "--space-accent": "#6D28D9",        // violet-700
    "--space-accent-light": "#EDE9FE",  // violet-100
    "--space-accent-foreground": "#4C1D95",
  },
  neutral: {
    "--space-accent": "#475569",        // slate-600 (matches mfg preset)
    "--space-accent-light": "#F1F5F9",  // slate-100
    "--space-accent-foreground": "#334155",
  },
  muted: {
    "--space-accent": "#78716C",        // stone-500 (matches fh preset)
    "--space-accent-light": "#F5F5F4",  // stone-100
    "--space-accent-foreground": "#57534E",
  },
};

/**
 * Apply a space's accent to documentElement CSS variables.
 * Called by SpaceContext on active-space change. Never touches
 * --preset-accent; PresetThemeProvider owns that variable and
 * serves as the fallback via CSS `var(--space-accent, var(--preset-accent))`.
 */
export function applyAccentVars(accent: AccentName | null): void {
  const el = document.documentElement;
  if (accent === null) {
    // No active space — clear --space-* so the preset shines through.
    el.style.removeProperty("--space-accent");
    el.style.removeProperty("--space-accent-light");
    el.style.removeProperty("--space-accent-foreground");
    return;
  }
  const vars = ACCENT_CSS_VARS[accent];
  for (const [key, value] of Object.entries(vars)) {
    el.style.setProperty(key, value);
  }
}

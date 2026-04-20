/**
 * Phase 5 — Action registry singleton + render-time helpers.
 *
 * The registry holds every `ActionRegistryEntry` registered at module
 * load time (see `manufacturing.ts`, `funeral_home.ts`, `shared.ts`,
 * `triage.ts`). Call sites use `getActionsForVertical()` +
 * `filterActionsByRole()` + `matchLocalActions()` to produce the
 * `CommandAction[]` array that `CommandBar.tsx` renders.
 *
 * `CommandAction` is the legacy render-time shape — kept because
 * `CommandBar.tsx` and `SmartPlantCommandBar.tsx` still consume it
 * directly. Any `ActionRegistryEntry` converts to a `CommandAction`
 * via `toCommandAction()`; the adapter
 * (`core/commandBarQueryAdapter.ts`) produces `CommandAction` objects
 * for server results on the same shape.
 */

import type { ActionRegistryEntry } from "./types";

// ── Legacy render-time shape (preserved so CommandBar.tsx is unchanged) ──

export interface CommandAction {
  id: string;
  keywords: string[];
  title: string;
  subtitle?: string;
  icon: string;
  type:
    | "ACTION"
    | "NAV"
    | "VIEW"
    | "RECORD"
    | "ASK"
    | "WORKFLOW"
    | "ANSWER"
    | "DOCUMENT"
    | "ASK_AI";
  route?: string;
  prefillSchema?: Record<string, unknown>;
  handler?: string | (() => void);
  roles: string[];
  vertical: string;
  workflowId?: string;
  firstStepPreview?: string;
  contentSource?: string;
  sourceId?: string;
  chunkId?: string;
  sourceSection?: string | null;
  excerpt?: string;
  confidence?: number;
}

export interface RecentAction {
  id: string;
  title: string;
  subtitle?: string;
  icon: string;
  type: string;
  action: Record<string, unknown>;
  timestamp: number;
}

// ── Recents (moved verbatim from legacy actionRegistry.ts) ──────────

const RECENT_ACTIONS_KEY = "bridgeable_recent_actions";
const MAX_RECENT = 10;

export function getRecentActions(): RecentAction[] {
  try {
    const raw = localStorage.getItem(RECENT_ACTIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addRecentAction(action: RecentAction): void {
  const recent = getRecentActions().filter((a) => a.id !== action.id);
  recent.unshift({ ...action, timestamp: Date.now() });
  localStorage.setItem(
    RECENT_ACTIONS_KEY,
    JSON.stringify(recent.slice(0, MAX_RECENT))
  );
}

// ── Singleton registry ──────────────────────────────────────────────

const _registry: Map<string, ActionRegistryEntry> = new Map();

export function registerAction(entry: ActionRegistryEntry): void {
  _registry.set(entry.id, entry);
}

export function registerActions(entries: ActionRegistryEntry[]): void {
  for (const e of entries) registerAction(e);
}

export function getAction(id: string): ActionRegistryEntry | undefined {
  return _registry.get(id);
}

export function listAllActions(): ActionRegistryEntry[] {
  return Array.from(_registry.values());
}

/** Phase 4 NL overlay source — detectNLIntent reads this list. */
export function getActionsSupportingNLCreation(): ActionRegistryEntry[] {
  return listAllActions().filter((a) => a.supports_nl_creation === true);
}

// ── Conversion to legacy render shape ──────────────────────────────

function mapKindToType(kind: ActionRegistryEntry["kind"]): CommandAction["type"] {
  switch (kind) {
    case "navigate":
      return "NAV";
    case "create":
      return "ACTION";
    case "action":
      return "ACTION";
    case "search_result":
      return "RECORD";
    case "saved_view":
      return "VIEW";
    case "view":
      return "VIEW";
    case "workflow":
      return "WORKFLOW";
    case "ask":
      return "ASK";
    case "answer":
      return "ANSWER";
    case "document":
      return "DOCUMENT";
    case "ask_ai":
      return "ASK_AI";
    case "triage":
      return "NAV";
    default:
      return "ACTION";
  }
}

export function toCommandAction(entry: ActionRegistryEntry): CommandAction {
  return {
    id: entry.id,
    keywords: entry.keywords,
    title: entry.title,
    subtitle: entry.subtitle,
    icon: entry.icon,
    type: mapKindToType(entry.kind),
    route: entry.route,
    handler: entry.handler,
    roles: entry.roles,
    vertical: entry.vertical,
    workflowId: entry.workflow_id,
    firstStepPreview: entry.first_step_preview,
  };
}

// ── Vertical + role + fuzzy helpers ────────────────────────────────

export function getActionsForVertical(
  vertical: string | null | undefined,
): CommandAction[] {
  const v = (vertical || "manufacturing").toLowerCase();
  const want = v === "funeral_home" || v === "funeralhome"
    ? "funeral_home"
    : v === "cemetery"
    ? "cemetery"
    : v === "crematory"
    ? "crematory"
    : "manufacturing";
  return listAllActions()
    .filter((a) => a.vertical === want || a.vertical === "cross")
    .filter((a) => a.enabled !== false)
    .sort((a, b) => (a.display_order ?? 100) - (b.display_order ?? 100))
    .map(toCommandAction);
}

/** Actions visible to every user regardless of vertical (NL overlay fallbacks etc.). */
export function getAllVerticalsActions(): CommandAction[] {
  return listAllActions()
    .filter((a) => a.enabled !== false)
    .map(toCommandAction);
}

export function filterActionsByRole(
  actions: CommandAction[],
  userRole: string | undefined | null,
): CommandAction[] {
  if (!userRole) {
    return actions.filter((a) => !a.roles || a.roles.length === 0);
  }
  return actions.filter((a) => {
    if (!a.roles || a.roles.length === 0) return true;
    return a.roles.includes(userRole);
  });
}

export function matchLocalActions(
  input: string,
  actions: CommandAction[],
  maxResults = 5,
): CommandAction[] {
  const lower = input.toLowerCase().trim();
  if (!lower) return [];

  const scored = actions
    .map((action) => {
      let score = 0;
      for (const kw of action.keywords) {
        if (lower === kw) {
          score = 100;
          break;
        }
        if (kw.includes(lower) || lower.includes(kw)) {
          score = Math.max(score, 70);
        }
        const kwWords = kw.split(" ");
        const inputWords = lower.split(" ");
        const overlap = inputWords.filter((w) =>
          kwWords.some((kw2) => kw2.includes(w) || w.includes(kw2))
        ).length;
        if (overlap > 0) {
          score = Math.max(score, (overlap / inputWords.length) * 60);
        }
      }
      if (action.title.toLowerCase().includes(lower)) {
        score = Math.max(score, 50);
      }
      return { action, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, maxResults).map((s) => s.action);
}

// ── Test hook (Phase 5 — used only in vitest/playwright) ────────────
export function __resetRegistry(): void {
  _registry.clear();
}

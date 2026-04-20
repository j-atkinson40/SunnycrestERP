/**
 * Phase 5 — ActionRegistryEntry is the canonical frontend action type.
 *
 * Supersedes the ad-hoc `CommandAction` shape from the legacy
 * `core/actionRegistry.ts`. `CommandAction` is retained as the
 * *render-time* shape consumed by `CommandBar.tsx` / `SmartPlantCommandBar.tsx`
 * — every `ActionRegistryEntry` produces a `CommandAction` via
 * `toCommandAction()` in `registry.ts`. The legacy
 * `core/commandBarQueryAdapter.ts` is the other producer of
 * `CommandAction` objects (for server-sourced results).
 *
 * New fields over the legacy `CommandAction`:
 *   - `permission` / `required_module` / `required_extension` — backend
 *     parity with `ActionRegistryEntry` in
 *     `app/services/command_bar/registry.py`.
 *   - `handler` / `playwright_step_id` / `workflow_id` — routing metadata
 *     for Phase 5 triage + future embedded-action dispatch.
 *   - `supports_nl_creation` / `nl_aliases` — Phase 4 NL overlay wiring.
 *     Authoritative source; `detectNLIntent.ts` derives its pattern list
 *     from entries flagged `supports_nl_creation`.
 *   - `keyboard_shortcut` — persisted shortcut hint surfaced in UI.
 */

export type ActionKind =
  | "navigate"
  | "create"
  | "search_result"
  | "action"
  | "saved_view"
  | "workflow"
  | "view"
  | "ask"
  | "answer"
  | "document"
  | "ask_ai"
  | "triage";

export interface ActionRegistryEntry {
  // Identity
  id: string;
  title: string;
  subtitle?: string;
  icon: string;
  kind: ActionKind;

  // Discovery
  keywords: string[];
  /** Phase 4 natural-language alias list (verb-less, e.g. "task"). */
  nl_aliases?: string[];

  // Gating
  /** Role slug list; empty = visible to all authenticated users. */
  roles: string[];
  /** Preset vertical the entry belongs to (manufacturing / funeral_home / cross). */
  vertical: "manufacturing" | "funeral_home" | "cemetery" | "crematory" | "cross";
  /** Optional permission gate (matches backend permission slug). */
  permission?: string;
  /** Optional company module gate. */
  required_module?: string;
  /** Optional tenant-extension gate. */
  required_extension?: string;

  // Routing / invocation
  route?: string;
  handler?: string;
  playwright_step_id?: string;
  workflow_id?: string;
  /** Phase 4: signals that typing "new <alias> ..." should open the NL overlay. */
  supports_nl_creation?: boolean;
  /** Phase 1: first-step preview for workflow entries. */
  first_step_preview?: string;

  // UX affordances
  keyboard_shortcut?: string;
  display_order?: number;
  enabled?: boolean;
}

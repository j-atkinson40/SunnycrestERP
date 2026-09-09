/**
 * Fragment contract — frontend mirror of `app/services/fragments/types.py`.
 *
 * Per DECISIONS 2026-09-04 ("Prose fragments declare four things or they don't
 * ship"). The shapes here are the wire contract for the note surface; any
 * change to one side requires a coordinated change to the other, in the manner
 * of `types/pulse.ts`.
 *
 * ⚠️ THE PAYLOAD IS A RENAME, NOT A REBUILD. `FragmentPayload` is
 * `IntelligenceStream` (`types/pulse.ts:64-71`) under fragment terminology. The
 * salvage investigation (`docs/investigations/2026-09-04-pulse-salvage.md`)
 * established that the body — synthesized prose plus typed entity links plus a
 * priority — was already correct, and that the four DECLARATIONS were what was
 * missing. `AnomalyIntelligenceStream.tsx` already renders this shape as prose
 * with inline chips.
 *
 * ⚠️ PULSE RENDERING IS DELIBERATELY UNTOUCHED. The rename is additive: the old
 * names stay where they are and keep working, because changing Pulse rendering
 * is out of this sub-arc's scope and Pulse is retired wholesale by the surface
 * arc rather than migrated. `_PayloadShapesAgree` below is a compile-time link
 * between the two names — if either shape drifts, `tsc` fails rather than the
 * two quietly diverging until the surface arc discovers it.
 */

import type { IntelligenceStream, ReferencedItem } from "@/types/pulse";

/** What a fragment opens. Mirrors `TargetSurface` in the Python contract.
 *
 *  ⚠️ NAME COLLISION: a DIFFERENT `TargetSurface` exists at
 *  `lib/widget-builder/types/composition-blob.ts`
 *  ("focus_canvas" | "page_canvas" | "palette_preview") — that one is
 *  the widget-builder's variant-authoring target. Unrelated concept,
 *  same name. Noted rather than renamed; a rename is its own change. */
export type TargetSurface = "peek" | "focus" | "window";

/**
 * Prompt fragments demand resolution and have NO dismiss path per DECISIONS
 * 2026-09-04 ("Prompts leave the note by resolution or dated deferral, never
 * silently"). Non-prompt fragments inform, and exit by dismiss.
 */
export type FragmentKind = "prompt" | "non_prompt";

/** One typed link inside a fragment's prose — a MEASURED claim. */
export type FragmentReference = ReferencedItem;

/** The fragment body. Renamed from `IntelligenceStream`; shape unchanged. */
export interface FragmentPayload {
  title: string;
  synthesized_text: string;
  referenced_items: FragmentReference[];
  priority: number;
}

/**
 * Compile-time proof that the rename is a rename.
 *
 * `IntelligenceStream` carries `stream_id` and `layer` in addition to the
 * payload fields; those are Pulse's composition bookkeeping and do not survive
 * into the fragment contract. What must not drift is the BODY — title, prose,
 * references, priority. If any of those four change shape on either side, this
 * assignment stops type-checking.
 */
type _PayloadBodyOf<T> = Pick<
  T,
  Extract<keyof T, "title" | "synthesized_text" | "referenced_items" | "priority">
>;
export type PayloadShapesAgree = _PayloadBodyOf<IntelligenceStream> extends
  _PayloadBodyOf<FragmentPayload>
  ? true
  : never;

/** Forces the assertion above to be evaluated rather than merely declared. A
 *  type alias alone is erased; this const makes drift a build failure. */
export const PAYLOAD_SHAPES_AGREE: PayloadShapesAgree = true;

/** (4) END TRANSITION — present iff `kind === "prompt"`. */
export interface EndTransition {
  entity_kind: string;
  resolved_when: string;
  past_tense: string;
}

/** A registered fragment type, as the note surface sees it. */
export interface FragmentDeclaration {
  fragment_id: string;
  label: string;
  kind: FragmentKind;
  /** (3) TARGET — type-level half. The scope half rides on the instance. */
  target_surface: TargetSurface;
  target_key: string;
  end_transition: EndTransition | null;
  /** Derived server-side: only non-prompt fragments may be dismissed. */
  dismissible: boolean;
}

/** One emitted fragment instance. */
export interface FragmentInstance {
  instance_key: string;
  payload: FragmentPayload;
  /**
   * (3) SCOPE — carried into whatever the fragment opens. Required non-empty
   * server-side: a fragment opens the scheduling Focus already scoped to
   * tomorrow, not a generic surface the user then filters.
   */
  scope: Record<string, unknown>;
}

/** A declaration paired with one of its instances. */
export interface EmittedFragment {
  declaration: FragmentDeclaration;
  instance: FragmentInstance;
}

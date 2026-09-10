/**
 * Fragment contract — frontend mirror of `app/services/fragments/types.py`.
 *
 * Per DECISIONS 2026-09-04 ("Prose fragments declare four things or they don't
 * ship"). The shapes here are the wire contract for the note surface; any
 * change to one side requires a coordinated change to the other.
 *
 * THE PAYLOAD WAS A RENAME, NOT A REBUILD. `FragmentPayload` was
 * `IntelligenceStream` under fragment terminology. The salvage investigation
 * established that the body — synthesized prose, typed entity links, a
 * priority — was already correct and that the four DECLARATIONS were missing.
 *
 * ⚠️ PULSE IS GONE AS OF 2026-09-10, and the paragraph that used to sit here
 * said its rendering was "deliberately untouched" and that the old names "stay
 * where they are and keep working." Neither is true now. The rename is no
 * longer additive; this file is the only home of these shapes.
 *
 * ──────────────────────────────────────────────────────────────────────
 * ⚠️ THIS FILE HAS ZERO IMPORTERS AND IS STALE IN TWO WAYS. Surfaced rather
 * than fixed or quietly left, because both are decisions the note arc has
 * already taken on the PYTHON side and this mirror never followed:
 *
 *   `EndTransition.past_tense` is a single template. The contract replaced it
 *     with per-outcome `outcomes: Outcome[]`, because one template cannot
 *     carry four terminal states (done / cancelled / acknowledged / dismissed).
 *   `FragmentInstance.scope` is one mapping. The contract split it into
 *     `predicate` (URL-carryable, re-derives) and `expansion` (payload only,
 *     never a URL key).
 *
 * A mirror nothing imports, describing a contract that moved twice, is a
 * document pretending to be code. Either it acquires a consumer and is brought
 * up to date, or it is deleted. Not decided here.
 */

/**
 * ⚠️ `ReferencedItem` MOVED HERE 2026-09-10, when Pulse was retired.
 *
 * It was imported from `@/types/pulse`. That module is gone; this shape was
 * always the fragment's, wearing Pulse's address because Pulse was written
 * first. Definition is byte-identical to the one it replaces.
 */
export interface ReferencedItem {
  /** "anomaly" | "delivery" | "task" | etc. The renderer dispatches on kind. */
  kind: string;
  entity_id: string;
  label: string;
  href: string | null;
}

/** What a fragment opens. Mirrors `TargetSurface` in the Python contract. */
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
/**
 * ⚠️ THE ASSERTION WAS RETIRED WITH PULSE, 2026-09-10, NOT RELOCATED.
 *
 * `PayloadShapesAgree` / `PAYLOAD_SHAPES_AGREE` compared this payload's body
 * against `IntelligenceStream`'s and failed the build if either drifted. It
 * existed to prove that the rename WAS a rename while both shapes were live.
 *
 * Both are not live any more. Keeping a copy of `IntelligenceStream` in this
 * file purely so the assertion still compiled would have preserved the guard
 * by manufacturing the thing it guards against — a hole with a guard on it,
 * where an absent field is not a hole. There is nothing left to drift FROM,
 * so the check is deleted rather than made vacuous.
 *
 * `_PayloadBodyOf` went with it; it had no other caller.
 */

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

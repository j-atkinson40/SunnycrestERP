/**
 * Personalization Studio canonical types — Phase 1B canvas implementation.
 *
 * Per §3.26.11.12.19 Personalization Studio canonical category +
 * §3.26.11.12 Generation Focus canon: this module mirrors the canonical
 * service substrate types from Phase 1A canonical-pattern-establisher
 * (`backend/app/models/generation_focus_instance.py` +
 * `backend/app/services/personalization_studio/instance_service.py`).
 *
 * **Canonical 4-options vocabulary post-r74** per §3.26.11.12.19.2 +
 * Step 0 Migration r74:
 *   - `legacy_print` (canonical; unchanged from pre-r74)
 *   - `physical_nameplate` (canonical refinement of pre-r74 `nameplate`)
 *   - `physical_emblem` (canonical refinement of pre-r74 `cover_emblem`)
 *   - `vinyl` (canonical; was pre-r74 `lifes_reflections`)
 *
 * **Canonical canvas state shape** per Phase 1A discovery output
 * Section 2a + canonical-pattern-establisher discipline:
 *
 * Phase 1A canonical-pattern-establisher discipline: Step 2 (Urn Vault
 * Personalization Studio) inherits canonical types via discriminator
 * differentiation; canvas state shape may differ per template_type
 * (urn vault has urn-specific fields), but the canonical type system
 * + service substrate is canonically shared.
 */

// ─────────────────────────────────────────────────────────────────────
// Canonical enumerations — canonical post-r74 vocabulary
// ─────────────────────────────────────────────────────────────────────

/** Generation Focus template type per Phase 1A pattern-establisher
 *  plus Step 2 substrate-consumption-follower extension. Future
 *  Personalization Studio templates extend per §3.26.11.12.19.6 scope
 *  freeze. */
export type TemplateType =
  | "burial_vault_personalization_studio"
  | "urn_vault_personalization_studio"

export const TEMPLATE_TYPES: readonly TemplateType[] = [
  "burial_vault_personalization_studio",
  "urn_vault_personalization_studio",
] as const

/** Canonical 3-value authoring_context discriminator per
 *  §3.26.11.12.19.3 Q3 baked canonical. */
export type AuthoringContext =
  | "funeral_home_with_family"
  | "manufacturer_without_family"
  | "manufacturer_from_fh_share"

export const AUTHORING_CONTEXTS: readonly AuthoringContext[] = [
  "funeral_home_with_family",
  "manufacturer_without_family",
  "manufacturer_from_fh_share",
] as const

/** Canonical 4-state lifecycle enumeration per §3.26.11.12.4-5
 *  closure semantics. */
export type LifecycleState = "active" | "draft" | "committed" | "abandoned"

export const LIFECYCLE_STATES: readonly LifecycleState[] = [
  "active",
  "draft",
  "committed",
  "abandoned",
] as const

/** Canonical linked_entity_type enumeration per Q3 canonical pairing. */
export type LinkedEntityType = "fh_case" | "sales_order" | "document_share"

/** Q3 canonical authoring_context ↔ linked_entity_type pairing per
 *  §3.26.11.12.19.3 baked canonical. */
export const AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE: Record<
  AuthoringContext,
  LinkedEntityType
> = {
  funeral_home_with_family: "fh_case",
  manufacturer_without_family: "sales_order",
  manufacturer_from_fh_share: "document_share",
}

/** Canonical family approval status per Q7b-reframed canonical. */
export type FamilyApprovalStatus =
  | "not_requested"
  | "requested"
  | "approved"
  | "rejected"

/** Canonical 4-options vocabulary per §3.26.11.12.19.2 post-r74.
 *
 *  - `legacy_print` — printed paper artifact insert (legacy_standard +
 *    legacy_custom canonical sub-categorizations preserved within this
 *    canonical option type at task substrate per r74 migration docstring).
 *  - `physical_nameplate` — engraved metal nameplate (canonical
 *    refinement of pre-r74 `nameplate`).
 *  - `physical_emblem` — physical emblem affixed to vault cover
 *    (canonical refinement of pre-r74 `cover_emblem`).
 *  - `vinyl` — vinyl-applied personalization (canonical; was
 *    pre-r74 `lifes_reflections` — Wilbert tenant displays
 *    "Life's Reflections" per per-tenant Workshop Tune mode display
 *    label customization).
 */
export type CanonicalOptionType =
  | "legacy_print"
  | "physical_nameplate"
  | "physical_emblem"
  | "vinyl"

export const CANONICAL_OPTION_TYPES: readonly CanonicalOptionType[] = [
  "legacy_print",
  "physical_nameplate",
  "physical_emblem",
  "vinyl",
] as const

/** Canonical default display labels per r74 — per-tenant Workshop Tune
 *  mode customization stored at `Company.settings_json.personalization_display_labels`.
 *  Frontend should resolve display labels via tenant settings before
 *  falling back to these canonical defaults. */
export const DEFAULT_DISPLAY_LABELS: Record<CanonicalOptionType, string> = {
  legacy_print: "Legacy Print",
  physical_nameplate: "Nameplate",
  physical_emblem: "Emblem",
  vinyl: "Vinyl",
}

// ─────────────────────────────────────────────────────────────────────
// Canonical canvas state shape — Phase 1A canonical-pattern-establisher
// ─────────────────────────────────────────────────────────────────────

/** Canonical canvas-element identifier — opaque UUID. */
export type CanvasElementId = string

/** Canvas-element type per discovery output Section 2a.
 *
 *  Phase 1B pattern-establisher: each element type renders via
 *  CanvasElement component dispatch. Step 2 substrate-consumption-
 *  follower extends with ``urn_product`` element type per Phase 2A
 *  shape; canonical 4-options vocabulary element types preserved per
 *  §3.26.11.12.19.6 scope freeze. */
export type CanvasElementType =
  | "vault_product" // Selected vault product reference (Step 1)
  | "urn_product" // Selected urn product reference (Step 2)
  | "emblem" // Physical or vinyl emblem placement
  | "nameplate" // Physical nameplate text + position
  | "name_text" // Decedent name text element
  | "date_text" // Birth/death date text element
  | "legacy_print_artifact" // Printed paper insert reference

/** Canonical positioned canvas element. Compositor x/y stored in
 *  canonical canvas coordinate space; canonical render-time anchor
 *  resolution NOT used for canvas elements (canvas is fixed-size
 *  authoring surface per Phase 1B canvas implementation). */
export interface CanvasElement {
  id: CanvasElementId
  element_type: CanvasElementType
  x: number
  y: number
  width?: number
  height?: number
  /** Per-element-type configuration data — element rendering depends on
   *  this canonical shape per element_type discriminator. */
  config?: Record<string, unknown>
}

/** Canonical per-option-type configuration data per canvas state.
 *  When an option type is active, its dict carries per-option-type
 *  canonical fields; null means the option type is canonically inactive
 *  in this canvas state. */
export interface CanvasOptions {
  legacy_print: { print_name?: string } | null
  physical_nameplate: Record<string, never> | null
  physical_emblem: Record<string, never> | null
  vinyl: { symbol?: string } | null
}

/** Canonical canvas state shape per Phase 1A canonical-pattern-establisher
 *  + Phase 1B canvas implementation.
 *
 *  Persisted to canonical Document substrate per D-9 polymorphic
 *  substrate. Stored as canonical JSON blob at `documents.storage_key`
 *  with `mime_type="application/json"`.
 *
 *  Canonical 4-options vocabulary post-r74 per §3.26.11.12.19.2.
 */
export interface CanvasState {
  /** Canonical schema version; bumps as canvas state shape evolves. */
  schema_version: number
  /** Canonical template_type discriminator — matches owning instance. */
  template_type: TemplateType
  /** Canonical canvas layout: positioned compositor elements. */
  canvas_layout: {
    elements: CanvasElement[]
  }
  /** Selected vault product reference. Present on
   *  ``burial_vault_personalization_studio`` per Phase 1A pattern-
   *  establisher; absent on ``urn_vault_personalization_studio`` per
   *  Step 2 substrate-consumption-follower (urn vault uses
   *  ``urn_product`` slot instead). */
  vault_product?: {
    vault_product_id: string | null
    vault_product_name: string | null
  }
  /** Step 2 substrate-consumption-follower: selected urn product
   *  reference. Present on ``urn_vault_personalization_studio`` per
   *  Phase 2A factory dispatch; absent on
   *  ``burial_vault_personalization_studio``. */
  urn_product?: {
    urn_product_id: string | null
    urn_product_name: string | null
  }
  /** Canonical emblem key per per-tenant catalog selection. */
  emblem_key: string | null
  /** Canonical decedent name display string. */
  name_display: string | null
  /** Canonical font key per per-tenant catalog selection. */
  font: string | null
  /** Canonical birth-date display string. */
  birth_date_display: string | null
  /** Canonical death-date display string. */
  death_date_display: string | null
  /** Canonical nameplate text. */
  nameplate_text: string | null
  /** Canonical 4-options vocabulary post-r74 per §3.26.11.12.19.2. */
  options: CanvasOptions
  /** Canonical family approval status per Q7b-reframed canonical. */
  family_approval_status: FamilyApprovalStatus
}

// ─────────────────────────────────────────────────────────────────────
// Canonical Generation Focus instance — Phase 1A canonical-pattern-
// establisher entity model
// ─────────────────────────────────────────────────────────────────────

/** Canonical Generation Focus instance metadata. Mirrors backend
 *  `GenerationFocusInstance` model per Phase 1A canonical-pattern-
 *  establisher discipline. Step 2 inherits via discriminator
 *  differentiation. */
export interface GenerationFocusInstance {
  id: string
  company_id: string
  template_type: TemplateType
  authoring_context: AuthoringContext
  lifecycle_state: LifecycleState
  linked_entity_type: LinkedEntityType
  linked_entity_id: string
  document_id: string | null
  opened_at: string
  opened_by_user_id: string | null
  last_active_at: string
  committed_at: string | null
  committed_by_user_id: string | null
  abandoned_at: string | null
  abandoned_by_user_id: string | null
  family_approval_status: FamilyApprovalStatus | null
  family_approval_requested_at: string | null
  family_approval_decided_at: string | null
}

// ─────────────────────────────────────────────────────────────────────
// Canonical API request/response shapes — mirror backend Pydantic models
// ─────────────────────────────────────────────────────────────────────

export interface OpenInstanceRequest {
  template_type: TemplateType
  authoring_context: AuthoringContext
  linked_entity_id: string
}

export interface CanvasStateResponse {
  /** Canvas state JSON or null when no canvas commit has been made. */
  canvas_state: CanvasState | null
}

export interface CommitCanvasStateRequest {
  canvas_state: CanvasState
}

export interface CommitCanvasStateResponse {
  document_version_id: string
  version_number: number
  storage_key: string
}

// ─────────────────────────────────────────────────────────────────────
// Canonical AI-extraction-review pipeline shapes — Phase 1C canonical
// per DESIGN_LANGUAGE §14.14.3 + Anti-pattern 1 (auto-commit on
// extraction confidence rejected) discipline
// ─────────────────────────────────────────────────────────────────────

/** Canonical confidence tier per §14.14.3 visual canon thresholds.
 *
 *  - `high` (≥0.85) — canonical success chrome
 *  - `medium` (0.70-0.85) — canonical warning chrome
 *  - `low` (<0.70) — canonical error chrome
 *
 *  Backend service annotates canonical line items with canonical
 *  `confidence_tier` per ``ai_extraction_review.confidence_tier``
 *  helper. Chrome substrate consumes canonical tier for visual
 *  treatment ONLY per canonical operator agency discipline at
 *  §3.26.11.12.16 Anti-pattern 1.
 */
export type ConfidenceTier = "high" | "medium" | "low"

export const CONFIDENCE_THRESHOLD_HIGH = 0.85
export const CONFIDENCE_THRESHOLD_MEDIUM = 0.7

/** Canonical confidence tier helper mirroring backend service substrate.
 *  Chrome substrate consumers use this for client-side rendering when
 *  backend tier annotation is unavailable. */
export function confidenceTier(confidence: number): ConfidenceTier {
  if (confidence >= CONFIDENCE_THRESHOLD_HIGH) return "high"
  if (confidence >= CONFIDENCE_THRESHOLD_MEDIUM) return "medium"
  return "low"
}

/** Canonical confidence-scored line item per §14.14.3 visual canon.
 *
 *  Mirrors backend ``SuggestionLineItem`` Pydantic model. Canonical
 *  anti-pattern guard: confidence is canonically required; canonical
 *  chrome substrate consumes canonical line items via canonical
 *  Pattern 2 sub-cards per §14.14.3.
 */
export interface SuggestionLineItem {
  line_item_key: string | null
  value: unknown
  confidence: number
  rationale: string | null
  confidence_tier: ConfidenceTier
}

/** Canonical AI-extraction-review pipeline response payload.
 *
 *  Mirrors backend ``SuggestionPayloadResponse`` Pydantic model.
 *  All three canonical AI-extraction-review endpoints return this
 *  canonical shape — canonical-pattern-establisher discipline at
 *  canonical chrome substrate consumes single canonical payload
 *  shape across canonical layout / text style / decedent extraction
 *  suggestion types.
 */
export interface SuggestionPayload {
  line_items: SuggestionLineItem[]
  execution_id: string | null
  model_used: string | null
  latency_ms: number | null
}

/** Canonical Phase 2c-0b multimodal content block shape.
 *
 *  Canonical operator-uploaded source materials canonical at canonical
 *  ``extract_decedent_info`` endpoint substrate. Mirrors canonical
 *  Anthropic content_block shape per
 *  ``intelligence_service._validate_content_blocks``.
 */
export interface ContentBlock {
  type: "image" | "document"
  source: {
    type: "base64"
    media_type: string
    data: string
  }
}

/** Canonical suggest_text_style request body — canonical family
 *  preferences canonical optional. */
export interface SuggestTextStyleRequest {
  family_preferences?: string
}

/** Canonical extract_decedent_info request body — canonical
 *  multimodal content_blocks canonical at Phase 2c-0b substrate. */
export interface ExtractDecedentInfoRequest {
  content_blocks: ContentBlock[]
  context_summary?: string
}

/** Canonical AI-extraction-review pipeline suggestion type discriminator. */
export type SuggestionType =
  | "suggest_layout"
  | "suggest_text_style"
  | "extract_decedent_info"

/** Canonical operator-decision outcome per canonical Confirm + Edit +
 *  Reject + Skip affordances per §14.14.3. */
export type LineItemDecision = "confirm" | "edit" | "reject" | "skip"


// ─────────────────────────────────────────────────────────────────────
// Canonical canvas viewport tier — Phase A Session 3.7 + 3.7.1 + 3.8
// canonical three-tier responsive cascade carried forward to Phase 1B
// ─────────────────────────────────────────────────────────────────────

/** Canonical three-tier responsive cascade per Phase A Session 3.7-3.8
 *  canonical (canvas | stack | icon). Phase 1B canvas implementation
 *  inherits canonical tier dispatch from Phase A canvas substrate. */
export type CanvasTier = "canvas" | "stack" | "icon"

// ─────────────────────────────────────────────────────────────────────
// Canonical canvas element factory — Phase 1B helpers
// ─────────────────────────────────────────────────────────────────────

/** Empty canvas state factory per Phase 1A pattern-establisher shape +
 *  Step 2 substrate-consumption-follower extension. Mirrors backend
 *  `instance_service._empty_canvas_state` 1:1. */
export function emptyCanvasState(template_type: TemplateType): CanvasState {
  if (template_type === "burial_vault_personalization_studio") {
    return {
      schema_version: 1,
      template_type,
      canvas_layout: { elements: [] },
      vault_product: {
        vault_product_id: null,
        vault_product_name: null,
      },
      emblem_key: null,
      name_display: null,
      font: null,
      birth_date_display: null,
      death_date_display: null,
      nameplate_text: null,
      options: {
        legacy_print: null,
        physical_nameplate: null,
        physical_emblem: null,
        vinyl: null,
      },
      family_approval_status: "not_requested",
    }
  }
  if (template_type === "urn_vault_personalization_studio") {
    // Step 2 substrate-consumption-follower shape: urn product replaces
    // vault product slot per Phase 2A factory dispatch; canonical 4-
    // options vocabulary preserved per §3.26.11.12.19.6 scope freeze.
    return {
      schema_version: 1,
      template_type,
      canvas_layout: { elements: [] },
      urn_product: {
        urn_product_id: null,
        urn_product_name: null,
      },
      emblem_key: null,
      name_display: null,
      font: null,
      birth_date_display: null,
      death_date_display: null,
      nameplate_text: null,
      options: {
        legacy_print: null,
        physical_nameplate: null,
        physical_emblem: null,
        vinyl: null,
      },
      family_approval_status: "not_requested",
    }
  }
  // Future Personalization Studio templates extend per
  // §3.26.11.12.19.6 scope freeze.
  throw new Error(
    `Unknown template_type ${template_type} — canonical Personalization ` +
      `Studio category values are 'burial_vault_personalization_studio' ` +
      `(Step 1) + 'urn_vault_personalization_studio' (Step 2). Future ` +
      `templates extend via canon session per §3.26.11.12.19.6.`,
  )
}

// ─────────────────────────────────────────────────────────────────────
// Phase 1E — Family approval flow types
//
// Per §3.26.11.12.21 reviewer-paths canonical (3 outcomes:
// approve / request_changes / decline) + §2.5 Portal Extension
// Pattern + Path B platform_action_tokens substrate.
// ─────────────────────────────────────────────────────────────────────

/** Canonical 3-outcome family-approval reviewer-paths per
 *  §3.26.11.12.21. `request_changes` + `decline` require
 *  completion_note rationale. */
export type FamilyApprovalOutcome =
  | "approve"
  | "request_changes"
  | "decline"

/** Canonical action_status enum stored on the action object inside
 *  `generation_focus_instances.action_payload.actions[]`. */
export type FamilyApprovalActionStatus =
  | "pending"
  | "approved"
  | "changes_requested"
  | "declined"

/** FH-director-initiated request body. */
export interface RequestFamilyApprovalRequest {
  family_email: string
  family_first_name?: string | null
  optional_message?: string | null
}

/** FH-director-initiated response. Token NOT included (canonical
 *  kill-the-portal — token routes only via family email). */
export interface RequestFamilyApprovalResponse {
  instance_id: string
  action_idx: number
  family_email: string
  family_approval_status: string
  delivery_id: string | null
}

/** Canonical SpaceConfig modifier slice surfaced to the family portal
 *  frontend. The frontend uses these flags to gate chrome (bounded
 *  affordances filtered, FH-tenant-branded surface). */
export interface FamilyPortalSpaceShape {
  template_id: string
  name: string
  icon: string
  accent: string
  access_mode: "portal_external"
  tenant_branding: boolean
  write_mode: "limited"
  session_timeout_minutes: number
}

/** Tenant branding payload (wash, not reskin per §10.6). */
export interface FamilyPortalBrandingShape {
  display_name: string
  logo_url: string | null
  brand_color: string
}

/** Read-only canvas snapshot for family approval surface. */
export interface FamilyPortalCanvasSnapshot {
  canvas_state: CanvasState | null
  version_number: number | null
}

/** GET response — full family-portal-rendering payload. */
export interface FamilyApprovalContextResponse {
  instance_id: string
  decedent_name: string | null
  fh_director_name: string | null
  action_status: FamilyApprovalActionStatus
  outcomes: readonly FamilyApprovalOutcome[]
  requires_completion_note: readonly FamilyApprovalOutcome[]
  canvas: FamilyPortalCanvasSnapshot
  space: FamilyPortalSpaceShape
  branding: FamilyPortalBrandingShape
}

/** POST request body — family decision. */
export interface FamilyApprovalCommitRequest {
  outcome: FamilyApprovalOutcome
  completion_note?: string | null
}

/** POST response — terminal action state.
 *
 *  Phase 1F extends with canonical post-commit dispatch outcome at
 *  `share_dispatch` field. Surfaces canonical D-6 grant fire result for
 *  canonical FE chrome consumption (FH-director PTR consent error
 *  surface when grant fire fails). Field is null on non-approve
 *  outcomes (request_changes / decline do NOT fire cross-tenant share). */
export interface FamilyApprovalCommitResponse {
  instance_id: string
  outcome: FamilyApprovalOutcome
  action_status: Exclude<FamilyApprovalActionStatus, "pending">
  family_approval_status: string | null
  lifecycle_state: string
  share_dispatch?: ShareDispatchResponse | null
}

/** Canonical outcome list — exported for FE chrome rendering.
 *  Mirrors `family_approval.ACTION_OUTCOMES_FAMILY_APPROVAL`. */
export const FAMILY_APPROVAL_OUTCOMES: readonly FamilyApprovalOutcome[] = [
  "approve",
  "request_changes",
  "decline",
] as const

/** Outcomes requiring completion_note per canonical-rationale
 *  discipline (mirrors `family_approval.REQUIRES_COMPLETION_NOTE`). */
export const FAMILY_APPROVAL_REQUIRES_NOTE: readonly FamilyApprovalOutcome[] = [
  "request_changes",
  "decline",
] as const

// ─────────────────────────────────────────────────────────────────────
// Phase 1F — DocumentShare grant + manufacturer-side from-share types
//
// Per §3.26.11.12.19.4 cross-tenant DocumentShare grant timing canonical
// (Q2 baked: full disclosure per-instance via grant) + §3.26.11.12.19.3
// Q3 canonical pairing (`manufacturer_from_fh_share` ↔
// `linked_entity_type="document_share"`).
// ─────────────────────────────────────────────────────────────────────

/** Canonical 5-state DocumentShare dispatch outcome surfaced via the
 *  Phase 1E commit response. Matches backend
 *  `PostCommitDispatchOutcome.OUTCOME_*` vocabulary verbatim. */
export type ShareDispatchOutcome =
  | "granted"
  | "ptr_missing"
  | "consent_default"
  | "consent_pending_outbound"
  | "consent_pending_inbound"

/** Canonical share dispatch payload returned on the canonical Phase 1E
 *  approve outcome. Surfaces canonical FH-director-side PTR consent
 *  error chrome data when the dispatch fails canonical PTR consent
 *  precondition. */
export interface ShareDispatchResponse {
  outcome: ShareDispatchOutcome
  share_id: string | null
  target_company_id: string | null
  target_company_name: string | null
  relationship_id: string | null
  error_detail: string | null
}

/** Canonical Mfg-tenant from-share entry point response. */
export interface FromShareInstanceResponse {
  instance: GenerationFocusInstance
  canvas_state: CanvasState | null
  document_share_id: string
  owner_company_id: string
  owner_company_name: string | null
  granted_at: string
  decedent_name: string | null
}

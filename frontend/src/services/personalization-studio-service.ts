/**
 * Personalization Studio frontend service — Phase 1B canvas implementation.
 *
 * Per §3.26.11.12.19 Personalization Studio canonical category +
 * §3.26.11.12 Generation Focus canon: this service mirrors the
 * canonical FastAPI endpoint set at `/api/v1/personalization-studio/*`
 * via axios client.
 *
 * **Canonical canvas commit boundary** per Phase A Session 3.8.3
 * canonical compositor pattern: canvas commits happen at canonical
 * edit-finish boundary (NOT every drag frame). Frontend canonical
 * operator agency required at canonical commit affordance per
 * §3.26.11.12.16 Anti-pattern 1.
 */

import axios from "axios"

import apiClient from "@/lib/api-client"
import type {
  CanvasState,
  CanvasStateResponse,
  CommitCanvasStateRequest,
  CommitCanvasStateResponse,
  ExtractDecedentInfoRequest,
  FamilyApprovalCommitRequest,
  FamilyApprovalCommitResponse,
  FamilyApprovalContextResponse,
  FamilyApprovalOutcome,
  FromShareInstanceResponse,
  GenerationFocusInstance,
  LifecycleState,
  LinkedEntityType,
  OpenInstanceRequest,
  RequestFamilyApprovalRequest,
  RequestFamilyApprovalResponse,
  ShareDispatchResponse,
  SuggestionPayload,
  SuggestTextStyleRequest,
  TemplateType,
} from "@/types/personalization-studio"

const BASE_PATH = "/personalization-studio"

/** Open canonical Generation Focus instance.
 *
 *  Creates canonical `GenerationFocusInstance` row + canonical
 *  `Document` substrate row. First `DocumentVersion` created on first
 *  canvas commit per §3.26.11.12.5 substrate-consumption canonical.
 */
export async function openInstance(
  body: OpenInstanceRequest,
): Promise<GenerationFocusInstance> {
  const res = await apiClient.post<GenerationFocusInstance>(
    `${BASE_PATH}/instances`,
    body,
  )
  return res.data
}

/** Fetch canonical Generation Focus instance metadata. Tenant-scoped
 *  per canonical multi-tenant isolation; cross-tenant access returns
 *  canonical existence-hiding 404. */
export async function getInstance(
  instanceId: string,
): Promise<GenerationFocusInstance> {
  const res = await apiClient.get<GenerationFocusInstance>(
    `${BASE_PATH}/instances/${instanceId}`,
  )
  return res.data
}

/** Read canonical canvas state from canonical Document substrate.
 *
 *  Returns the current `DocumentVersion`'s canvas state JSON (most
 *  recently committed). Returns `canvas_state: null` when no commit
 *  has been made.
 */
export async function getCanvasState(
  instanceId: string,
): Promise<CanvasStateResponse> {
  const res = await apiClient.get<CanvasStateResponse>(
    `${BASE_PATH}/instances/${instanceId}/canvas-state`,
  )
  return res.data
}

/** Commit canonical canvas state to canonical Document substrate.
 *
 *  Per Phase A Session 3.8.3 canonical compositor pattern: canvas
 *  commits canonical at canonical edit-finish boundary. Each commit
 *  creates new `DocumentVersion` with `is_current=True` flip per
 *  canonical D-9 versioning. FH-vertical authoring context triggers
 *  canonical `case_merchandise.vault_personalization` JSONB
 *  denormalization (best-effort, server-side).
 */
export async function commitCanvasState(
  instanceId: string,
  canvasState: CanvasState,
): Promise<CommitCanvasStateResponse> {
  const body: CommitCanvasStateRequest = { canvas_state: canvasState }
  const res = await apiClient.post<CommitCanvasStateResponse>(
    `${BASE_PATH}/instances/${instanceId}/commit-canvas-state`,
    body,
  )
  return res.data
}

/** Commit canonical Generation Focus instance — canonical bounded-output
 *  closure. Transitions canonical lifecycle_state `active` → `committed`
 *  per §3.26.11.12.4. */
export async function commitInstance(
  instanceId: string,
): Promise<GenerationFocusInstance> {
  const res = await apiClient.post<GenerationFocusInstance>(
    `${BASE_PATH}/instances/${instanceId}/commit`,
  )
  return res.data
}

/** Abandon canonical Generation Focus instance. Canonical lifecycle
 *  abandon path per §3.26.11.12.5; symmetric with canonical `commit`
 *  path. */
export async function abandonInstance(
  instanceId: string,
): Promise<GenerationFocusInstance> {
  const res = await apiClient.post<GenerationFocusInstance>(
    `${BASE_PATH}/instances/${instanceId}/abandon`,
  )
  return res.data
}

// ─────────────────────────────────────────────────────────────────────
// Phase 1C — AI-extraction-review pipeline canonical
//
// Per §3.26.11.12.20 Generation Focus extraction adapter category +
// §3.26.11.12.21 operational modes + §3.26.11.12.16 Anti-pattern 1
// (auto-commit on extraction confidence rejected) + DESIGN_LANGUAGE
// §14.14.3 visual canon.
// ─────────────────────────────────────────────────────────────────────

/** Canonical operator-initiated canvas layout suggestion request.
 *
 *  Invokes canonical backend ``intelligence_service.execute()`` with
 *  canonical case data + canonical selected vault product + canonical
 *  4-options selections; returns canonical confidence-scored canvas
 *  layout suggestion line items for canonical AI-extraction-review
 *  chrome rendering per §14.14.3.
 *
 *  Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 1:
 *  service returns canonical line items only; canonical Confirm action
 *  canonical at chrome substrate applies canonical line item to canvas
 *  state via canonical operator agency.
 */
export async function suggestLayout(
  instanceId: string,
): Promise<SuggestionPayload> {
  const res = await apiClient.post<SuggestionPayload>(
    `${BASE_PATH}/instances/${instanceId}/suggest-layout`,
  )
  return res.data
}

/** Canonical operator-initiated text style suggestion request.
 *
 *  Invokes canonical backend ``intelligence_service.execute()`` with
 *  canonical deceased name + family preferences; returns canonical
 *  confidence-scored font + size + color suggestion line items.
 */
export async function suggestTextStyle(
  instanceId: string,
  body: SuggestTextStyleRequest = {},
): Promise<SuggestionPayload> {
  const res = await apiClient.post<SuggestionPayload>(
    `${BASE_PATH}/instances/${instanceId}/suggest-text-style`,
    body,
  )
  return res.data
}

/** Canonical operator-initiated multimodal decedent info extraction
 *  request.
 *
 *  Invokes canonical backend ``intelligence_service.execute()`` with
 *  canonical multimodal content_blocks (PDFs + images) per canonical
 *  Phase 2c-0b multimodal substrate. Returns canonical confidence-
 *  scored decedent extraction line items.
 *
 *  Canonical anti-pattern guard per §3.26.11.12.16 Anti-pattern 12:
 *  canonical AI-extraction-review pipeline single canonical
 *  architecture across canonical adapter source categories — canonical
 *  multimodal content_blocks substrate canonical at canonical extraction
 *  adapter category per §3.26.11.12.20.
 */
export async function extractDecedentInfo(
  instanceId: string,
  body: ExtractDecedentInfoRequest,
): Promise<SuggestionPayload> {
  const res = await apiClient.post<SuggestionPayload>(
    `${BASE_PATH}/instances/${instanceId}/extract-decedent-info`,
    body,
  )
  return res.data
}

/** List canonical Generation Focus instances for a linked entity.
 *
 *  Canonical query pattern per Phase 1A canonical-pattern-establisher:
 *  "what personalization Generation Focus instances exist for FH
 *  case X?" or "what instances exist for sales order Y?"
 *
 *  Filtered to caller's company_id for canonical multi-tenant isolation.
 */
export async function listInstancesForLinkedEntity(params: {
  linked_entity_type: LinkedEntityType
  linked_entity_id: string
  template_type?: TemplateType
  lifecycle_state?: LifecycleState
}): Promise<GenerationFocusInstance[]> {
  const res = await apiClient.get<GenerationFocusInstance[]>(
    `${BASE_PATH}/instances`,
    { params },
  )
  return res.data
}

// ─────────────────────────────────────────────────────────────────────
// Phase 1E — Family approval flow
// ─────────────────────────────────────────────────────────────────────

/** FH-director-initiated family-approval request.
 *
 *  Issues a Path B platform_action_token + dispatches the canonical
 *  `email.personalization_studio_family_approval_request` managed
 *  email template carrying the magic-link URL per §3.26.11.9 + Path B
 *  substrate consumption.
 */
export async function requestFamilyApproval(
  instanceId: string,
  body: RequestFamilyApprovalRequest,
): Promise<RequestFamilyApprovalResponse> {
  const res = await apiClient.post<RequestFamilyApprovalResponse>(
    `${BASE_PATH}/instances/${instanceId}/request-family-approval`,
    body,
  )
  return res.data
}

// ─────────────────────────────────────────────────────────────────────
// Family portal endpoints — PUBLIC (no JWT, no apiClient interceptor).
//
// Per §2.5.4 Anti-pattern 16 (cross-realm privilege bleed rejected):
// the magic-link token is the family's sole authentication factor.
// We use bare axios (no apiClient) to ensure no tenant-realm JWT is
// attached to portal requests.
// ─────────────────────────────────────────────────────────────────────

/** Resolve API base URL once for portal endpoints. Falls back to
 *  `/api/v1` when `VITE_API_URL` is unset (canonical dev shape). */
function _portalBaseUrl(): string {
  const envBase = import.meta.env?.VITE_API_URL?.replace(/\/$/, "")
  return `${envBase || ""}/api/v1`
}

/** GET — render family portal context (read-only canvas + 3-outcome
 *  action vocabulary). Throws on 401/410 (terminal token state). */
export async function getFamilyApprovalContext(
  tenantSlug: string,
  token: string,
): Promise<FamilyApprovalContextResponse> {
  const res = await axios.get<FamilyApprovalContextResponse>(
    `${_portalBaseUrl()}/portal/${encodeURIComponent(tenantSlug)}/personalization-studio/family-approval/${encodeURIComponent(token)}`,
  )
  return res.data
}

/** POST — commit family decision atomically. Token consumed on success;
 *  re-commit returns 409. */
export async function commitFamilyApproval(
  tenantSlug: string,
  token: string,
  body: FamilyApprovalCommitRequest,
): Promise<FamilyApprovalCommitResponse> {
  const res = await axios.post<FamilyApprovalCommitResponse>(
    `${_portalBaseUrl()}/portal/${encodeURIComponent(tenantSlug)}/personalization-studio/family-approval/${encodeURIComponent(token)}`,
    body,
  )
  return res.data
}

export type {
  FamilyApprovalOutcome,
  FamilyApprovalCommitRequest,
  FamilyApprovalCommitResponse,
  FamilyApprovalContextResponse,
  FromShareInstanceResponse,
  RequestFamilyApprovalRequest,
  RequestFamilyApprovalResponse,
  ShareDispatchResponse,
}


// ─────────────────────────────────────────────────────────────────────
// Phase 1F — Manufacturer-side from-share entry point
// ─────────────────────────────────────────────────────────────────────


/** Open canonical Generation Focus instance at canonical Mfg-tenant scope
 *  from canonical D-6 DocumentShare.
 *
 *  Per §3.26.11.12.19.3 Q3 canonical pairing
 *  (`manufacturer_from_fh_share` ↔ `linked_entity_type="document_share"`):
 *  Mfg-tenant operator clicks share-granted email link → service
 *  materializes Mfg-tenant-scoped GenerationFocusInstance pointing at
 *  the canonical D-6 DocumentShare. Idempotent — re-open returns
 *  canonical existing instance. */
export async function openInstanceFromShare(
  documentShareId: string,
): Promise<FromShareInstanceResponse> {
  const res = await apiClient.post<FromShareInstanceResponse>(
    `${BASE_PATH}/from-share/${encodeURIComponent(documentShareId)}`,
  )
  return res.data
}

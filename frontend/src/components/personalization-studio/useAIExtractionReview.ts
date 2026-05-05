/**
 * useAIExtractionReview — canonical operator-initiated AI-extraction-
 * review pipeline hook per Phase 1C canonical.
 *
 * **Canonical anti-pattern guards explicit at hook substrate**:
 *
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): canonical Confirm action canonical at hook substrate
 *   applies canonical line item to canvas state via canonical
 *   `applyLineItem`. Canonical confidence threshold does NOT trigger
 *   canonical auto-commit. Operator decides.
 *
 * - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
 *   rejected): canonical line items canonical at canonical service
 *   substrate; canonical hook consumes canonical line items via
 *   canonical service-layer call.
 *
 * **Canonical operator-decision actions**:
 *
 * - `confirm(lineItem)` — canonical Confirm action; applies canonical
 *   line item to canvas state via canonical `applyLineItem` dispatcher
 * - `edit(lineItem)` — canonical Edit action; opens canonical edit
 *   surface with canonical line item value as starting state
 * - `reject(lineItem)` — canonical Reject action; dismisses canonical
 *   line item without canvas state change
 * - `skip(lineItem)` — canonical Skip action; defers canonical line
 *   item review (canonical line item remains in payload but marked
 *   canonically deferred)
 */

import { useCallback, useState } from "react"

import {
  extractDecedentInfo,
  suggestLayout,
  suggestTextStyle,
} from "@/services/personalization-studio-service"
import type {
  CanvasElement,
  CanvasState,
  ExtractDecedentInfoRequest,
  LineItemDecision,
  SuggestionLineItem,
  SuggestionPayload,
  SuggestionType,
  SuggestTextStyleRequest,
} from "@/types/personalization-studio"

import { usePersonalizationCanvasState } from "./canvas-state-context"


/** Canonical per-line-item operator-decision tracking — local hook
 *  state. Per §3.26.11.12.16 Anti-pattern 11 guard: canonical operator-
 *  decision tracking is canonical hook-state-substrate ephemeral. */
export interface LineItemDecisionRecord {
  line_item_key: string | null
  decision: LineItemDecision
  /** Canonical edit-finished value when decision is `edit`. */
  edited_value?: unknown
}

export interface UseAIExtractionReviewState {
  /** Canonical pending suggestion type when one is in-flight or
   *  awaiting canonical operator review. */
  activeSuggestionType: SuggestionType | null
  /** Canonical confidence-scored payload from canonical service substrate. */
  payload: SuggestionPayload | null
  /** Canonical loading flag during canonical service-layer call. */
  isLoading: boolean
  /** Canonical error message from canonical service-layer call. */
  error: string | null
  /** Canonical per-line-item canonical operator-decision records. */
  decisions: LineItemDecisionRecord[]
}

export interface UseAIExtractionReviewValue extends UseAIExtractionReviewState {
  /** Canonical operator-initiated layout suggestion request. */
  requestSuggestLayout: () => Promise<void>
  /** Canonical operator-initiated text style suggestion request. */
  requestSuggestTextStyle: (
    body?: SuggestTextStyleRequest,
  ) => Promise<void>
  /** Canonical operator-initiated multimodal decedent info extraction. */
  requestExtractDecedentInfo: (
    body: ExtractDecedentInfoRequest,
  ) => Promise<void>
  /** Canonical Confirm action — applies canonical line item to canvas state. */
  confirm: (lineItem: SuggestionLineItem, editedValue?: unknown) => void
  /** Canonical Edit action — records canonical edit decision. */
  edit: (lineItem: SuggestionLineItem) => void
  /** Canonical Reject action — dismisses canonical line item. */
  reject: (lineItem: SuggestionLineItem) => void
  /** Canonical Skip action — defers canonical line item review. */
  skip: (lineItem: SuggestionLineItem) => void
  /** Canonical reset — clears canonical payload + decisions. */
  reset: () => void
}


export function useAIExtractionReview(
  instanceId: string,
): UseAIExtractionReviewValue {
  const canvasState = usePersonalizationCanvasState()
  const [state, setState] = useState<UseAIExtractionReviewState>({
    activeSuggestionType: null,
    payload: null,
    isLoading: false,
    error: null,
    decisions: [],
  })

  const reset = useCallback(() => {
    setState({
      activeSuggestionType: null,
      payload: null,
      isLoading: false,
      error: null,
      decisions: [],
    })
  }, [])

  const _runRequest = useCallback(
    async (
      suggestionType: SuggestionType,
      runner: () => Promise<SuggestionPayload>,
    ) => {
      setState((prev) => ({
        ...prev,
        activeSuggestionType: suggestionType,
        isLoading: true,
        error: null,
        // Canonical decision reset on canonical new suggestion request.
        decisions: [],
      }))
      try {
        const payload = await runner()
        setState((prev) => ({
          ...prev,
          payload,
          isLoading: false,
        }))
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: extractErrorMessage(err) ?? "Suggestion request failed",
        }))
      }
    },
    [],
  )

  const requestSuggestLayout = useCallback(async () => {
    await _runRequest("suggest_layout", () => suggestLayout(instanceId))
  }, [_runRequest, instanceId])

  const requestSuggestTextStyle = useCallback(
    async (body: SuggestTextStyleRequest = {}) => {
      await _runRequest("suggest_text_style", () =>
        suggestTextStyle(instanceId, body),
      )
    },
    [_runRequest, instanceId],
  )

  const requestExtractDecedentInfo = useCallback(
    async (body: ExtractDecedentInfoRequest) => {
      await _runRequest("extract_decedent_info", () =>
        extractDecedentInfo(instanceId, body),
      )
    },
    [_runRequest, instanceId],
  )

  // Canonical Confirm action — canonical operator agency applies
  // canonical line item to canvas state per §3.26.11.12.16 Anti-pattern
  // 1 discipline.
  const confirm = useCallback(
    (lineItem: SuggestionLineItem, editedValue?: unknown) => {
      const valueToApply =
        editedValue !== undefined ? editedValue : lineItem.value
      const nextCanvasState = applyLineItemToCanvasState(
        canvasState.canvasState,
        lineItem.line_item_key,
        valueToApply,
        state.activeSuggestionType,
      )
      canvasState.setCanvasState(nextCanvasState)
      setState((prev) => ({
        ...prev,
        decisions: upsertDecision(prev.decisions, {
          line_item_key: lineItem.line_item_key,
          decision: "confirm",
          edited_value: editedValue,
        }),
      }))
    },
    [canvasState, state.activeSuggestionType],
  )

  const edit = useCallback((lineItem: SuggestionLineItem) => {
    setState((prev) => ({
      ...prev,
      decisions: upsertDecision(prev.decisions, {
        line_item_key: lineItem.line_item_key,
        decision: "edit",
      }),
    }))
  }, [])

  const reject = useCallback((lineItem: SuggestionLineItem) => {
    setState((prev) => ({
      ...prev,
      decisions: upsertDecision(prev.decisions, {
        line_item_key: lineItem.line_item_key,
        decision: "reject",
      }),
    }))
  }, [])

  const skip = useCallback((lineItem: SuggestionLineItem) => {
    setState((prev) => ({
      ...prev,
      decisions: upsertDecision(prev.decisions, {
        line_item_key: lineItem.line_item_key,
        decision: "skip",
      }),
    }))
  }, [])

  return {
    ...state,
    requestSuggestLayout,
    requestSuggestTextStyle,
    requestExtractDecedentInfo,
    confirm,
    edit,
    reject,
    skip,
    reset,
  }
}


/** Canonical line-item-to-canvas-state dispatcher.
 *
 *  Per §3.26.11.12.16 Anti-pattern 1: applies canonical line item to
 *  canvas state via canonical mutation per canonical line_item_key
 *  + canonical suggestion_type. Canonical operator agency canonical
 *  via canonical Confirm action canonical at chrome substrate.
 *
 *  Canonical line_item_key dispatch:
 *  - layout suggestion keys (name_text_position, date_text_position,
 *    emblem_position, nameplate_position, vault_product_position) →
 *    create or update canonical canvas element x/y/width/height
 *  - text style suggestion keys (name_text_font, name_text_size, etc.)
 *    → update canonical element config field
 *  - decedent extraction keys (decedent_first_name, birth_date, etc.)
 *    → update canonical canvas state top-level field
 */
function applyLineItemToCanvasState(
  canvasState: CanvasState,
  lineItemKey: string | null,
  value: unknown,
  suggestionType: SuggestionType | null,
): CanvasState {
  if (!lineItemKey || suggestionType === null) return canvasState

  // Canonical layout suggestion keys → canonical canvas element placement.
  if (suggestionType === "suggest_layout") {
    const elementType = mapLayoutKeyToElementType(lineItemKey)
    if (!elementType) return canvasState
    const position = value as Partial<{
      x: number
      y: number
      width: number
      height: number
    }>
    const elements = [...canvasState.canvas_layout.elements]
    const idx = elements.findIndex((el) => el.element_type === elementType)
    if (idx >= 0) {
      // Canonical element already present → update position.
      elements[idx] = {
        ...elements[idx],
        x: position.x ?? elements[idx].x,
        y: position.y ?? elements[idx].y,
        width: position.width ?? elements[idx].width,
        height: position.height ?? elements[idx].height,
      }
    } else {
      // Canonical element absent → create canonical canvas element.
      const newEl: CanvasElement = {
        id: generateId(),
        element_type: elementType,
        x: position.x ?? 0,
        y: position.y ?? 0,
        width: position.width,
        height: position.height,
        config: {},
      }
      elements.push(newEl)
    }
    return {
      ...canvasState,
      canvas_layout: { elements },
    }
  }

  // Canonical text style suggestion keys → canonical element config update.
  if (suggestionType === "suggest_text_style") {
    const styleTarget = mapTextStyleKey(lineItemKey)
    if (!styleTarget) return canvasState
    const styleValue = value as Partial<{
      font: string
      size: number
      color: string
    }>
    const elements = canvasState.canvas_layout.elements.map((el) => {
      if (el.element_type !== styleTarget.elementType) return el
      const config = (el.config ?? {}) as Record<string, unknown>
      const nextConfig = { ...config }
      if (styleTarget.field === "font" && styleValue.font !== undefined) {
        nextConfig.font = styleValue.font
      }
      if (styleTarget.field === "size" && styleValue.size !== undefined) {
        nextConfig.size = styleValue.size
      }
      if (styleTarget.field === "color" && styleValue.color !== undefined) {
        nextConfig.color = styleValue.color
      }
      return { ...el, config: nextConfig }
    })
    return { ...canvasState, canvas_layout: { elements } }
  }

  // Canonical decedent extraction keys → canonical canvas state top-level
  // field update.
  if (suggestionType === "extract_decedent_info") {
    return applyDecedentInfoToCanvasState(canvasState, lineItemKey, value)
  }

  return canvasState
}


function mapLayoutKeyToElementType(
  key: string,
): CanvasElement["element_type"] | null {
  switch (key) {
    case "name_text_position":
      return "name_text"
    case "date_text_position":
      return "date_text"
    case "emblem_position":
      return "emblem"
    case "nameplate_position":
      return "nameplate"
    case "vault_product_position":
      return "vault_product"
    default:
      return null
  }
}


function mapTextStyleKey(
  key: string,
): { elementType: CanvasElement["element_type"]; field: "font" | "size" | "color" } | null {
  switch (key) {
    case "name_text_font":
      return { elementType: "name_text", field: "font" }
    case "name_text_size":
      return { elementType: "name_text", field: "size" }
    case "name_text_color":
      return { elementType: "name_text", field: "color" }
    case "date_text_font":
      return { elementType: "date_text", field: "font" }
    case "date_text_size":
      return { elementType: "date_text", field: "size" }
    case "nameplate_text_font":
      return { elementType: "nameplate", field: "font" }
    default:
      return null
  }
}


function applyDecedentInfoToCanvasState(
  canvasState: CanvasState,
  key: string,
  value: unknown,
): CanvasState {
  const stringValue = typeof value === "string" ? value : null
  switch (key) {
    case "decedent_first_name":
    case "decedent_middle_name":
    case "decedent_last_name":
    case "decedent_full_name":
      return {
        ...canvasState,
        name_display:
          key === "decedent_full_name"
            ? stringValue
            : composeNameDisplay(canvasState.name_display, key, stringValue),
      }
    case "birth_date":
      return { ...canvasState, birth_date_display: stringValue }
    case "death_date":
      return { ...canvasState, death_date_display: stringValue }
    case "emblem_hint":
      return { ...canvasState, emblem_key: stringValue }
    case "nameplate_text_hint":
      return { ...canvasState, nameplate_text: stringValue }
    default:
      return canvasState
  }
}


function composeNameDisplay(
  current: string | null,
  key:
    | "decedent_first_name"
    | "decedent_middle_name"
    | "decedent_last_name",
  value: string | null,
): string | null {
  // Canonical name_display composition canonical-best-effort: per-part
  // canonical line items compose into single canonical name_display
  // string. Phase 1C canonical-pattern-establisher: simple canonical
  // append; chrome substrate refines via canonical Edit affordance per
  // canonical operator agency.
  if (!value) return current
  const existingParts = (current ?? "").split(/\s+/).filter(Boolean)
  const orderHint = {
    decedent_first_name: 0,
    decedent_middle_name: 1,
    decedent_last_name: 2,
  } as const
  const nextParts = [...existingParts]
  // Defensive insert at canonical hint position.
  const insertIdx = Math.min(orderHint[key], nextParts.length)
  nextParts.splice(insertIdx, 0, value)
  return nextParts.join(" ")
}


function upsertDecision(
  decisions: LineItemDecisionRecord[],
  next: LineItemDecisionRecord,
): LineItemDecisionRecord[] {
  const idx = decisions.findIndex(
    (d) => d.line_item_key === next.line_item_key,
  )
  if (idx >= 0) {
    const copy = [...decisions]
    copy[idx] = next
    return copy
  }
  return [...decisions, next]
}


function generateId(): string {
  // Canonical UUID generation; crypto.randomUUID() canonically available
  // in modern browsers + Node 18+; canonical fallback canonical for
  // jsdom-test substrate.
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID()
  }
  return `el-${Math.random().toString(36).slice(2, 11)}-${Date.now()}`
}


function extractErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    return e.response?.data?.detail ?? e.message ?? null
  }
  return null
}

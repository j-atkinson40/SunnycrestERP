/**
 * useNLExtraction — debounced NL extraction state.
 *
 * Owns:
 *   - The current NL input text (owned by caller via `text` arg;
 *     the hook only reacts to changes)
 *   - Debounced extract call at 300ms (per approved plan — amortizes
 *     AI latency)
 *   - AbortController cancellation on new input
 *   - ExtractionResult state + loading + error
 *
 * Exposes:
 *   - `extractions`, `missingRequired`, `extractionMs`
 *   - `isExtracting`, `error`
 *   - `create(overrides?)` — POSTs to /nl-creation/create, returns
 *     a `CreateResponse`. Caller navigates.
 *   - `manuallyOverride(fieldKey, value)` — let users edit a
 *     captured value; bumps confidence to 1.0 and flags is_manual
 *     so subsequent keystrokes don't revert it.
 *   - `clearManualOverrides()` — purge manual state when user
 *     exits NL mode.
 *
 * Debounce strategy:
 *   - 300ms after the last keystroke → fire extract.
 *   - If a new keystroke arrives during an in-flight call, abort
 *     and queue the next one.
 *   - Empty input → clear extractions immediately (no network).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  createEntity,
  extractFields,
} from "@/services/nl-creation-service";
import type {
  CreateResponse,
  ExtractionResult,
  FieldExtraction,
  NLEntityType,
} from "@/types/nl-creation";

const DEBOUNCE_MS = 300;
const MIN_INPUT_LEN = 3; // below this, don't bother extracting

interface UseNLExtractionArgs {
  entityType: NLEntityType;
  text: string;
  activeSpaceId?: string | null;
  /** If false, the hook is dormant — no extracts fire. Used to
   *  suspend when the overlay is closed. */
  enabled?: boolean;
}

interface UseNLExtractionReturn {
  extractions: FieldExtraction[];
  missingRequired: string[];
  extractionMs: number | null;
  aiLatencyMs: number | null;
  isExtracting: boolean;
  error: string | null;
  /** Materialize the entity. Returns the create response. */
  create: () => Promise<CreateResponse>;
  /** Overwrite a field's value manually (user edit). */
  manuallyOverride: (fieldKey: string, value: string) => void;
  /** Remove a field. */
  removeField: (fieldKey: string) => void;
  /** Reset all extraction state — called when exiting NL mode. */
  reset: () => void;
}

export function useNLExtraction({
  entityType,
  text,
  activeSpaceId,
  enabled = true,
}: UseNLExtractionArgs): UseNLExtractionReturn {
  const [extractions, setExtractions] = useState<FieldExtraction[]>([]);
  const [missingRequired, setMissingRequired] = useState<string[]>([]);
  const [extractionMs, setExtractionMs] = useState<number | null>(null);
  const [aiLatencyMs, setAiLatencyMs] = useState<number | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Manual-override state: map of field_key → FieldExtraction with
  // confidence=1.0 + source="ai_extraction" preserved as-is but
  // treated as untouchable in merge. We store the keys and patch
  // them into `prior_extractions` on the next extract call.
  const manualOverridesRef = useRef<Map<string, FieldExtraction>>(new Map());

  // AbortController of the in-flight call.
  const abortRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runExtract = useCallback(
    async (input: string, prior: FieldExtraction[]) => {
      if (!enabled) return;
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsExtracting(true);
      setError(null);
      try {
        const result: ExtractionResult = await extractFields(
          {
            entity_type: entityType,
            natural_language: input,
            active_space_id: activeSpaceId ?? null,
            prior_extractions: prior,
          },
          controller.signal,
        );
        // Re-apply manual overrides on top of server response (the
        // server returned them as-is via prior_extractions, but we
        // defensively re-merge here in case the server dropped any).
        const merged = _reapplyManualOverrides(
          result.extractions,
          manualOverridesRef.current,
        );
        setExtractions(merged);
        setMissingRequired(result.missing_required);
        setExtractionMs(result.extraction_ms);
        setAiLatencyMs(result.ai_latency_ms);
      } catch (err) {
        // Ignore abort errors — expected on rapid keystroke.
        const e = err as { name?: string; response?: { data?: { detail?: string } } };
        if (e?.name === "CanceledError" || e?.name === "AbortError") {
          return;
        }
        setError(e?.response?.data?.detail ?? "Extraction failed");
      } finally {
        setIsExtracting(false);
      }
    },
    [entityType, activeSpaceId, enabled],
  );

  // Debounce on text changes.
  useEffect(() => {
    if (!enabled) return;
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);

    const trimmed = text.trim();
    if (trimmed.length < MIN_INPUT_LEN) {
      // Keep existing manual overrides even when text is short.
      setExtractions(_reapplyManualOverrides([], manualOverridesRef.current));
      setMissingRequired([]);
      setExtractionMs(null);
      setAiLatencyMs(null);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      // Pass manual overrides as prior_extractions so the server
      // preserves them in its merge pass.
      const prior: FieldExtraction[] = Array.from(
        manualOverridesRef.current.values(),
      );
      void runExtract(trimmed, prior);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [text, enabled, runExtract]);

  // Reset everything when entity type changes.
  useEffect(() => {
    manualOverridesRef.current.clear();
    setExtractions([]);
    setMissingRequired([]);
    setError(null);
  }, [entityType]);

  const create = useCallback(async (): Promise<CreateResponse> => {
    return createEntity({
      entity_type: entityType,
      extractions,
      raw_input: text,
    });
  }, [entityType, extractions, text]);

  const manuallyOverride = useCallback(
    (fieldKey: string, value: string) => {
      setExtractions((prev) => {
        const next = [...prev];
        const idx = next.findIndex((e) => e.field_key === fieldKey);
        const label =
          idx >= 0
            ? next[idx].field_label
            : fieldKey.replaceAll("_", " ");
        const patched: FieldExtraction = {
          field_key: fieldKey,
          field_label: label,
          extracted_value: value,
          display_value: value,
          confidence: 1.0,
          source: "ai_extraction", // closest slot; server treats as user-affirmed via confidence=1
          resolved_entity_id: null,
          resolved_entity_type: null,
        };
        if (idx >= 0) next[idx] = patched;
        else next.push(patched);
        manualOverridesRef.current.set(fieldKey, patched);
        return next;
      });
    },
    [],
  );

  const removeField = useCallback((fieldKey: string) => {
    setExtractions((prev) => prev.filter((e) => e.field_key !== fieldKey));
    manualOverridesRef.current.delete(fieldKey);
  }, []);

  const reset = useCallback(() => {
    manualOverridesRef.current.clear();
    setExtractions([]);
    setMissingRequired([]);
    setError(null);
    setExtractionMs(null);
    setAiLatencyMs(null);
    if (abortRef.current) abortRef.current.abort();
  }, []);

  return {
    extractions,
    missingRequired,
    extractionMs,
    aiLatencyMs,
    isExtracting,
    error,
    create,
    manuallyOverride,
    removeField,
    reset,
  };
}

// ── helpers ──────────────────────────────────────────────────────────

function _reapplyManualOverrides(
  serverExtractions: FieldExtraction[],
  overrides: Map<string, FieldExtraction>,
): FieldExtraction[] {
  if (overrides.size === 0) return serverExtractions;
  const byKey = new Map(serverExtractions.map((e) => [e.field_key, e]));
  for (const [k, v] of overrides.entries()) {
    byKey.set(k, v);
  }
  return Array.from(byKey.values());
}

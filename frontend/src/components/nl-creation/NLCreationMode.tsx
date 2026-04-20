/**
 * NLCreationMode — orchestrates the live overlay + input + keyboard.
 *
 * Renders the NLOverlay below the caller's input (the command bar
 * `<input>` stays in the parent — this component is positioned as a
 * panel under it). Keyboard behavior:
 *
 *   Enter  → create()  → navigate to entity detail
 *   Tab    → tabToForm() → navigate to traditional /cases/new, etc,
 *            with extracted fields pre-filled via query params
 *   Escape → onCancel() → caller unmounts this component
 *
 * The component does NOT own the input text. The command bar owns
 * the text + passes it in via `text`. This decoupling lets the
 * command bar keep its existing input + voice integration intact.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNLExtraction } from "@/hooks/useNLExtraction";
import { listNLEntityTypes } from "@/services/nl-creation-service";
import type { NLEntityType, NLEntityTypeInfo } from "@/types/nl-creation";

import { NLOverlay } from "./NLOverlay";

export interface NLCreationModeProps {
  entityType: NLEntityType;
  text: string;
  activeSpaceId?: string | null;
  /** Called when the user dismisses the overlay (Escape / error). */
  onCancel: () => void;
  /** Called when the user successfully creates. Receives the
   *  navigate_url so the caller can close the command bar after
   *  redirecting. */
  onCreated?: (navigateUrl: string) => void;
  /** Base URL for Tab-to-form fallback. Usually the entity's
   *  existing create route (e.g. "/cases/new"). */
  tabFallbackUrl?: string;
}

// Module-level cache of entity types — the command bar spawns /
// unmounts this component repeatedly as the user types, and the
// entity schema doesn't change often.
let _entityTypesCache: Promise<NLEntityTypeInfo[]> | null = null;
function getEntityTypes(): Promise<NLEntityTypeInfo[]> {
  if (!_entityTypesCache) {
    _entityTypesCache = listNLEntityTypes();
  }
  return _entityTypesCache;
}

export function NLCreationMode({
  entityType,
  text,
  activeSpaceId,
  onCancel,
  onCreated,
  tabFallbackUrl,
}: NLCreationModeProps) {
  const navigate = useNavigate();
  const [entityTypes, setEntityTypes] = useState<NLEntityTypeInfo[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    extractions,
    missingRequired,
    extractionMs,
    isExtracting,
    error,
    create,
  } = useNLExtraction({
    entityType,
    text,
    activeSpaceId,
    enabled: true,
  });

  // Load entity types on mount — they populate the overlay header
  // + field label lookups for the Missing section.
  useEffect(() => {
    let cancelled = false;
    getEntityTypes()
      .then((list) => {
        if (!cancelled) setEntityTypes(list);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const entityInfo = useMemo(
    () =>
      entityTypes.find((e) => e.entity_type === entityType) ?? null,
    [entityTypes, entityType],
  );

  // ── Keyboard — listen on window so we catch keys even if focus
  //    is still on the command bar input. ───────────────────────
  const handleCreate = useCallback(async () => {
    if (submitting) return;
    if (missingRequired.length > 0) {
      // Don't submit when required fields are unresolved; the
      // overlay already shows what's missing.
      setSubmitError(
        `Missing: ${missingRequired.join(", ")}. Keep typing or press Tab to open a form.`,
      );
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const resp = await create();
      onCreated?.(resp.navigate_url);
      navigate(resp.navigate_url);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setSubmitError(e?.response?.data?.detail ?? "Failed to create");
    } finally {
      setSubmitting(false);
    }
  }, [create, missingRequired, submitting, onCreated, navigate]);

  const handleTabToForm = useCallback(() => {
    if (!tabFallbackUrl) return;
    // Pass the raw input + extraction hints via query params so the
    // traditional form can pre-fill. Simple scheme: ?nl=<input> and
    // nothing else; the form inspects the NL input on mount and
    // pre-fills deterministically. If the receiving page doesn't
    // honor `nl`, it harmlessly falls through to a blank form.
    const url = `${tabFallbackUrl}?nl=${encodeURIComponent(text)}`;
    onCancel();
    navigate(url);
  }, [tabFallbackUrl, text, onCancel, navigate]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void handleCreate();
        return;
      }
      if (e.key === "Tab" && !e.shiftKey && tabFallbackUrl) {
        e.preventDefault();
        handleTabToForm();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
        return;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleCreate, handleTabToForm, onCancel, tabFallbackUrl]);

  const displayError = submitError ?? error;

  return (
    <div data-testid="nl-creation-mode" data-entity-type={entityType}>
      <NLOverlay
        entityType={entityType}
        entityInfo={entityInfo}
        extractions={extractions}
        missingRequired={missingRequired}
        isExtracting={isExtracting || submitting}
        error={displayError}
        extractionMs={extractionMs}
      />
    </div>
  );
}

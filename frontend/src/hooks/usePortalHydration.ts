/**
 * usePortalHydration — S-1 (§4.2), ruled hydration semantics:
 * hydrate on result HIGHLIGHT with ~150ms debounce; cancel the
 * in-flight request when the highlight moves.
 *
 * Composes the same debounce + AbortController pattern as the
 * saved-view builder preview (useDebouncedValue + abort-on-newer).
 */

import { useEffect, useRef, useState } from "react";

import { fetchEntityPortal } from "@/services/entity-portal-service";
import type { PortalResponse } from "@/types/entity-portal";

const HIGHLIGHT_DEBOUNCE_MS = 150;

export interface PortalHydrationState {
  data: PortalResponse | null;
  loading: boolean;
  error: boolean;
}

export function usePortalHydration(
  entityType: string | null,
  entityId: string | null,
): PortalHydrationState {
  const [state, setState] = useState<PortalHydrationState>({
    data: null,
    loading: false,
    error: false,
  });
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Highlight moved away (or nothing highlighted): cancel + clear.
    abortRef.current?.abort();
    if (!entityType || !entityId) {
      setState({ data: null, loading: false, error: false });
      return;
    }

    setState((s) => ({ ...s, loading: true, error: false }));
    const controller = new AbortController();
    abortRef.current = controller;

    const timer = setTimeout(() => {
      fetchEntityPortal(entityType, entityId, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) {
            setState({ data, loading: false, error: false });
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setState({ data: null, loading: false, error: true });
          }
        });
    }, HIGHLIGHT_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [entityType, entityId]);

  return state;
}

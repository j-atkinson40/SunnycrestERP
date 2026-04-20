/**
 * SpaceContext — Phase 3 of UI/UX Arc.
 *
 * Loads the current user's spaces on mount (authed users only),
 * tracks the active space, exposes mutation helpers that
 * optimistic-update + reconcile with server truth.
 *
 * Mounts INSIDE PresetThemeProvider inside the tenant AppLayout
 * branch. Platform admin (BridgeableAdminApp) is untouched — no
 * SpaceProvider there.
 *
 * Accent application:
 *   - On active-space change, applyAccentVars(accent) sets
 *     --space-* CSS variables on documentElement.
 *   - PresetThemeProvider's --preset-accent is never touched.
 *   - Components use var(--space-accent, var(--preset-accent))
 *     so they gracefully fall back when no space is active.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAuth } from "@/contexts/auth-context";
import {
  activateSpace as apiActivate,
  addPin as apiAddPin,
  createSpace as apiCreate,
  deleteSpace as apiDelete,
  listSpaces as apiList,
  removePin as apiRemovePin,
  reorderPins as apiReorderPins,
  reorderSpaces as apiReorderSpaces,
  updateSpace as apiUpdate,
} from "@/services/spaces-service";
import type {
  AddPinBody,
  CreateSpaceBody,
  ResolvedPin,
  Space,
  UpdateSpaceBody,
} from "@/types/spaces";
import { applyAccentVars } from "@/types/spaces";

interface SpaceContextValue {
  spaces: Space[];
  activeSpace: Space | null;
  activeSpaceId: string | null;
  isLoading: boolean;
  error: string | null;
  // Mutations
  refresh: () => Promise<void>;
  switchSpace: (spaceId: string) => Promise<void>;
  createSpace: (body: CreateSpaceBody) => Promise<Space>;
  updateSpace: (spaceId: string, body: UpdateSpaceBody) => Promise<Space>;
  deleteSpace: (spaceId: string) => Promise<void>;
  reorderSpaces: (spaceIds: string[]) => Promise<void>;
  // Pin ops
  addPin: (spaceId: string, body: AddPinBody) => Promise<ResolvedPin>;
  removePin: (spaceId: string, pinId: string) => Promise<void>;
  reorderPins: (spaceId: string, pinIds: string[]) => Promise<void>;
  // Convenience — is this nav href / saved-view id pinned in the active space?
  isPinned: (args: {
    pinType: "nav_item" | "saved_view";
    targetId: string;
  }) => boolean;
  togglePinInActiveSpace: (args: {
    pinType: "nav_item" | "saved_view";
    targetId: string;
    labelOverride?: string;
  }) => Promise<void>;
}

const SpaceContext = createContext<SpaceContextValue | null>(null);

export function SpaceProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  const [spaces, setSpaces] = useState<Space[]>([]);
  const [activeSpaceId, setActiveSpaceId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track whether we've attempted a load for the current user, so
  // we don't re-fetch on every render.
  const loadedForUserId = useRef<string | null>(null);

  const fetchSpaces = useCallback(async () => {
    if (!user?.id) return;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await apiList();
      setSpaces(resp.spaces);
      setActiveSpaceId(resp.active_space_id);
      loadedForUserId.current = user.id;
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to load spaces");
      // Leave spaces empty on error — UI renders without any
      // pinned section. Base vertical nav still works.
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  // Load on mount + whenever the user changes.
  useEffect(() => {
    if (!user?.id) {
      setSpaces([]);
      setActiveSpaceId(null);
      loadedForUserId.current = null;
      return;
    }
    if (loadedForUserId.current === user.id) return;
    void fetchSpaces();
  }, [user?.id, fetchSpaces]);

  // Apply accent vars when the active space changes.
  const activeSpace = useMemo(
    () =>
      activeSpaceId
        ? spaces.find((s) => s.space_id === activeSpaceId) ?? null
        : spaces.find((s) => s.is_default) ?? null,
    [spaces, activeSpaceId],
  );

  useEffect(() => {
    applyAccentVars(activeSpace?.accent ?? null);
  }, [activeSpace?.accent]);

  // ── Mutations with optimistic updates + reconciliation ──────────

  const switchSpace = useCallback(
    async (spaceId: string) => {
      // Optimistic: update local state immediately.
      setActiveSpaceId(spaceId);
      try {
        await apiActivate(spaceId);
      } catch (err) {
        // Reconcile: refetch truth on failure.
        await fetchSpaces();
        throw err;
      }
    },
    [fetchSpaces],
  );

  const createSpace = useCallback(
    async (body: CreateSpaceBody): Promise<Space> => {
      const created = await apiCreate(body);
      setSpaces((prev) => {
        // If the new space is_default, demote any existing default.
        const next = created.is_default
          ? prev.map((s) => ({ ...s, is_default: false }))
          : prev.slice();
        next.push(created);
        next.sort((a, b) => a.display_order - b.display_order);
        return next;
      });
      return created;
    },
    [],
  );

  const updateSpace = useCallback(
    async (spaceId: string, body: UpdateSpaceBody): Promise<Space> => {
      const updated = await apiUpdate(spaceId, body);
      setSpaces((prev) => {
        // Promoting to default demotes everyone else.
        const next = updated.is_default
          ? prev.map((s) =>
              s.space_id === spaceId
                ? updated
                : { ...s, is_default: false },
            )
          : prev.map((s) => (s.space_id === spaceId ? updated : s));
        return next;
      });
      return updated;
    },
    [],
  );

  const deleteSpace = useCallback(
    async (spaceId: string) => {
      // Optimistic removal, then refetch for default promotion /
      // active-space clear.
      setSpaces((prev) => prev.filter((s) => s.space_id !== spaceId));
      try {
        await apiDelete(spaceId);
      } finally {
        await fetchSpaces();
      }
    },
    [fetchSpaces],
  );

  const reorderSpaces = useCallback(
    async (spaceIds: string[]) => {
      // Optimistic
      setSpaces((prev) => {
        const byId = new Map(prev.map((s) => [s.space_id, s]));
        return spaceIds
          .map((id, i) => {
            const s = byId.get(id);
            return s ? { ...s, display_order: i } : null;
          })
          .filter((s): s is Space => s !== null);
      });
      try {
        const resp = await apiReorderSpaces(spaceIds);
        setSpaces(resp.spaces);
      } catch (err) {
        await fetchSpaces();
        throw err;
      }
    },
    [fetchSpaces],
  );

  const addPin = useCallback(
    async (spaceId: string, body: AddPinBody): Promise<ResolvedPin> => {
      const pin = await apiAddPin(spaceId, body);
      setSpaces((prev) =>
        prev.map((s) => {
          if (s.space_id !== spaceId) return s;
          // De-dupe — the backend is idempotent; replace if same pin_id.
          const filtered = s.pins.filter((p) => p.pin_id !== pin.pin_id);
          return { ...s, pins: [...filtered, pin].sort((a, b) => a.display_order - b.display_order) };
        }),
      );
      return pin;
    },
    [],
  );

  const removePin = useCallback(
    async (spaceId: string, pinId: string) => {
      // Optimistic
      setSpaces((prev) =>
        prev.map((s) =>
          s.space_id === spaceId
            ? { ...s, pins: s.pins.filter((p) => p.pin_id !== pinId) }
            : s,
        ),
      );
      try {
        await apiRemovePin(spaceId, pinId);
      } catch (err) {
        await fetchSpaces();
        throw err;
      }
    },
    [fetchSpaces],
  );

  const reorderPins = useCallback(
    async (spaceId: string, pinIds: string[]) => {
      // Optimistic
      setSpaces((prev) =>
        prev.map((s) => {
          if (s.space_id !== spaceId) return s;
          const byId = new Map(s.pins.map((p) => [p.pin_id, p]));
          const reordered = pinIds
            .map((id, i) => {
              const p = byId.get(id);
              return p ? { ...p, display_order: i } : null;
            })
            .filter((p): p is ResolvedPin => p !== null);
          return { ...s, pins: reordered };
        }),
      );
      try {
        const updated = await apiReorderPins(spaceId, pinIds);
        setSpaces((prev) =>
          prev.map((s) => (s.space_id === spaceId ? updated : s)),
        );
      } catch (err) {
        await fetchSpaces();
        throw err;
      }
    },
    [fetchSpaces],
  );

  // ── Pin convenience helpers ─────────────────────────────────────

  const isPinned = useCallback(
    (args: { pinType: "nav_item" | "saved_view"; targetId: string }): boolean => {
      if (!activeSpace) return false;
      return activeSpace.pins.some(
        (p) => p.pin_type === args.pinType && p.target_id === args.targetId,
      );
    },
    [activeSpace],
  );

  const togglePinInActiveSpace = useCallback(
    async (args: {
      pinType: "nav_item" | "saved_view";
      targetId: string;
      labelOverride?: string;
    }) => {
      if (!activeSpace) return;
      const existing = activeSpace.pins.find(
        (p) => p.pin_type === args.pinType && p.target_id === args.targetId,
      );
      if (existing) {
        await removePin(activeSpace.space_id, existing.pin_id);
      } else {
        await addPin(activeSpace.space_id, {
          pin_type: args.pinType,
          target_id: args.targetId,
          label_override: args.labelOverride ?? null,
        });
      }
    },
    [activeSpace, addPin, removePin],
  );

  const value: SpaceContextValue = {
    spaces,
    activeSpace,
    activeSpaceId,
    isLoading,
    error,
    refresh: fetchSpaces,
    switchSpace,
    createSpace,
    updateSpace,
    deleteSpace,
    reorderSpaces,
    addPin,
    removePin,
    reorderPins,
    isPinned,
    togglePinInActiveSpace,
  };

  return (
    <SpaceContext.Provider value={value}>{children}</SpaceContext.Provider>
  );
}

export function useSpaces(): SpaceContextValue {
  const ctx = useContext(SpaceContext);
  if (!ctx) {
    throw new Error("useSpaces must be used within SpaceProvider");
  }
  return ctx;
}

/**
 * Null-safe variant of {@link useSpaces}. Returns `null` when
 * SpaceProvider isn't mounted — e.g. the command bar renders above
 * SpaceProvider in the App tree, so it's reachable on login /
 * unauthenticated routes. Callers check for null before using.
 *
 * **Do NOT** use this in components that live INSIDE the
 * SpaceProvider subtree (SpaceSwitcher, PinnedSection, etc.) — those
 * should use `useSpaces()` which asserts the provider is present.
 */
export function useSpacesOptional(): SpaceContextValue | null {
  return useContext(SpaceContext);
}

/**
 * Hook for callers that only need the active space id without
 * subscribing to the full context value. Used by command bar to
 * thread `active_space_id` into the query payload.
 */
export function useActiveSpaceId(): string | null {
  const ctx = useContext(SpaceContext);
  // Null-safe: when SpaceProvider isn't mounted (e.g. login page
  // before auth), return null — callers handle gracefully.
  return ctx?.activeSpace?.space_id ?? null;
}

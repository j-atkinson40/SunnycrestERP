/**
 * Triage session context — holds the current session + current item
 * + cached queue config for the active `/triage/:queueId` page.
 *
 * The provider wraps a single queue page; it's not an app-wide
 * provider. The page mounts → provider calls `startSession` →
 * calls `next_item` → user acts → provider auto-advances.
 *
 * On unmount (navigate away or page close) the provider fires
 * `endSession` so the backend can stamp `ended_at`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  applyAction,
  endSession,
  fetchNextItem,
  getQueueConfig,
  snoozeItem,
  startSession,
  type ApplyActionPayload,
  type SnoozePayload,
} from "@/services/triage-service";
import type {
  TriageItem,
  TriageQueueConfig,
  TriageSessionSummary,
} from "@/types/triage";

type Status = "loading" | "idle" | "working" | "empty" | "error";

interface TriageSessionContextValue {
  status: Status;
  error: string | null;
  config: TriageQueueConfig | null;
  session: TriageSessionSummary | null;
  item: TriageItem | null;
  /** Fetch the next item. Sets status=empty if the queue is exhausted. */
  advance: () => Promise<void>;
  act: (payload: ApplyActionPayload) => Promise<void>;
  snooze: (payload: SnoozePayload) => Promise<void>;
}

const TriageSessionContext = createContext<TriageSessionContextValue | null>(
  null,
);

export function TriageSessionProvider({
  queueId,
  children,
}: {
  queueId: string;
  children: ReactNode;
}) {
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<TriageQueueConfig | null>(null);
  const [session, setSession] = useState<TriageSessionSummary | null>(null);
  const [item, setItem] = useState<TriageItem | null>(null);

  // Session id held in a ref so the unmount cleanup doesn't race
  // with state updates.
  const sessionIdRef = useRef<string | null>(null);

  const advance = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    setStatus("working");
    try {
      const next = await fetchNextItem(sid);
      if (next) {
        setItem(next);
        setStatus("idle");
      } else {
        setItem(null);
        setStatus("empty");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load item");
      setStatus("error");
    }
  }, []);

  const act = useCallback(
    async (payload: ApplyActionPayload) => {
      const sid = sessionIdRef.current;
      if (!sid || !item) return;
      setStatus("working");
      try {
        const result = await applyAction(sid, item.entity_id, payload);
        if (result.status === "errored") {
          // Phase 7: action-level failure doesn't kill the session —
          // item stays in queue, caller surfaces toast + lets the user
          // retry. Restore status=idle so buttons re-enable.
          setStatus("idle");
          throw new Error(result.message);
        }
        // Backend auto-advances cursor; fetch the next item.
        await advance();
      } catch (err) {
        setStatus("idle");
        throw err instanceof Error ? err : new Error("Action failed");
      }
    },
    [advance, item],
  );

  const snooze = useCallback(
    async (payload: SnoozePayload) => {
      const sid = sessionIdRef.current;
      if (!sid || !item) return;
      setStatus("working");
      try {
        await snoozeItem(sid, item.entity_id, payload);
        await advance();
      } catch (err) {
        setStatus("idle");
        throw err instanceof Error ? err : new Error("Snooze failed");
      }
    },
    [advance, item],
  );

  // Bootstrap: load config + open session + pull first item.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStatus("loading");
      setError(null);
      try {
        const [cfg, sess] = await Promise.all([
          getQueueConfig(queueId),
          startSession(queueId),
        ]);
        if (cancelled) return;
        setConfig(cfg.config);
        setSession(sess);
        sessionIdRef.current = sess.session_id;
        // First item:
        const next = await fetchNextItem(sess.session_id);
        if (cancelled) return;
        if (next) {
          setItem(next);
          setStatus("idle");
        } else {
          setItem(null);
          setStatus("empty");
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Failed to start triage session",
        );
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
      const sid = sessionIdRef.current;
      if (sid) {
        // Fire-and-forget — don't block unmount.
        void endSession(sid).catch(() => undefined);
        sessionIdRef.current = null;
      }
    };
  }, [queueId]);

  return (
    <TriageSessionContext.Provider
      value={{ status, error, config, session, item, advance, act, snooze }}
    >
      {children}
    </TriageSessionContext.Provider>
  );
}

export function useTriageSession(): TriageSessionContextValue {
  const ctx = useContext(TriageSessionContext);
  if (!ctx) {
    throw new Error(
      "useTriageSession must be used inside <TriageSessionProvider>",
    );
  }
  return ctx;
}

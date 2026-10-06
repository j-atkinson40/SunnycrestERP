// call-context.tsx — Global call state + SSE connection for Call Intelligence.
// Manages active call lifecycle: ringing → active → review → dismissed.
// Provider: RingCentral (SSE endpoint). Provider-agnostic context interface.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { resolveApiBaseUrl } from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * One extracted field as the server sends it.
 *
 * ⚠️ `confidence` IS NULLABLE, DELIBERATELY. The model supplies confidence per
 * field and may omit one; the server sends `null` rather than defaulting,
 * because `1.0` would assert certainty nothing measured and `0.0` would assert
 * doubt nothing measured. Render no percentage when it is null.
 *
 * ⚠️ This shape is the CONTRACT, and until 2026-10-05 the server did not send
 * it — it sent flat strings plus one separate `confidence` dict, so
 * `field?.value` was `undefined` for every field on every surface and no
 * captured value has ever rendered. Three client sites assumed this shape; the
 * flat form had no consumers, so the server moved.
 */
export interface CallExtractionField {
  value: string;
  confidence: number | null;
}

export interface CallExtraction {
  /* ⚠️ EXACTLY THE FIELDS THE SERVER SENDS — `_EXTRACTED_FIELDS` in
   * app/api/routes/call_intelligence.py. Four names were removed on 2026-10-05
   * because they existed only here: `service_location`, `service_date`,
   * `service_time` and `special_instructions` had no column on
   * `ringcentral_call_extractions`, so they could never carry a value.
   *
   * `service_location` is a REAL requirement — a real `sales_orders` column read
   * by the scheduling Focus — and it enters the SALES-ORDER CAPTURE TEMPLATE
   * rather than this type. Nothing extracts it from a call yet, so it reports as
   * still-needed, which is correct. `service_date` / `service_time` are already
   * captured as `burial_date` / `service_time`. ⚠️ THIS SAID `burial_time` AND
   * DESCRIBED THE DRAFT WRITER AS "mapping one onto the other" — which was the
   * conflation, not a mapping. An order carries TWO time facts: `service_time` (the
   * service) and `eta` (cemetery arrival). r199 renamed the column and the writer now
   * takes each from its own field. `special_instructions` is `special_requests`. */
  funeral_home_name: CallExtractionField | null;
  deceased_name: CallExtractionField | null;
  vault_type: CallExtractionField | null;
  vault_size: CallExtractionField | null;
  cemetery_name: CallExtractionField | null;
  burial_date: CallExtractionField | null;
  service_time: CallExtractionField | null;
  eta: CallExtractionField | null;
  service_location: CallExtractionField | null;
  service_location_other: CallExtractionField | null;
  grave_location: CallExtractionField | null;
  special_requests: CallExtractionField | null;
  missing_fields: string[];
  /**
   * ⚠️ SERVER-COMPUTED, LIKE `missing_fields`. Field ids the capture engine
   * determined are answered. Render this; do not re-derive it from the
   * extraction columns — two components did exactly that, with two different
   * hardcoded lists, and neither ever rendered (every field is typed here as
   * `{value, confidence}` while the server sends flat strings). See r197.
   */
  answered_fields: string[];
  /**
   * ⚠️ WHAT THE VAULT PHRASE RESOLVED TO, AND THE AMBIGUOUS CASE IS THE POINT.
   *
   *   resolved     candidates has one entry, resolved_variant_id is set
   *   AMBIGUOUS    several candidates, resolved_variant_id null, and
   *                `discriminator` names the question to ask —
   *                "form" → burial or urn? "size" → which size?
   *                "line" → which product line? "option" → which finish?
   *   no match     candidates is empty
   *   not attempted  the whole field is null
   *
   * Render the ambiguous case as a QUESTION, never as a failure. "Bronze
   * Triune — burial or urn vault?" is one thing an operator can ask a caller who
   * is still on the phone; an empty capture list is a dead end. The server
   * deliberately does not pick: `cream and gold` matches a Regal and a Tribute
   * urn, and picking would sell the Regal silently every time.
   */
  vault_resolution: {
    phrase: string;
    resolved_variant_id: string | null;
    candidates: string[];
    discriminator: "form" | "line" | "size" | "option" | null;
  } | null;
  draft_order_id: string | null;
}

export type CallState = "ringing" | "active" | "review";

export interface InvoiceMetadata {
  invoice_number: string;
  invoice_date: string;
  total: number;
  status: string;
  customer_name?: string;
}

export interface ActiveCall {
  call_id: string;
  state: CallState;
  direction: "inbound" | "outbound";
  caller_number: string;
  caller_name: string | null;
  company_name: string | null;
  company_id: string | null;
  last_order_date: string | null;
  open_ar_balance: number | null;
  recent_invoices: InvoiceMetadata[];
  started_at: Date;
  answered_at: Date | null;
  ended_at: Date | null;
  extraction: CallExtraction | null;
}

export interface CallPreferences {
  rc_overlay_enabled: boolean;
  rc_sound_enabled: boolean;
  rc_auto_open_order: boolean;
}

export interface KBPanelResult {
  id: string;
  query: string;
  query_type: string;
  synthesis: string;
  confidence: string;
  pricing: Array<{
    product_name: string;
    product_code: string | null;
    price: string | null;
    price_tier: string;
    unit: string;
  }>;
  source_documents: string[];
  dismissed: boolean;
  received_at: Date;
}

interface CallContextValue {
  activeCall: ActiveCall | null;
  minimized: boolean;
  preferences: CallPreferences;
  connected: boolean;
  kbPanels: KBPanelResult[];
  dismissCall: () => void;
  toggleMinimized: () => void;
  answerCall: (callId: string) => Promise<void>;
  updatePreferences: (prefs: Partial<CallPreferences>) => void;
  dismissKBPanel: (id: string) => void;
}

const DEFAULT_PREFS: CallPreferences = {
  rc_overlay_enabled: true,
  rc_sound_enabled: true,
  rc_auto_open_order: false,
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CallContext = createContext<CallContextValue>({
  activeCall: null,
  minimized: false,
  preferences: DEFAULT_PREFS,
  connected: false,
  kbPanels: [],
  dismissCall: () => {},
  toggleMinimized: () => {},
  answerCall: async () => {},
  updatePreferences: () => {},
  dismissKBPanel: () => {},
});

export function useCall() {
  return useContext(CallContext);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CallContextProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [activeCall, setActiveCall] = useState<ActiveCall | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [connected, setConnected] = useState(false);
  const [preferences, setPreferences] = useState<CallPreferences>(DEFAULT_PREFS);
  const [kbPanels, setKBPanels] = useState<KBPanelResult[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  // Load preferences from localStorage
  useEffect(() => {
    if (!user) return;
    try {
      const stored = localStorage.getItem(`call_prefs_${user.id}`);
      if (stored) setPreferences({ ...DEFAULT_PREFS, ...JSON.parse(stored) });
    } catch {}
  }, [user?.id]);

  const updatePreferences = useCallback(
    (patch: Partial<CallPreferences>) => {
      setPreferences((prev) => {
        const next = { ...prev, ...patch };
        if (user) {
          localStorage.setItem(`call_prefs_${user.id}`, JSON.stringify(next));
        }
        return next;
      });
    },
    [user],
  );

  const dismissCall = useCallback(() => {
    setActiveCall(null);
    setMinimized(false);
    setKBPanels([]);
  }, []);

  const dismissKBPanel = useCallback((id: string) => {
    setKBPanels((prev) =>
      prev.map((p) => (p.id === id ? { ...p, dismissed: true } : p)),
    );
  }, []);

  const toggleMinimized = useCallback(() => {
    setMinimized((prev) => !prev);
  }, []);

  const answerCall = useCallback(async (callId: string) => {
    try {
      const { default: apiClient } = await import("@/lib/api-client");
      await apiClient.post(`/api/v1/integrations/ringcentral/calls/${callId}/answer`);
      setActiveCall((prev) =>
        prev && prev.call_id === callId
          ? { ...prev, state: "active", answered_at: new Date() }
          : prev,
      );
    } catch {
      const { toast } = await import("sonner");
      toast.error("Failed to answer call");
    }
  }, []);

  // SSE connection
  useEffect(() => {
    if (!user || !preferences.rc_overlay_enabled) return;

    // THE HANGING-JOBS FIX (2026-07-20): connect is SYNC again — the
    // async import created a cleanup race (cleanup ran before the await
    // resolved, so every mount cycle leaked an ORPHANED EventSource that
    // held one of the browser's 6 per-host connection slots forever;
    // enough tabs/mounts starved the whole origin and /jobs hung
    // indefinitely). Static import + the cancelled guard below make an
    // orphan impossible.
    let cancelled = false;
    function connect() {
      if (cancelled) return;
      const token = localStorage.getItem("access_token");
      if (!token) return;

      const url = `${resolveApiBaseUrl()}/api/v1/integrations/ringcentral/events?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        retryCountRef.current = 0;
      };

      es.addEventListener("call_started", (e) => {
        try {
          const data = JSON.parse(e.data);
          setActiveCall({
            call_id: data.call_id,
            state: "ringing",
            direction: data.direction || "inbound",
            caller_number: data.caller_number || "",
            caller_name: data.caller_name || null,
            company_name: data.company_name || null,
            company_id: data.company_id || null,
            last_order_date: data.last_order_date || null,
            open_ar_balance: data.open_ar_balance ?? null,
            recent_invoices: data.recent_invoices || [],
            started_at: new Date(),
            answered_at: null,
            ended_at: null,
            extraction: null,
          });
          setMinimized(false);
        } catch {}
      });

      es.addEventListener("call_answered", (e) => {
        try {
          const data = JSON.parse(e.data);
          setActiveCall((prev) =>
            prev && prev.call_id === data.call_id
              ? { ...prev, state: "active", answered_at: new Date() }
              : prev,
          );
        } catch {}
      });

      es.addEventListener("call_ended", (e) => {
        try {
          const data = JSON.parse(e.data);
          setActiveCall((prev) =>
            prev && prev.call_id === data.call_id
              ? { ...prev, ended_at: new Date() }
              : prev,
          );
        } catch {}
      });

      es.addEventListener("call_processed", (e) => {
        try {
          const data = JSON.parse(e.data);
          setActiveCall((prev) =>
            prev && prev.call_id === data.call_id
              ? {
                  ...prev,
                  state: "review",
                  extraction: data.extraction || null,
                }
              : prev,
          );
          setMinimized(false);

          // Process KB results from the extraction pipeline
          if (data.kb_results && Array.isArray(data.kb_results)) {
            const panels: KBPanelResult[] = data.kb_results.map(
              (r: Record<string, unknown>, i: number) => ({
                id: `${data.call_id}-kb-${i}`,
                query: r.query || "",
                query_type: r.query_type || "general",
                synthesis: r.synthesis || "",
                confidence: r.confidence || "low",
                pricing: r.pricing || [],
                source_documents: r.source_documents || [],
                dismissed: false,
                received_at: new Date(),
              }),
            );
            setKBPanels((prev) => [...prev, ...panels]);
          }
        } catch {}
      });

      es.addEventListener("kb_result", (e) => {
        try {
          const data = JSON.parse(e.data);
          const panel: KBPanelResult = {
            id: data.id || `kb-${Date.now()}`,
            query: data.query || "",
            query_type: data.query_type || "general",
            synthesis: data.synthesis || "",
            confidence: data.confidence || "low",
            pricing: data.pricing || [],
            source_documents: data.source_documents || [],
            dismissed: false,
            received_at: new Date(),
          };
          setKBPanels((prev) => [...prev, panel]);
        } catch {}
      });

      es.onerror = () => {
        es.close();
        setConnected(false);
        eventSourceRef.current = null;

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
        const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
        retryCountRef.current += 1;
        retryRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      cancelled = true;
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      if (retryRef.current) clearTimeout(retryRef.current);
      setConnected(false);
    };
  }, [user?.id, preferences.rc_overlay_enabled]);

  return (
    <CallContext.Provider
      value={{
        activeCall,
        minimized,
        preferences,
        connected,
        kbPanels,
        dismissCall,
        toggleMinimized,
        answerCall,
        updatePreferences,
        dismissKBPanel,
      }}
    >
      {children}
    </CallContext.Provider>
  );
}

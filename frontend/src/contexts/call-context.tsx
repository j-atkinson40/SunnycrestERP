// call-context.tsx — Global call state + SSE connection for RingCentral integration.
// Manages active call lifecycle: ringing → active → review → dismissed.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/contexts/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CallExtractionField {
  value: string;
  confidence: number;
}

export interface CallExtraction {
  deceased_name: CallExtractionField | null;
  vault_type: CallExtractionField | null;
  burial_date: CallExtractionField | null;
  burial_time: CallExtractionField | null;
  cemetery_name: CallExtractionField | null;
  grave_location: CallExtractionField | null;
  service_location: CallExtractionField | null;
  service_date: CallExtractionField | null;
  service_time: CallExtractionField | null;
  special_instructions: CallExtractionField | null;
  missing_fields: string[];
  draft_order_id: string | null;
}

export type CallState = "ringing" | "active" | "review";

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

interface CallContextValue {
  activeCall: ActiveCall | null;
  minimized: boolean;
  preferences: CallPreferences;
  connected: boolean;
  dismissCall: () => void;
  toggleMinimized: () => void;
  answerCall: (callId: string) => Promise<void>;
  updatePreferences: (prefs: Partial<CallPreferences>) => void;
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
  dismissCall: () => {},
  toggleMinimized: () => {},
  answerCall: async () => {},
  updatePreferences: () => {},
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

    function connect() {
      const token = localStorage.getItem("access_token");
      if (!token) return;

      const url = `/api/v1/integrations/ringcentral/events?token=${encodeURIComponent(token)}`;
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
        dismissCall,
        toggleMinimized,
        answerCall,
        updatePreferences,
      }}
    >
      {children}
    </CallContext.Provider>
  );
}

// CallOverlay.tsx — Global overlay for active calls (Call Intelligence).
// Shows ringing card → active call card → review card with AI extraction.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCall, type ActiveCall } from "@/contexts/call-context";
import { MinimizedCallPill } from "./MinimizedCallPill";
import { cn } from "@/lib/utils";
import {
  Phone,
  PhoneOff,
  PhoneIncoming,
  Minimize2,
  Clock,
  AlertCircle,
  CheckCircle2,
  FileText,
  Building2,
  User,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Timer hook
// ---------------------------------------------------------------------------

function useCallTimer(startedAt: Date | null) {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!startedAt) {
      setElapsed(0);
      return;
    }
    const tick = () =>
      setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));
    tick();
    intervalRef.current = setInterval(tick, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [startedAt]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function CallerInfo({ call }: { call: ActiveCall }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <User className="h-4 w-4 text-muted-foreground" />
        <span className="font-semibold text-sm">
          {call.caller_name || call.caller_number}
        </span>
      </div>
      {call.company_name && (
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {call.company_name}
          </span>
        </div>
      )}
      {call.caller_name && (
        <p className="text-xs text-muted-foreground pl-6">
          {call.caller_number}
        </p>
      )}
    </div>
  );
}

function CustomerContext({ call }: { call: ActiveCall }) {
  if (!call.last_order_date && call.open_ar_balance == null) return null;
  return (
    <div className="flex gap-4 text-xs text-muted-foreground border-t pt-2 mt-2">
      {call.last_order_date && (
        <span>Last order: {call.last_order_date}</span>
      )}
      {call.open_ar_balance != null && (
        <span>
          AR:{" "}
          <span
            className={cn(
              call.open_ar_balance > 0 ? "text-amber-600 font-medium" : "",
            )}
          >
            ${call.open_ar_balance.toLocaleString()}
          </span>
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// STATE 1 — Ringing
// ---------------------------------------------------------------------------

function RingingCard({
  call,
  onAnswer,
  onDismiss,
}: {
  call: ActiveCall;
  onAnswer: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="w-80 rounded-xl border bg-white shadow-2xl overflow-hidden animate-in slide-in-from-right-5 fade-in duration-300">
      {/* Header */}
      <div className="bg-green-50 border-b px-4 py-3 flex items-center gap-2">
        <PhoneIncoming className="h-5 w-5 text-green-600 animate-pulse" />
        <span className="text-sm font-semibold text-green-800">
          Incoming Call
        </span>
        <span className="ml-auto text-xs text-green-600 capitalize">
          {call.direction}
        </span>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        <CallerInfo call={call} />
        <CustomerContext call={call} />
      </div>

      {/* Actions */}
      <div className="flex gap-2 px-4 pb-4">
        <Button
          onClick={onAnswer}
          className="flex-1 bg-green-600 hover:bg-green-700 text-white"
          size="sm"
        >
          <Phone className="h-4 w-4 mr-1" />
          Answer
        </Button>
        <Button
          onClick={onDismiss}
          variant="outline"
          className="flex-1"
          size="sm"
        >
          <X className="h-4 w-4 mr-1" />
          Dismiss
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// STATE 2 — Active Call
// ---------------------------------------------------------------------------

function ActiveCallCard({
  call,
  onMinimize,
  onDismiss,
}: {
  call: ActiveCall;
  onMinimize: () => void;
  onDismiss: () => void;
}) {
  const navigate = useNavigate();
  const timer = useCallTimer(call.answered_at || call.started_at);
  const extraction = call.extraction;

  // Collect what we've heard so far
  const heardFields: { label: string; value: string }[] = [];
  if (extraction) {
    if (extraction.deceased_name?.value)
      heardFields.push({ label: "Deceased", value: extraction.deceased_name.value });
    if (extraction.vault_type?.value)
      heardFields.push({ label: "Vault", value: extraction.vault_type.value });
    if (extraction.burial_date?.value)
      heardFields.push({ label: "Burial date", value: extraction.burial_date.value });
    if (extraction.cemetery_name?.value)
      heardFields.push({ label: "Cemetery", value: extraction.cemetery_name.value });
  }

  const missingFields = extraction?.missing_fields ?? [];

  return (
    <div className="w-[380px] rounded-xl border bg-white shadow-2xl overflow-hidden animate-in slide-in-from-right-5 fade-in duration-300">
      {/* Header */}
      <div className="bg-blue-50 border-b px-4 py-3 flex items-center gap-2">
        <Phone className="h-5 w-5 text-blue-600" />
        <span className="text-sm font-semibold text-blue-800">
          Active Call
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="secondary" className="font-mono text-xs">
            <Clock className="h-3 w-3 mr-1" />
            {timer}
          </Badge>
          <button
            onClick={onMinimize}
            className="p-1 rounded hover:bg-blue-100 transition-colors"
          >
            <Minimize2 className="h-4 w-4 text-blue-600" />
          </button>
        </div>
      </div>

      {/* Caller */}
      <div className="px-4 pt-3">
        <CallerInfo call={call} />
      </div>

      {/* Still Needed — most prominent */}
      {missingFields.length > 0 && (
        <div className="mx-4 mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <span className="text-xs font-semibold text-amber-800 uppercase tracking-wide">
              Still Needed
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missingFields.map((f) => (
              <Badge
                key={f}
                variant="outline"
                className="text-xs border-amber-300 text-amber-700 bg-white"
              >
                {f.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Heard So Far */}
      {heardFields.length > 0 && (
        <div className="mx-4 mt-3 rounded-lg border bg-gray-50 p-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            Heard So Far
          </p>
          <div className="space-y-1">
            {heardFields.map((f) => (
              <div key={f.label} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{f.label}</span>
                <span className="font-medium">{f.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <CustomerContext call={call} />

      {/* Actions */}
      <div className="flex gap-2 p-4">
        <Button
          onClick={() => navigate("/order-station?from=call")}
          className="flex-1"
          size="sm"
        >
          <FileText className="h-4 w-4 mr-1" />
          Open Order Form
        </Button>
        <Button
          onClick={onDismiss}
          variant="outline"
          size="sm"
        >
          <PhoneOff className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// STATE 3 — Review (post-call AI extraction)
// ---------------------------------------------------------------------------

function ReviewCard({
  call,
  onDismiss,
}: {
  call: ActiveCall;
  onDismiss: () => void;
}) {
  const navigate = useNavigate();
  const extraction = call.extraction;
  if (!extraction) return null;

  const captured: { label: string; value: string; confidence: number }[] = [];
  const entries: [string, { value: string; confidence: number } | null][] = [
    ["Deceased", extraction.deceased_name],
    ["Vault type", extraction.vault_type],
    ["Burial date", extraction.burial_date],
    ["Burial time", extraction.burial_time],
    ["Cemetery", extraction.cemetery_name],
    ["Grave location", extraction.grave_location],
    ["Service location", extraction.service_location],
    ["Service date", extraction.service_date],
    ["Service time", extraction.service_time],
    ["Special instructions", extraction.special_instructions],
  ];

  for (const [label, field] of entries) {
    if (field?.value) {
      captured.push({ label, value: field.value, confidence: field.confidence });
    }
  }

  const missing = extraction.missing_fields ?? [];

  return (
    <div className="w-[420px] rounded-xl border bg-white shadow-2xl overflow-hidden animate-in slide-in-from-right-5 fade-in duration-300">
      {/* Header */}
      <div className="bg-purple-50 border-b px-4 py-3 flex items-center gap-2">
        <FileText className="h-5 w-5 text-purple-600" />
        <span className="text-sm font-semibold text-purple-800">
          Call Review
        </span>
        <button
          onClick={onDismiss}
          className="ml-auto p-1 rounded hover:bg-purple-100 transition-colors"
        >
          <X className="h-4 w-4 text-purple-600" />
        </button>
      </div>

      {/* Caller */}
      <div className="px-4 pt-3">
        <CallerInfo call={call} />
      </div>

      {/* Still Needed (red) */}
      {missing.length > 0 && (
        <div className="mx-4 mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <span className="text-xs font-semibold text-red-800 uppercase tracking-wide">
              Still Needed
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((f) => (
              <Badge
                key={f}
                variant="outline"
                className="text-xs border-red-300 text-red-700 bg-white"
              >
                {f.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Captured (green) */}
      {captured.length > 0 && (
        <div className="mx-4 mt-3 rounded-lg border border-green-200 bg-green-50 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <span className="text-xs font-semibold text-green-800 uppercase tracking-wide">
              Captured
            </span>
          </div>
          <div className="space-y-1.5">
            {captured.map((f) => (
              <div key={f.label} className="flex items-start justify-between text-xs gap-2">
                <span className="text-green-700 shrink-0">{f.label}</span>
                <div className="text-right">
                  <span className="font-medium text-green-900">{f.value}</span>
                  {f.confidence < 0.8 && (
                    <span className="ml-1 text-amber-600 text-[10px]">
                      ({Math.round(f.confidence * 100)}%)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 p-4">
        <Button
          onClick={() => {
            const url = extraction.draft_order_id
              ? `/ar/orders/${extraction.draft_order_id}`
              : "/order-station?from=call";
            navigate(url);
            onDismiss();
          }}
          className="flex-1"
          size="sm"
        >
          <FileText className="h-4 w-4 mr-1" />
          {extraction.draft_order_id ? "Review Draft Order" : "Create Order"}
        </Button>
        <Button onClick={onDismiss} variant="outline" size="sm">
          Dismiss
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Overlay
// ---------------------------------------------------------------------------

export function CallOverlay() {
  const { activeCall, minimized, preferences, dismissCall, toggleMinimized, answerCall } =
    useCall();

  if (!preferences.rc_overlay_enabled || !activeCall) return null;

  if (minimized) {
    return <MinimizedCallPill call={activeCall} onExpand={toggleMinimized} />;
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-md:top-2 max-md:right-2 max-md:left-2">
      {activeCall.state === "ringing" && (
        <RingingCard
          call={activeCall}
          onAnswer={() => answerCall(activeCall.call_id)}
          onDismiss={dismissCall}
        />
      )}
      {activeCall.state === "active" && (
        <ActiveCallCard
          call={activeCall}
          onMinimize={toggleMinimized}
          onDismiss={dismissCall}
        />
      )}
      {activeCall.state === "review" && (
        <ReviewCard call={activeCall} onDismiss={dismissCall} />
      )}
    </div>
  );
}

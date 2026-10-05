// call-log.tsx — Call log page showing recent calls with
// filtering, search, and expandable rows for extraction details.

import { useCallback, useEffect, useState } from "react";
import type { CallExtractionField } from "@/contexts/call-context";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Phone,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
  Search,
  ChevronDown,
  ChevronUp,
  Filter,
  Clock,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// ⚠️ IMPORTED, NOT REDECLARED. This file carried its own copy of
// `CallExtractionField` until 2026-10-05 — a second definition of the server's
// contract, which is how a shape disagreement went unnoticed on two surfaces at
// once. One definition, in call-context, which is where the SSE payload type
// already lives.

interface CallLogExtraction {
  deceased_name: CallExtractionField | null;
  vault_type: CallExtractionField | null;
  burial_date: CallExtractionField | null;
  burial_time: CallExtractionField | null;
  cemetery_name: CallExtractionField | null;
  grave_location: CallExtractionField | null;
  special_requests: CallExtractionField | null;
  missing_fields: string[];
  answered_fields: string[];
  draft_order_id: string | null;
}

interface CallLogEntry {
  id: string;
  call_id: string;
  direction: "inbound" | "outbound";
  status: "completed" | "missed" | "voicemail" | "rejected";
  caller_number: string;
  caller_name: string | null;
  company_name: string | null;
  company_id: string | null;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  extraction: CallLogExtraction | null;
  draft_order_id: string | null;
  recording_url: string | null;
}

type DirectionFilter = "all" | "inbound" | "outbound";
type StatusFilter = "all" | "completed" | "missed";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "--";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function DirectionIcon({ direction, status }: { direction: string; status: string }) {
  if (status === "missed") return <PhoneMissed className="h-4 w-4 text-red-500" />;
  if (direction === "outbound") return <PhoneOutgoing className="h-4 w-4 text-blue-500" />;
  return <PhoneIncoming className="h-4 w-4 text-green-500" />;
}

// ---------------------------------------------------------------------------
// Expanded row — extraction details
// ---------------------------------------------------------------------------

function ExtractionDetails({ extraction }: { extraction: CallLogExtraction }) {
  // ⚠️ THE THIRD HARDCODED LIST, RETIRED 2026-10-05. This page derived its own
  // captured set from ten extraction columns — identical in content to the call
  // overlay's ReviewCard and disagreeing with ActiveCallCard's four. None of the
  // three ever rendered: the client typed every field `{value, confidence}` and
  // the server sent flat strings.
  //
  // ⚠️ AND THIS PAGE IS ROUTED AT /calls, unlike the overlay — so the broken
  // captured display was reachable here. Both sets now come from the capture
  // engine. Values are not shown; see CallOverlay.tsx for why (template ids vs
  // extraction keys) and why that belongs to the unbuilt review layout.
  const captured = extraction.answered_fields ?? [];
  const missing = extraction.missing_fields ?? [];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-gray-50 border-t">
      {/* Captured */}
      {captured.length > 0 && (
        <div className="rounded-lg border border-green-200 bg-white p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <span className="text-xs font-semibold text-green-800 uppercase tracking-wide">
              Captured
            </span>
          </div>
          <div className="space-y-1.5">
            {captured.map((f) => (
              <div key={f} className="flex items-center gap-1.5 text-xs">
                <CheckCircle2 className="h-3 w-3 text-green-600 shrink-0" />
                <span className="font-medium">{f.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing */}
      {missing.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-white p-3">
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
                className="text-xs border-red-300 text-red-700"
              >
                {f.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {captured.length === 0 && missing.length === 0 && (
        <p className="text-sm text-muted-foreground col-span-2">
          No extraction data available for this call.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CallLogPage() {
  const [calls, setCalls] = useState<CallLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (directionFilter !== "all") params.set("direction", directionFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await apiClient.get(`/api/v1/integrations/ringcentral/calls?${params}`);
      setCalls(res.data.calls ?? res.data ?? []);
    } catch {
      setCalls([]);
    } finally {
      setLoading(false);
    }
  }, [search, directionFilter, statusFilter]);

  useEffect(() => {
    fetchCalls();
  }, [fetchCalls]);

  const filtered = calls; // server-side filtering; client array is already filtered

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Call Log</h1>
          <p className="text-sm text-muted-foreground">
            Recent calls with AI extraction details
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchCalls} disabled={loading}>
          <RefreshCw className={cn("h-4 w-4 mr-1", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, number, or company..."
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1">
          <Filter className="h-4 w-4 text-muted-foreground" />
          {(["all", "inbound", "outbound"] as DirectionFilter[]).map((d) => (
            <Button
              key={d}
              variant={directionFilter === d ? "default" : "outline"}
              size="sm"
              onClick={() => setDirectionFilter(d)}
              className="capitalize text-xs"
            >
              {d}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          {(["all", "completed", "missed"] as StatusFilter[]).map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(s)}
              className="capitalize text-xs"
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            Loading calls...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            <Phone className="h-8 w-8 mx-auto mb-2 opacity-30" />
            No calls found
          </div>
        ) : (
          <div className="divide-y">
            {/* Header row — desktop */}
            <div className="hidden md:grid grid-cols-[40px_1fr_1fr_100px_100px_40px] gap-3 px-4 py-2 bg-muted/50 text-xs font-medium text-muted-foreground">
              <span />
              <span>Caller</span>
              <span>Company</span>
              <span>Duration</span>
              <span>Time</span>
              <span />
            </div>

            {filtered.map((call) => {
              const expanded = expandedId === call.id;
              return (
                <div key={call.id}>
                  {/* Row */}
                  <button
                    onClick={() => setExpandedId(expanded ? null : call.id)}
                    className={cn(
                      "w-full text-left px-4 py-3 hover:bg-muted/30 transition-colors",
                      "grid grid-cols-[40px_1fr_auto] md:grid-cols-[40px_1fr_1fr_100px_100px_40px] gap-3 items-center",
                      expanded && "bg-muted/20",
                    )}
                  >
                    <DirectionIcon direction={call.direction} status={call.status} />

                    {/* Caller */}
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {call.caller_name || call.caller_number}
                      </p>
                      {call.caller_name && (
                        <p className="text-xs text-muted-foreground truncate">
                          {call.caller_number}
                        </p>
                      )}
                    </div>

                    {/* Company — desktop */}
                    <span className="hidden md:block text-sm text-muted-foreground truncate">
                      {call.company_name || "--"}
                    </span>

                    {/* Duration — desktop */}
                    <span className="hidden md:flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {formatDuration(call.duration_seconds)}
                    </span>

                    {/* Time — desktop */}
                    <span className="hidden md:block text-xs text-muted-foreground">
                      {formatDateTime(call.started_at)}
                    </span>

                    {/* Mobile meta + expand arrow */}
                    <div className="flex items-center gap-2 md:contents">
                      <div className="md:hidden text-right text-xs text-muted-foreground">
                        <p>{formatDuration(call.duration_seconds)}</p>
                        <p>{formatDateTime(call.started_at)}</p>
                      </div>
                      {call.extraction ? (
                        expanded ? (
                          <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )
                      ) : (
                        <span className="h-4 w-4" />
                      )}
                    </div>
                  </button>

                  {/* Expanded extraction */}
                  {expanded && call.extraction && (
                    <ExtractionDetails extraction={call.extraction} />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

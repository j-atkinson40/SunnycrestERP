/**
 * Operator Dashboard — platform health view showing tenant health scores,
 * notifications, repeat patterns, and open incidents.
 * Auto-refreshes every 60 seconds.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  getHealthSummary,
  getHealthIncidents,
  recalculateAllHealth,
  resolveIncident,
  triggerSmokeTest,
  getNotifications,
  dismissNotification,
  getRepeatPatterns,
  getHealthTimeline,
  getSystemHealth,
} from "@/services/platform-service";
import type {
  HealthSummaryResponse,
  HealthIncident,
  TenantHealthItem,
  PlatformNotificationItem,
  RepeatPattern,
  TimelineEntry,
  SystemHealthResponse,
} from "@/types/platform";
import {
  Activity,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Loader2,
  Play,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  X,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 0) return "Today";
  return `${days}d ago`;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "\u2014";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return remainMins > 0 ? `${hours}h ${remainMins}m` : `${hours}h`;
}

const SCORE_COLORS: Record<string, string> = {
  healthy: "border-green-300 bg-green-50 text-green-700 dark:border-green-600 dark:bg-green-950 dark:text-green-300",
  watch: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-600 dark:bg-amber-950 dark:text-amber-300",
  degraded: "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-600 dark:bg-orange-950 dark:text-orange-300",
  critical: "border-red-300 bg-red-50 text-red-700 dark:border-red-600 dark:bg-red-950 dark:text-red-300",
  unknown: "border-slate-300 bg-slate-50 text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-700",
  high: "border-orange-300 bg-orange-50 text-orange-700",
  medium: "border-amber-300 bg-amber-50 text-amber-700",
  low: "border-slate-300 bg-slate-50 text-slate-500",
};

const TIER_COLORS: Record<string, string> = {
  auto_fix: "border-blue-300 bg-blue-50 text-blue-700",
  auto_remediate: "border-purple-300 bg-purple-50 text-purple-700",
  escalate: "border-red-300 bg-red-50 text-red-700",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "border-amber-300 bg-amber-50 text-amber-700",
  in_progress: "border-blue-300 bg-blue-50 text-blue-700",
  resolved: "border-green-300 bg-green-50 text-green-700",
  escalated: "border-red-300 bg-red-50 text-red-700",
  ignored: "border-slate-300 bg-slate-50 text-slate-500",
};

const DOT_COLORS: Record<string, string> = {
  healthy: "bg-green-500",
  watch: "bg-amber-500",
  degraded: "bg-red-500",
  critical: "bg-red-600",
  unknown: "bg-slate-400",
};

const NOTIF_BAR_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

const SYSTEM_STATUS_COLORS: Record<string, { dot: string; text: string; label: string }> = {
  operational: { dot: "bg-green-500", text: "text-green-700 dark:text-green-300", label: "Operational" },
  degraded: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", label: "Degraded" },
  down: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300", label: "System down" },
};

// ---------------------------------------------------------------------------
// Small sub-components
// ---------------------------------------------------------------------------

function ComponentDot({ label, score }: { label: string; score: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5" title={`${label}: ${score}`}>
      <span className={`h-2 w-2 rounded-full ${DOT_COLORS[score] ?? DOT_COLORS.unknown}`} />
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

function SkeletonCard() {
  return (
    <Card className="p-4">
      <div className="h-4 w-16 animate-pulse rounded bg-slate-200" />
      <div className="mt-2 h-8 w-12 animate-pulse rounded bg-slate-200" />
    </Card>
  );
}

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-full animate-pulse rounded bg-slate-200" />
        </td>
      ))}
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Timeline dots component
// ---------------------------------------------------------------------------

function HealthTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <div className="flex items-center gap-0.5">
      {entries.map((e) => (
        <div
          key={e.date}
          className={`h-3 w-3 rounded-full ${DOT_COLORS[e.score] ?? DOT_COLORS.unknown} cursor-default`}
          title={`${e.date}: ${e.score} (${e.incident_count} incident${e.incident_count !== 1 ? "s" : ""})`}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PlatformHealthPage() {
  const [data, setData] = useState<HealthSummaryResponse | null>(null);
  const [incidents, setIncidents] = useState<HealthIncident[]>([]);
  const [incidentTotal, setIncidentTotal] = useState(0);
  const [notifications, setNotifications] = useState<PlatformNotificationItem[]>([]);
  const [notifTotal, setNotifTotal] = useState(0);
  const [patterns, setPatterns] = useState<RepeatPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [incidentsExpanded, setIncidentsExpanded] = useState(true);
  const [patternsExpanded, setPatternsExpanded] = useState(false);
  const [notifsShowAll, setNotifsShowAll] = useState(false);
  const [filterTenantId, setFilterTenantId] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveAction, setResolveAction] = useState("");
  const [justUpdated, setJustUpdated] = useState(false);
  const [expandedTenantId, setExpandedTenantId] = useState<string | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null);
  const fadeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // ---- Data fetching ----

  const fetchData = useCallback(
    async (showUpdated = false) => {
      try {
        const [summaryRes, incidentRes, notifRes, patternRes, sysRes] = await Promise.all([
          getHealthSummary(),
          getHealthIncidents({
            tenant_id: filterTenantId ?? undefined,
            limit: 50,
          }),
          getNotifications({ dismissed: false }),
          getRepeatPatterns(),
          getSystemHealth().catch(() => null),
        ]);
        setData(summaryRes);
        setIncidents(incidentRes.incidents);
        setIncidentTotal(incidentRes.total);
        setNotifications(notifRes.notifications);
        setNotifTotal(notifRes.total);
        setPatterns(patternRes.patterns);
        if (sysRes) setSystemHealth(sysRes);
        if (showUpdated) {
          setJustUpdated(true);
          clearTimeout(fadeTimer.current);
          fadeTimer.current = setTimeout(() => setJustUpdated(false), 3000);
        }
      } catch {
        if (loading) toast.error("Failed to load platform health data");
      } finally {
        setLoading(false);
      }
    },
    [filterTenantId, loading]
  );

  useEffect(() => {
    fetchData();
  }, [filterTenantId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const interval = setInterval(() => fetchData(true), 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ---- Handlers ----

  async function handleRecalculate() {
    setRecalculating(true);
    try {
      const result = await recalculateAllHealth();
      toast.success(`Health scores updated \u2014 ${result.recalculated} tenant(s) recalculated`);
      await fetchData(true);
    } catch {
      toast.error("Failed to recalculate health scores");
    } finally {
      setRecalculating(false);
    }
  }

  async function handleResolve(incidentId: string) {
    if (!resolveAction.trim()) {
      toast.error("Please describe the resolution action");
      return;
    }
    try {
      await resolveIncident(incidentId, resolveAction.trim());
      toast.success("Incident resolved");
      setResolvingId(null);
      setResolveAction("");
      await fetchData(true);
    } catch {
      toast.error("Failed to resolve incident");
    }
  }

  async function handleDismissNotif(id: string) {
    try {
      await dismissNotification(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      setNotifTotal((prev) => Math.max(0, prev - 1));
    } catch {
      toast.error("Failed to dismiss notification");
    }
  }

  // ---- Loading state ----

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Health</h1>
          <p className="text-muted-foreground">Tenant health scores and open incidents</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
        <Card className="overflow-hidden">
          <table className="w-full"><tbody><SkeletonRow /><SkeletonRow /><SkeletonRow /></tbody></table>
        </Card>
      </div>
    );
  }

  const summary = data?.summary;
  const tenants = data?.tenants ?? [];

  if (summary && summary.total_tenants === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Health</h1>
          <p className="text-muted-foreground">Tenant health scores and open incidents</p>
        </div>
        <Card className="flex flex-col items-center justify-center py-16">
          <Activity className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg font-medium">No tenants found</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Tenant health scores will appear here once tenants are onboarded.
          </p>
        </Card>
      </div>
    );
  }

  const visibleNotifs = notifsShowAll ? notifications : notifications.slice(0, 5);

  // ---- Render ----

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Platform Health</h1>
            {systemHealth && (() => {
              const s = SYSTEM_STATUS_COLORS[systemHealth.status] ?? SYSTEM_STATUS_COLORS.degraded;
              return (
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.text}`}>
                  <span className={`h-2 w-2 rounded-full ${s.dot}`} />
                  {s.label}
                </span>
              );
            })()}
          </div>
          <p className="text-muted-foreground">Tenant health scores and open incidents</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={handleRecalculate} disabled={recalculating} size="sm">
            {recalculating ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            )}
            Recalculate all
          </Button>
          <span className="text-xs text-muted-foreground">
            {justUpdated ? (
              <span className="text-green-600">Updated just now</span>
            ) : summary?.last_updated ? (
              `Last updated ${timeAgo(summary.last_updated)}`
            ) : (
              "Not yet calculated"
            )}
          </span>
        </div>
      </div>

      {/* ================================================================ */}
      {/* NOTIFICATIONS BANNER                                             */}
      {/* ================================================================ */}
      {notifications.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Bell className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-semibold">Platform alerts ({notifTotal})</span>
          </div>
          <div className="space-y-2">
            {visibleNotifs.map((n) => (
              <Card key={n.id} className="flex overflow-hidden">
                <div className={`w-1 shrink-0 ${NOTIF_BAR_COLORS[n.level] ?? NOTIF_BAR_COLORS.info}`} />
                <div className="flex flex-1 items-start justify-between gap-3 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{n.title}</p>
                    {n.body && (
                      <p className="mt-0.5 line-clamp-3 text-xs text-muted-foreground">{n.body}</p>
                    )}
                    <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      {n.tenant_name && <span>{n.tenant_name}</span>}
                      {n.tenant_name && <span>&middot;</span>}
                      <span>{timeAgo(n.created_at)}</span>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 shrink-0 p-0"
                    onClick={() => handleDismissNotif(n.id)}
                    title="Dismiss"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
          {notifications.length > 5 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-1 text-xs"
              onClick={() => setNotifsShowAll((v) => !v)}
            >
              {notifsShowAll ? "Show less" : `Show all (${notifications.length})`}
            </Button>
          )}
        </div>
      )}

      {/* ================================================================ */}
      {/* SUMMARY CARDS (5)                                                */}
      {/* ================================================================ */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card className="border-green-200 bg-green-50/50 p-4 dark:border-green-800 dark:bg-green-950/30">
          <div className="text-sm font-medium text-green-700 dark:text-green-300">Healthy</div>
          <div className="mt-1 text-3xl font-bold text-green-800 dark:text-green-200">
            {summary?.healthy ?? 0}
          </div>
        </Card>

        <Card className="border-amber-200 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <div className="text-sm font-medium text-amber-700 dark:text-amber-300">Watch</div>
          <div className="mt-1 text-3xl font-bold text-amber-800 dark:text-amber-200">
            {summary?.watch ?? 0}
          </div>
        </Card>

        <Card className="border-red-200 bg-red-50/50 p-4 dark:border-red-800 dark:bg-red-950/30">
          <div className="text-sm font-medium text-red-700 dark:text-red-300">Degraded / Critical</div>
          <div className="mt-1 text-3xl font-bold text-red-800 dark:text-red-200">
            {(summary?.degraded ?? 0) + (summary?.critical ?? 0)}
          </div>
          {(summary?.critical ?? 0) > 0 && (
            <Badge variant="destructive" className="mt-1">{summary!.critical} critical</Badge>
          )}
        </Card>

        <Card className="border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-800/30">
          <div className="text-sm font-medium text-slate-600 dark:text-slate-400">Unknown</div>
          <div className="mt-1 text-3xl font-bold text-slate-700 dark:text-slate-300">
            {summary?.unknown ?? 0}
          </div>
          {(summary?.unknown ?? 0) > 0 && (
            <span className="mt-1 text-xs text-muted-foreground">Not yet calculated</span>
          )}
        </Card>

        <Card className="border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-800/30">
          <div className="flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-400">
            <Clock className="h-3.5 w-3.5" />
            Avg resolution (7d)
          </div>
          <div className="mt-1 text-3xl font-bold text-slate-700 dark:text-slate-300">
            {formatDuration(summary?.avg_resolution_seconds_7d ?? null)}
          </div>
        </Card>
      </div>

      {/* Unknown scores advisory */}
      {summary && summary.unknown > 0 && summary.unknown === summary.total_tenants && (
        <Card className="flex items-center gap-3 border-amber-200 bg-amber-50/50 p-4">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
          <div>
            <p className="font-medium text-amber-800">Health scores not yet calculated</p>
            <p className="text-sm text-amber-700">
              Scores calculate nightly at 2:15am. Click <strong>Recalculate all</strong> to run now.
            </p>
          </div>
        </Card>
      )}

      {/* ================================================================ */}
      {/* TENANT HEALTH TABLE                                              */}
      {/* ================================================================ */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-2.5 text-left font-medium">Tenant</th>
                <th className="px-4 py-2.5 text-left font-medium">Health</th>
                <th className="px-4 py-2.5 text-left font-medium">Components</th>
                <th className="px-4 py-2.5 text-left font-medium">Open Incidents</th>
                <th className="px-4 py-2.5 text-left font-medium">Last Incident</th>
                <th className="px-4 py-2.5 text-left font-medium">Last Calculated</th>
                <th className="px-4 py-2.5 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {tenants.map((t) => (
                <TenantRowWithDrillDown
                  key={t.tenant_id}
                  tenant={t}
                  isExpanded={expandedTenantId === t.tenant_id}
                  onToggleExpand={() =>
                    setExpandedTenantId((prev) => (prev === t.tenant_id ? null : t.tenant_id))
                  }
                  onFilterIncidents={(id) => {
                    setFilterTenantId(id);
                    setIncidentsExpanded(true);
                  }}
                  onRefresh={() => fetchData(true)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ================================================================ */}
      {/* REPEAT PATTERNS                                                  */}
      {/* ================================================================ */}
      <div>
        <button
          onClick={() => setPatternsExpanded((v) => !v)}
          className="mb-3 flex items-center gap-2 text-lg font-semibold"
        >
          <TrendingUp className="h-4 w-4" />
          Repeat patterns ({patterns.length})
          {patternsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {patternsExpanded && (
          <>
            {patterns.length === 0 ? (
              <Card className="flex flex-col items-center justify-center py-8">
                <CheckCircle2 className="mb-2 h-6 w-6 text-green-500" />
                <p className="text-sm font-medium">No repeat patterns</p>
                <p className="mt-0.5 text-xs text-muted-foreground">No fingerprint has 2+ incidents in 30 days.</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {patterns.map((p) => (
                  <Card key={p.fingerprint} className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={SEVERITY_COLORS.medium}>{p.category}</Badge>
                          <span className="truncate text-sm">
                            {p.first_error.length > 60 ? p.first_error.slice(0, 60) + "\u2026" : p.first_error}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                          <span className="font-medium">{p.count} occurrences</span>
                          <span>&middot;</span>
                          <span>{p.tenants_affected.length} tenant{p.tenants_affected.length !== 1 ? "s" : ""}</span>
                          <span>&middot;</span>
                          <span>last seen {timeAgo(p.last_seen)}</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        {/* Resolution rate bar */}
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-200">
                            <div
                              className="h-full rounded-full bg-green-500 transition-all"
                              style={{ width: `${Math.round(p.resolution_rate * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-muted-foreground">
                            {Math.round(p.resolution_rate * 100)}% resolved
                          </span>
                        </div>
                        {p.avg_resolution_seconds != null && (
                          <span className="text-xs text-muted-foreground">
                            avg {formatDuration(p.avg_resolution_seconds)}
                          </span>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* ================================================================ */}
      {/* RECENT INCIDENTS                                                 */}
      {/* ================================================================ */}
      <div>
        <button
          onClick={() => setIncidentsExpanded((v) => !v)}
          className="mb-3 flex items-center gap-2 text-lg font-semibold"
        >
          Recent incidents ({incidentTotal})
          {incidentsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>

        {filterTenantId && (
          <div className="mb-3 flex items-center gap-2">
            <Badge variant="outline">Filtered by tenant</Badge>
            <Button variant="ghost" size="sm" onClick={() => setFilterTenantId(null)}>
              Clear filter
            </Button>
          </div>
        )}

        {incidentsExpanded && (
          <>
            {incidents.length === 0 ? (
              <Card className="flex flex-col items-center justify-center py-12">
                <CheckCircle2 className="mb-2 h-8 w-8 text-green-500" />
                <p className="font-medium">No open incidents</p>
                <p className="mt-1 text-sm text-muted-foreground">All systems healthy.</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {incidents.map((inc) => (
                  <IncidentCard
                    key={inc.id}
                    incident={inc}
                    resolvingId={resolvingId}
                    resolveAction={resolveAction}
                    onStartResolve={(id) => { setResolvingId(id); setResolveAction(""); }}
                    onCancelResolve={() => { setResolvingId(null); setResolveAction(""); }}
                    onResolveActionChange={setResolveAction}
                    onResolve={handleResolve}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Incident card sub-component
// ---------------------------------------------------------------------------

function IncidentCard({
  incident: inc,
  resolvingId,
  resolveAction,
  onStartResolve,
  onCancelResolve,
  onResolveActionChange,
  onResolve,
}: {
  incident: HealthIncident;
  resolvingId: string | null;
  resolveAction: string;
  onStartResolve: (id: string) => void;
  onCancelResolve: () => void;
  onResolveActionChange: (v: string) => void;
  onResolve: (id: string) => void;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={SEVERITY_COLORS[inc.severity] ?? SEVERITY_COLORS.medium}>
              {inc.severity}
            </Badge>
            <span className="text-sm font-bold">{inc.category}</span>
          </div>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {inc.error_message
              ? inc.error_message.length > 80 ? inc.error_message.slice(0, 80) + "\u2026" : inc.error_message
              : "No error message"}
          </p>
          {inc.resolution_action && inc.resolution_status === "resolved" && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground/70 italic">
              {inc.resolution_action.length > 100 ? inc.resolution_action.slice(0, 100) + "\u2026" : inc.resolution_action}
            </p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {inc.tenant_name && <span>{inc.tenant_name}</span>}
            {inc.tenant_name && inc.source && <span>&middot;</span>}
            {inc.source && <span>{inc.source}</span>}
            <span>&middot;</span>
            <span>{timeAgo(inc.created_at)}</span>
            {inc.was_repeat && (
              <><span>&middot;</span><span className="text-amber-600">repeat</span></>
            )}
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <div className="flex items-center gap-1.5">
            {inc.resolution_tier && (
              <Badge variant="outline" className={TIER_COLORS[inc.resolution_tier] ?? TIER_COLORS.auto_fix}>
                {inc.resolution_tier}
              </Badge>
            )}
            <Badge variant="outline" className={STATUS_COLORS[inc.resolution_status] ?? STATUS_COLORS.pending}>
              {inc.resolution_status}
            </Badge>
          </div>

          {(inc.resolution_status === "pending" || inc.resolution_status === "in_progress") && (
            <>
              {resolvingId === inc.id ? (
                <div className="mt-1 flex items-center gap-1.5">
                  <input
                    type="text"
                    placeholder="Resolution action"
                    value={resolveAction}
                    onChange={(e) => onResolveActionChange(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") onResolve(inc.id); }}
                    className="h-7 w-48 rounded border px-2 text-xs"
                    autoFocus
                  />
                  <Button size="sm" variant="default" className="h-7 text-xs" onClick={() => onResolve(inc.id)}>
                    Mark resolved
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={onCancelResolve}>
                    Cancel
                  </Button>
                </div>
              ) : (
                <Button size="sm" variant="outline" className="mt-1 h-7 text-xs" onClick={() => onStartResolve(inc.id)}>
                  Resolve
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Tenant row with inline drill-down
// ---------------------------------------------------------------------------

function TenantRowWithDrillDown({
  tenant,
  isExpanded,
  onToggleExpand,
  onFilterIncidents,
  onRefresh,
}: {
  tenant: TenantHealthItem;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onFilterIncidents: (tenantId: string) => void;
  onRefresh: () => void;
}) {
  const [smokeRunning, setSmokeRunning] = useState(false);
  const t = tenant;
  const cs = t.component_scores;
  const lastCalcAgo = timeAgo(t.last_calculated);
  const isStale = !t.last_calculated || Date.now() - new Date(t.last_calculated).getTime() > 24 * 60 * 60 * 1000;

  async function handleSmokeTest(e: React.MouseEvent) {
    e.stopPropagation();
    setSmokeRunning(true);
    try {
      const result = await triggerSmokeTest(t.tenant_id);
      if (result.error) {
        toast(result.error, { description: "Run smoke tests locally or via CI." });
      } else if (result.failed > 0) {
        toast.warning(`Smoke test complete \u2014 ${result.incidents_logged} incident(s) logged`, {
          description: `${result.passed} passed, ${result.failed} failed (${Math.round(result.duration_ms / 1000)}s)`,
        });
      } else {
        toast.success("Smoke test passed \u2014 all healthy", {
          description: `${result.passed} passed (${Math.round(result.duration_ms / 1000)}s)`,
        });
      }
      onRefresh();
    } catch {
      toast.error("Failed to trigger smoke test");
    } finally {
      setSmokeRunning(false);
    }
  }

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
        onClick={onToggleExpand}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-1.5">
            {isExpanded ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
            <div>
              <div className="font-medium">{t.tenant_name}</div>
              <div className="text-xs text-muted-foreground">{t.tenant_id.slice(0, 12)}...</div>
            </div>
          </div>
        </td>
        <td className="px-4 py-3">
          <Badge variant="outline" className={SCORE_COLORS[t.score] ?? SCORE_COLORS.unknown}>{t.score}</Badge>
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2.5">
            <ComponentDot label="API" score={cs.api} />
            <ComponentDot label="Auth" score={cs.auth} />
            <ComponentDot label="Data" score={cs.data} />
            <ComponentDot label="Jobs" score={cs.background_job} />
          </div>
        </td>
        <td className="px-4 py-3">
          {t.open_incident_count === 0 ? (
            <span className="text-muted-foreground">&mdash;</span>
          ) : (
            <span className="font-bold">{t.open_incident_count}</span>
          )}
        </td>
        <td className="px-4 py-3 text-muted-foreground">{timeAgo(t.last_incident_at)}</td>
        <td className="px-4 py-3">
          <span className="flex items-center gap-1.5">
            {isStale && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
            <span className={isStale ? "text-amber-600" : "text-muted-foreground"}>{lastCalcAgo}</span>
          </span>
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleSmokeTest} disabled={smokeRunning} title="Run smoke tests">
              {smokeRunning ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Play className="mr-1 h-3 w-3" />}
              {smokeRunning ? "Running\u2026" : "Smoke"}
            </Button>
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => onFilterIncidents(t.tenant_id)}>
              Incidents &rarr;
            </Button>
          </div>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="bg-slate-50/50 p-0 dark:bg-slate-900/30">
            <TenantDrillDown tenantId={t.tenant_id} tenantName={t.tenant_name} />
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Tenant drill-down panel
// ---------------------------------------------------------------------------

function TenantDrillDown({ tenantId, tenantName }: { tenantId: string; tenantName: string }) {
  const [tab, setTab] = useState<"incidents" | "timeline">("incidents");
  const [drillIncidents, setDrillIncidents] = useState<HealthIncident[]>([]);
  const [drillTotal, setDrillTotal] = useState(0);
  const [drillLoading, setDrillLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);

  const PAGE_SIZE = 20;

  // Load incidents
  useEffect(() => {
    setDrillLoading(true);
    getHealthIncidents({
      tenant_id: tenantId,
      status: statusFilter ?? undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    })
      .then((res) => {
        setDrillIncidents(res.incidents);
        setDrillTotal(res.total);
      })
      .catch(() => toast.error("Failed to load tenant incidents"))
      .finally(() => setDrillLoading(false));
  }, [tenantId, statusFilter, page]);

  // Load timeline on tab switch
  useEffect(() => {
    if (tab === "timeline" && timeline.length === 0) {
      setTimelineLoading(true);
      getHealthTimeline(tenantId, 30)
        .then((res) => setTimeline(res.timeline))
        .catch(() => toast.error("Failed to load health timeline"))
        .finally(() => setTimelineLoading(false));
    }
  }, [tab, tenantId, timeline.length]);

  const totalPages = Math.ceil(drillTotal / PAGE_SIZE);

  return (
    <div className="border-t px-6 py-4">
      <div className="mb-3 flex items-center gap-4">
        <span className="text-sm font-semibold">{tenantName}</span>
        <div className="flex gap-1">
          <Button
            variant={tab === "incidents" ? "default" : "ghost"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setTab("incidents")}
          >
            Incident history
          </Button>
          <Button
            variant={tab === "timeline" ? "default" : "ghost"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setTab("timeline")}
          >
            Health timeline
          </Button>
        </div>
      </div>

      {tab === "incidents" && (
        <>
          {/* Status filter chips */}
          <div className="mb-3 flex gap-1">
            {[null, "pending", "resolved", "escalated"].map((s) => (
              <Button
                key={s ?? "all"}
                variant={statusFilter === s ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs"
                onClick={() => { setStatusFilter(s); setPage(0); }}
              >
                {s ?? "All"}
              </Button>
            ))}
          </div>

          {drillLoading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : drillIncidents.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No incidents found.</p>
          ) : (
            <div className="space-y-1.5">
              {drillIncidents.map((inc) => (
                <div key={inc.id} className="rounded border bg-white p-2.5 text-xs dark:bg-slate-800">
                  <div className="flex items-center gap-1.5">
                    <Badge variant="outline" className={`text-[10px] ${SEVERITY_COLORS[inc.severity] ?? SEVERITY_COLORS.medium}`}>
                      {inc.severity}
                    </Badge>
                    <span className="font-semibold">{inc.category}</span>
                    <Badge variant="outline" className={`text-[10px] ${STATUS_COLORS[inc.resolution_status] ?? STATUS_COLORS.pending}`}>
                      {inc.resolution_status}
                    </Badge>
                  </div>
                  <p className="mt-1 truncate text-muted-foreground">
                    {inc.error_message
                      ? inc.error_message.length > 80 ? inc.error_message.slice(0, 80) + "\u2026" : inc.error_message
                      : "No error message"}
                  </p>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    {inc.source && <span>{inc.source}</span>}
                    {inc.source && <span>&middot;</span>}
                    <span>{timeAgo(inc.created_at)}</span>
                  </div>
                  {inc.resolution_action && inc.resolution_status === "resolved" && (
                    <p className="mt-0.5 truncate text-[11px] italic text-muted-foreground/70">
                      {inc.resolution_action.length > 100 ? inc.resolution_action.slice(0, 100) + "\u2026" : inc.resolution_action}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-3 flex items-center justify-center gap-2">
              <Button size="sm" variant="outline" className="h-6 text-xs" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Prev
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {page + 1} of {totalPages}
              </span>
              <Button size="sm" variant="outline" className="h-6 text-xs" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {tab === "timeline" && (
        <div className="py-2">
          {timelineLoading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : timeline.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No timeline data.</p>
          ) : (
            <div>
              <p className="mb-2 text-xs text-muted-foreground">
                Last 30 days &mdash; hover for details. Oldest on left, newest on right.
              </p>
              <HealthTimeline entries={timeline} />
              <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" /> healthy</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" /> watch</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" /> degraded</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-red-600" /> critical</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

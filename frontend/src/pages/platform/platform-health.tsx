/**
 * Operator Dashboard — platform health view showing tenant health scores
 * and open incidents. Auto-refreshes every 60 seconds.
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
} from "@/services/platform-service";
import type {
  HealthSummaryResponse,
  HealthIncident,
  TenantHealthItem,
} from "@/types/platform";
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  AlertTriangle,
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

// ---------------------------------------------------------------------------
// Component dot for health components
// ---------------------------------------------------------------------------

function ComponentDot({ label, score }: { label: string; score: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5" title={`${label}: ${score}`}>
      <span className={`h-2 w-2 rounded-full ${DOT_COLORS[score] ?? DOT_COLORS.unknown}`} />
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton components
// ---------------------------------------------------------------------------

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
// Main component
// ---------------------------------------------------------------------------

export default function PlatformHealthPage() {
  const [data, setData] = useState<HealthSummaryResponse | null>(null);
  const [incidents, setIncidents] = useState<HealthIncident[]>([]);
  const [incidentTotal, setIncidentTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [incidentsExpanded, setIncidentsExpanded] = useState(true);
  const [filterTenantId, setFilterTenantId] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveAction, setResolveAction] = useState("");
  const [justUpdated, setJustUpdated] = useState(false);
  const fadeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // ---- Data fetching ----

  const fetchData = useCallback(
    async (showUpdated = false) => {
      try {
        const [summaryRes, incidentRes] = await Promise.all([
          getHealthSummary(),
          getHealthIncidents({
            tenant_id: filterTenantId ?? undefined,
            limit: 50,
          }),
        ]);
        setData(summaryRes);
        setIncidents(incidentRes.incidents);
        setIncidentTotal(incidentRes.total);
        if (showUpdated) {
          setJustUpdated(true);
          clearTimeout(fadeTimer.current);
          fadeTimer.current = setTimeout(() => setJustUpdated(false), 3000);
        }
      } catch {
        // Only toast on initial load
        if (loading) toast.error("Failed to load platform health data");
      } finally {
        setLoading(false);
      }
    },
    [filterTenantId, loading]
  );

  // Initial load
  useEffect(() => {
    fetchData();
  }, [filterTenantId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => fetchData(true), 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ---- Recalculate ----

  async function handleRecalculate() {
    setRecalculating(true);
    try {
      const result = await recalculateAllHealth();
      toast.success(
        `Health scores updated — ${result.recalculated} tenant(s) recalculated`
      );
      await fetchData(true);
    } catch {
      toast.error("Failed to recalculate health scores");
    } finally {
      setRecalculating(false);
    }
  }

  // ---- Resolve incident ----

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

  // ---- Loading state ----

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Health</h1>
          <p className="text-muted-foreground">
            Tenant health scores and open incidents
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <Card className="overflow-hidden">
          <table className="w-full">
            <tbody>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </tbody>
          </table>
        </Card>
      </div>
    );
  }

  const summary = data?.summary;
  const tenants = data?.tenants ?? [];
  // ---- Empty state: no tenants ----

  if (summary && summary.total_tenants === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Health</h1>
          <p className="text-muted-foreground">
            Tenant health scores and open incidents
          </p>
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

  // ---- Render ----

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Platform Health</h1>
          <p className="text-muted-foreground">
            Tenant health scores and open incidents
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button
            onClick={handleRecalculate}
            disabled={recalculating}
            size="sm"
          >
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

      {/* Section 1: Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-green-200 bg-green-50/50 p-4 dark:border-green-800 dark:bg-green-950/30">
          <div className="text-sm font-medium text-green-700 dark:text-green-300">
            Healthy
          </div>
          <div className="mt-1 text-3xl font-bold text-green-800 dark:text-green-200">
            {summary?.healthy ?? 0}
          </div>
        </Card>

        <Card className="border-amber-200 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <div className="text-sm font-medium text-amber-700 dark:text-amber-300">
            Watch
          </div>
          <div className="mt-1 text-3xl font-bold text-amber-800 dark:text-amber-200">
            {summary?.watch ?? 0}
          </div>
        </Card>

        <Card className="border-red-200 bg-red-50/50 p-4 dark:border-red-800 dark:bg-red-950/30">
          <div className="text-sm font-medium text-red-700 dark:text-red-300">
            Degraded / Critical
          </div>
          <div className="mt-1 text-3xl font-bold text-red-800 dark:text-red-200">
            {(summary?.degraded ?? 0) + (summary?.critical ?? 0)}
          </div>
          {(summary?.critical ?? 0) > 0 && (
            <Badge
              variant="destructive"
              className="mt-1"
            >
              {summary!.critical} critical
            </Badge>
          )}
        </Card>

        <Card className="border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-800/30">
          <div className="text-sm font-medium text-slate-600 dark:text-slate-400">
            Unknown
          </div>
          <div className="mt-1 text-3xl font-bold text-slate-700 dark:text-slate-300">
            {summary?.unknown ?? 0}
          </div>
          {(summary?.unknown ?? 0) > 0 && (
            <span className="mt-1 text-xs text-muted-foreground">
              Not yet calculated
            </span>
          )}
        </Card>
      </div>

      {/* Unknown scores advisory */}
      {summary && summary.unknown > 0 && summary.unknown === summary.total_tenants && (
        <Card className="flex items-center gap-3 border-amber-200 bg-amber-50/50 p-4">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
          <div>
            <p className="font-medium text-amber-800">
              Health scores not yet calculated
            </p>
            <p className="text-sm text-amber-700">
              Scores calculate nightly at 2:15am. Click{" "}
              <strong>Recalculate all</strong> to run now.
            </p>
          </div>
        </Card>
      )}

      {/* Section 2: Tenant health table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-2.5 text-left font-medium">Tenant</th>
                <th className="px-4 py-2.5 text-left font-medium">Health</th>
                <th className="px-4 py-2.5 text-left font-medium">
                  Components
                </th>
                <th className="px-4 py-2.5 text-left font-medium">
                  Open Incidents
                </th>
                <th className="px-4 py-2.5 text-left font-medium">
                  Last Incident
                </th>
                <th className="px-4 py-2.5 text-left font-medium">
                  Last Calculated
                </th>
                <th className="px-4 py-2.5 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {tenants.map((t) => (
                <TenantRow
                  key={t.tenant_id}
                  tenant={t}
                  onFilterIncidents={(id) => {
                    setFilterTenantId(id);
                    setIncidentsExpanded(true);
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Section 3: Recent incidents */}
      <div>
        <button
          onClick={() => setIncidentsExpanded((v) => !v)}
          className="mb-3 flex items-center gap-2 text-lg font-semibold"
        >
          Recent incidents ({incidentTotal})
          {incidentsExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {filterTenantId && (
          <div className="mb-3 flex items-center gap-2">
            <Badge variant="outline">
              Filtered by tenant
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilterTenantId(null)}
            >
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
                <p className="mt-1 text-sm text-muted-foreground">
                  All systems healthy.
                </p>
              </Card>
            ) : (
              <div className="space-y-2">
                {incidents.map((inc) => (
                  <Card key={inc.id} className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      {/* Left side */}
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant="outline"
                            className={
                              SEVERITY_COLORS[inc.severity] ?? SEVERITY_COLORS.medium
                            }
                          >
                            {inc.severity}
                          </Badge>
                          <span className="text-sm font-bold">
                            {inc.category}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-sm text-muted-foreground">
                          {inc.error_message
                            ? inc.error_message.length > 80
                              ? inc.error_message.slice(0, 80) + "..."
                              : inc.error_message
                            : "No error message"}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                          {inc.tenant_name && (
                            <span>{inc.tenant_name}</span>
                          )}
                          {inc.tenant_name && inc.source && (
                            <span>&middot;</span>
                          )}
                          {inc.source && <span>{inc.source}</span>}
                          <span>&middot;</span>
                          <span>{timeAgo(inc.created_at)}</span>
                          {inc.was_repeat && (
                            <>
                              <span>&middot;</span>
                              <span className="text-amber-600">repeat</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Right side */}
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <div className="flex items-center gap-1.5">
                          {inc.resolution_tier && (
                            <Badge
                              variant="outline"
                              className={
                                TIER_COLORS[inc.resolution_tier] ??
                                TIER_COLORS.auto_fix
                              }
                            >
                              {inc.resolution_tier}
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={
                              STATUS_COLORS[inc.resolution_status] ??
                              STATUS_COLORS.pending
                            }
                          >
                            {inc.resolution_status}
                          </Badge>
                        </div>

                        {(inc.resolution_status === "pending" ||
                          inc.resolution_status === "in_progress") && (
                          <>
                            {resolvingId === inc.id ? (
                              <div className="mt-1 flex items-center gap-1.5">
                                <input
                                  type="text"
                                  placeholder="Resolution action"
                                  value={resolveAction}
                                  onChange={(e) =>
                                    setResolveAction(e.target.value)
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter")
                                      handleResolve(inc.id);
                                  }}
                                  className="h-7 w-48 rounded border px-2 text-xs"
                                  autoFocus
                                />
                                <Button
                                  size="sm"
                                  variant="default"
                                  className="h-7 text-xs"
                                  onClick={() => handleResolve(inc.id)}
                                >
                                  Mark resolved
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 text-xs"
                                  onClick={() => {
                                    setResolvingId(null);
                                    setResolveAction("");
                                  }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                className="mt-1 h-7 text-xs"
                                onClick={() => {
                                  setResolvingId(inc.id);
                                  setResolveAction("");
                                }}
                              >
                                Resolve
                              </Button>
                            )}
                          </>
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
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tenant row sub-component
// ---------------------------------------------------------------------------

function TenantRow({
  tenant,
  onFilterIncidents,
}: {
  tenant: TenantHealthItem;
  onFilterIncidents: (tenantId: string) => void;
}) {
  const t = tenant;
  const cs = t.component_scores;
  const lastCalcAgo = timeAgo(t.last_calculated);
  const isStale =
    !t.last_calculated ||
    Date.now() - new Date(t.last_calculated).getTime() > 24 * 60 * 60 * 1000;

  return (
    <tr className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
      <td className="px-4 py-3">
        <div className="font-medium">{t.tenant_name}</div>
        <div className="text-xs text-muted-foreground">
          {t.tenant_id.slice(0, 12)}...
        </div>
      </td>
      <td className="px-4 py-3">
        <Badge
          variant="outline"
          className={SCORE_COLORS[t.score] ?? SCORE_COLORS.unknown}
        >
          {t.score}
        </Badge>
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
          <span className="font-bold">
            {t.open_incident_count}
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-muted-foreground">
        {timeAgo(t.last_incident_at)}
      </td>
      <td className="px-4 py-3">
        <span className="flex items-center gap-1.5">
          {isStale && (
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
          )}
          <span className={isStale ? "text-amber-600" : "text-muted-foreground"}>
            {lastCalcAgo}
          </span>
        </span>
      </td>
      <td className="px-4 py-3">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => onFilterIncidents(t.tenant_id)}
        >
          View incidents &rarr;
        </Button>
      </td>
    </tr>
  );
}

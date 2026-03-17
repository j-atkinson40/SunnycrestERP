import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { safetyService } from "@/services/safety-service";
import type {
  ComplianceScore,
  SafetyAlert,
  OverdueInspection,
  SafetyIncident,
} from "@/types/safety";

function scoreColor(score: number): string {
  if (score >= 90) return "text-green-600";
  if (score >= 75) return "text-amber-500";
  return "text-red-600";
}

function scoreBgColor(score: number): string {
  if (score >= 90) return "bg-green-50 ring-green-200";
  if (score >= 75) return "bg-amber-50 ring-amber-200";
  return "bg-red-50 ring-red-200";
}

function progressBarColor(score: number): string {
  if (score >= 90) return "bg-green-500";
  if (score >= 75) return "bg-amber-500";
  return "bg-red-500";
}

function severityBadge(severity: SafetyAlert["severity"]) {
  const map: Record<
    SafetyAlert["severity"],
    { label: string; className: string }
  > = {
    critical: {
      label: "Critical",
      className: "bg-red-100 text-red-800 border-red-300",
    },
    warning: {
      label: "Warning",
      className: "bg-amber-100 text-amber-800 border-amber-300",
    },
    info: {
      label: "Info",
      className: "bg-blue-100 text-blue-800 border-blue-300",
    },
  };
  const s = map[severity];
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

function incidentStatusBadge(status: string) {
  const map: Record<string, { label: string; className: string }> = {
    reported: {
      label: "Reported",
      className: "bg-blue-100 text-blue-800 border-blue-300",
    },
    investigating: {
      label: "Investigating",
      className: "bg-amber-100 text-amber-800 border-amber-300",
    },
    corrective_actions: {
      label: "Corrective Actions",
      className: "bg-orange-100 text-orange-800 border-orange-300",
    },
    closed: {
      label: "Closed",
      className: "bg-green-100 text-green-800 border-green-300",
    },
  };
  const s = map[status] ?? {
    label: status,
    className: "bg-gray-100 text-gray-800 border-gray-300",
  };
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

export default function SafetyDashboardPage() {
  const [compliance, setCompliance] = useState<ComplianceScore | null>(null);
  const [alerts, setAlerts] = useState<SafetyAlert[]>([]);
  const [overdue, setOverdue] = useState<OverdueInspection[]>([]);
  const [incidents, setIncidents] = useState<SafetyIncident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const [complianceData, alertsData, overdueData, incidentsData] =
          await Promise.all([
            safetyService.getComplianceScore(),
            safetyService.listAlerts(true),
            safetyService.getOverdueInspections(),
            safetyService.listIncidents({ limit: 5 }),
          ]);
        setCompliance(complianceData);
        setAlerts(
          [...alertsData].sort(
            (a, b) =>
              (SEVERITY_ORDER[a.severity] ?? 9) -
              (SEVERITY_ORDER[b.severity] ?? 9),
          ),
        );
        setOverdue(overdueData);
        setIncidents(incidentsData.items);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load safety dashboard";
        setError(message);
        toast.error(message);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  async function handleAcknowledge(alertId: string) {
    setAcknowledgingId(alertId);
    try {
      await safetyService.acknowledgeAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      toast.success("Alert acknowledged");
    } catch {
      toast.error("Failed to acknowledge alert");
    } finally {
      setAcknowledgingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading safety dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  const overallScore = compliance?.overall_score ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Safety Dashboard</h1>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <Link to="/safety/inspections/new">
          <Button>Start Inspection</Button>
        </Link>
        <Link to="/safety/incidents/new">
          <Button variant="outline">Report Incident</Button>
        </Link>
        <Link to="/safety/chemicals">
          <Button variant="outline">SDS Lookup</Button>
        </Link>
      </div>

      {/* Top Row: Compliance Score + Active Alerts */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Compliance Score */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Compliance Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center gap-4">
              <div
                className={`flex h-28 w-28 items-center justify-center rounded-full ring-4 ${scoreBgColor(overallScore)}`}
              >
                <span className={`text-4xl font-bold ${scoreColor(overallScore)}`}>
                  {Math.round(overallScore)}
                </span>
              </div>
              {compliance && compliance.categories.length > 0 && (
                <div className="w-full space-y-3 pt-2">
                  {compliance.categories.map((cat) => {
                    const pct =
                      cat.max_score > 0
                        ? Math.round((cat.score / cat.max_score) * 100)
                        : 0;
                    return (
                      <div key={cat.category} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium capitalize">
                            {cat.category.replace(/_/g, " ")}
                          </span>
                          <span className="text-muted-foreground">
                            {cat.items_compliant}/{cat.items_total} ({pct}%)
                          </span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-gray-100">
                          <div
                            className={`h-2 rounded-full transition-all ${progressBarColor(pct)}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {compliance && (
                <p className="text-xs text-muted-foreground">
                  Last calculated {formatDate(compliance.generated_at)}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Active Alerts */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No active alerts. All clear.
              </p>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between gap-3 rounded-lg border p-3"
                  >
                    <div className="flex flex-col gap-1.5 min-w-0">
                      <div className="flex items-center gap-2">
                        {severityBadge(alert.severity)}
                        {alert.due_date && (
                          <span className="text-xs text-muted-foreground">
                            Due {formatDate(alert.due_date)}
                          </span>
                        )}
                      </div>
                      <p className="text-sm leading-snug">{alert.message}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="shrink-0"
                      disabled={acknowledgingId === alert.id}
                      onClick={() => handleAcknowledge(alert.id)}
                    >
                      {acknowledgingId === alert.id ? "..." : "Acknowledge"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row: Overdue Inspections + Recent Incidents */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Overdue Inspections */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Overdue Inspections
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overdue.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No overdue inspections.
              </p>
            ) : (
              <div className="space-y-3">
                {overdue.map((item) => (
                  <div
                    key={item.template_id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {item.template_name}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {item.equipment_type && (
                          <span>{item.equipment_type}</span>
                        )}
                        <span>Every {item.frequency_days} days</span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Last inspected: {formatDate(item.last_inspection_date)}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className="shrink-0 bg-red-100 text-red-800 border-red-300"
                    >
                      {item.days_overdue}d overdue
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Incidents */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recent Incidents
            </CardTitle>
          </CardHeader>
          <CardContent>
            {incidents.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No incidents recorded.
              </p>
            ) : (
              <div className="space-y-3">
                {incidents.map((incident) => (
                  <Link
                    key={incident.id}
                    to={`/safety/incidents/${incident.id}`}
                    className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {incident.incident_type.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {incident.location} &middot;{" "}
                        {formatDate(incident.incident_date)}
                      </p>
                      {incident.involved_employee_name && (
                        <p className="text-xs text-muted-foreground">
                          {incident.involved_employee_name}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {incident.osha_recordable && (
                        <Badge
                          variant="outline"
                          className="bg-red-100 text-red-800 border-red-300"
                        >
                          OSHA
                        </Badge>
                      )}
                      {incidentStatusBadge(incident.status)}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

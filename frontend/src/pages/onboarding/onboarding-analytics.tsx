import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import * as onboardingService from "@/services/onboarding-service";
import type { OnboardingAnalytics } from "@/types/onboarding";

// ── Stat Card ──────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sublabel,
  accent = "primary",
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "primary" | "green" | "amber" | "red";
}) {
  const colorMap = {
    primary: "text-primary",
    green: "text-green-600",
    amber: "text-amber-600",
    red: "text-red-600",
  };
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        <p className={cn("mt-1 text-3xl font-bold", colorMap[accent])}>{value}</p>
        {sublabel && (
          <p className="mt-0.5 text-xs text-muted-foreground">{sublabel}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Progress Circle ────────────────────────────────────────────

function ProgressCircle({
  percent,
  size = 80,
  strokeWidth = 6,
  label,
}: {
  percent: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-muted/30"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn(
            percent >= 75 ? "text-green-500" : percent >= 50 ? "text-amber-500" : "text-red-500"
          )}
        />
      </svg>
      <span className="text-lg font-bold">{percent}%</span>
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  );
}

// ── Horizontal Bar ─────────────────────────────────────────────

function HBar({
  label,
  value,
  max,
  color = "bg-primary",
}: {
  label: string;
  value: number;
  max: number;
  color?: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{value}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted/50">
        <div
          className={cn("h-2 rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────

export default function OnboardingAnalyticsPage() {
  const [analytics, setAnalytics] = useState<OnboardingAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    onboardingService
      .getOnboardingAnalytics()
      .then(setAnalytics)
      .catch(() => {
        toast.error("Failed to load onboarding analytics");
        // Use placeholder data for dev/demo
        setAnalytics({
          avg_time_to_first_order_hours: 4.2,
          must_complete_rate_7d: 68,
          checklist_drop_off: [
            { item_key: "connect_accounting", stuck_count: 12, skipped_count: 8 },
            { item_key: "import_customers", stuck_count: 9, skipped_count: 5 },
            { item_key: "setup_pricing", stuck_count: 7, skipped_count: 3 },
            { item_key: "invite_team", stuck_count: 6, skipped_count: 11 },
            { item_key: "first_production_run", stuck_count: 4, skipped_count: 2 },
          ],
          integration_adoption: {
            quickbooks: 42,
            sage_csv: 28,
            sage_api: 5,
            none: 25,
          },
          scenario_completion: {
            first_order: 72,
            first_invoice: 58,
            first_delivery: 45,
            first_production: 38,
          },
          white_glove_requests: { total: 18, pending: 4, completed: 14 },
          check_in_call_rate: 61,
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!analytics) return null;

  const integrationTotal = Object.values(analytics.integration_adoption).reduce(
    (a, b) => a + b,
    0
  );
  const integrationColors: Record<string, string> = {
    quickbooks: "bg-[#2CA01C]",
    sage_csv: "bg-blue-500",
    sage_api: "bg-purple-500",
    none: "bg-gray-400",
  };
  const integrationLabels: Record<string, string> = {
    quickbooks: "QuickBooks",
    sage_csv: "Sage CSV",
    sage_api: "Sage API",
    none: "No Integration",
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Onboarding Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Platform-wide onboarding metrics and drop-off analysis.
        </p>
      </div>

      {/* Top-level stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Time to First Value"
          value={
            analytics.avg_time_to_first_order_hours != null
              ? `${analytics.avg_time_to_first_order_hours.toFixed(1)}h`
              : "N/A"
          }
          sublabel="Avg hours from signup to first order"
          accent="primary"
        />
        <StatCard
          label="Must-Complete Rate (7d)"
          value={`${analytics.must_complete_rate_7d}%`}
          sublabel="Tenants completing essentials in 7 days"
          accent={analytics.must_complete_rate_7d >= 70 ? "green" : "amber"}
        />
        <StatCard
          label="Check-in Call Rate"
          value={`${analytics.check_in_call_rate}%`}
          sublabel="Accepted the free onboarding call"
          accent={analytics.check_in_call_rate >= 50 ? "green" : "amber"}
        />
        <StatCard
          label="White-Glove Requests"
          value={String(analytics.white_glove_requests.total)}
          sublabel={`${analytics.white_glove_requests.pending} pending / ${analytics.white_glove_requests.completed} completed`}
          accent="primary"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Must-Complete Rate Visual */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Must-Complete Progress</CardTitle>
            <CardDescription>
              Percentage of tenants finishing essential checklist items within 7 days.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center py-4">
            <ProgressCircle
              percent={analytics.must_complete_rate_7d}
              size={120}
              strokeWidth={10}
              label="within 7 days"
            />
          </CardContent>
        </Card>

        {/* Integration Adoption */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Integration Adoption</CardTitle>
            <CardDescription>
              Which accounting integration tenants are using.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(analytics.integration_adoption).map(([key, value]) => (
              <HBar
                key={key}
                label={integrationLabels[key] || key}
                value={value}
                max={integrationTotal}
                color={integrationColors[key] || "bg-primary"}
              />
            ))}
          </CardContent>
        </Card>

        {/* Drop-off Analysis */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Drop-off Analysis</CardTitle>
            <CardDescription>
              Checklist items where tenants get stuck or skip most often.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border">
              <div className="grid grid-cols-[1fr_80px_80px] gap-2 border-b bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
                <span>Item</span>
                <span className="text-center">Stuck</span>
                <span className="text-center">Skipped</span>
              </div>
              {analytics.checklist_drop_off.map((row) => (
                <div
                  key={row.item_key}
                  className="grid grid-cols-[1fr_80px_80px] gap-2 border-b last:border-b-0 px-4 py-2.5"
                >
                  <span className="text-sm font-medium">
                    {row.item_key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                  <span className="text-center">
                    <Badge variant="outline" className="text-red-600 border-red-200 bg-red-50">
                      {row.stuck_count}
                    </Badge>
                  </span>
                  <span className="text-center">
                    <Badge variant="outline" className="text-amber-600 border-amber-200 bg-amber-50">
                      {row.skipped_count}
                    </Badge>
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Scenario Completion */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Scenario Completion Rates</CardTitle>
            <CardDescription>
              How many tenants complete each guided walkthrough.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(analytics.scenario_completion).map(([key, pct]) => {
              const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
              return (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">{label}</span>
                    <span className="text-muted-foreground">{pct}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted/50">
                    <div
                      className={cn(
                        "h-2 rounded-full transition-all",
                        pct >= 70 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-400"
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

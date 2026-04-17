import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Briefcase,
  Calendar,
  Package,
  DollarSign,
  AlertCircle,
  Clock,
  ChevronRight,
  ShieldCheck,
  Activity,
  ArrowRight,
  Rocket,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { funeralHomeService } from "@/services/funeral-home-service";
import * as onboardingService from "@/services/onboarding-service";
import apiClient from "@/lib/api-client";
import type { FHCase, FHDashboardData } from "@/types/funeral-home";

// ── Helpers ──

const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "");
function daysBetween(from: string, to: Date = new Date()): number {
  return Math.floor((to.getTime() - new Date(from).getTime()) / 86400000);
}

// ── Stat Card ──

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  suffix,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  suffix?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={cn("rounded-lg p-3", color)}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold">
            {value}
            {suffix && (
              <span className="ml-1 text-sm font-normal text-muted-foreground">
                {suffix}
              </span>
            )}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Compliance Score Ring ──

function ComplianceRing({ score }: { score: number }) {
  const color = score >= 90 ? "text-green-600" : score >= 70 ? "text-amber-500" : "text-red-500";
  const bgColor = score >= 90 ? "stroke-green-100" : score >= 70 ? "stroke-amber-100" : "stroke-red-100";
  const fgColor = score >= 90 ? "stroke-green-600" : score >= 70 ? "stroke-amber-500" : "stroke-red-500";
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-24 w-24">
        <svg className="h-24 w-24 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" strokeWidth="8" className={bgColor} />
          <circle
            cx="40"
            cy="40"
            r="36"
            fill="none"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={fgColor}
          />
        </svg>
        <span className={cn("absolute inset-0 flex items-center justify-center text-xl font-bold", color)}>
          {score}%
        </span>
      </div>
    </div>
  );
}

// ── Attention Group ──

interface AttentionGroup {
  key: string;
  label: string;
  cases: FHCase[];
  color: string;
  actionLabel?: string;
}

function buildAttentionGroups(data: FHDashboardData): AttentionGroup[] {
  const groups: AttentionGroup[] = [];
  const na = data.needs_attention;

  if (na.needs_arrangement.length > 0) {
    groups.push({
      key: "arrangement",
      label: "Needs Arrangement Conference",
      cases: na.needs_arrangement,
      color: "text-red-600 bg-red-50",
    });
  }
  if (na.vault_not_ordered.length > 0) {
    groups.push({
      key: "vault_order",
      label: "Vault Not Ordered",
      cases: na.vault_not_ordered,
      color: "text-orange-600 bg-orange-50",
    });
  }
  if (na.vault_at_risk.length > 0) {
    groups.push({
      key: "vault_risk",
      label: "Vault Delivery at Risk",
      cases: na.vault_at_risk,
      color: "text-amber-600 bg-amber-50",
    });
  }
  if (na.awaiting_cremation_auth.length > 0) {
    groups.push({
      key: "cremation_auth",
      label: "Awaiting Cremation Authorization",
      cases: na.awaiting_cremation_auth,
      color: "text-purple-600 bg-purple-50",
    });
  }
  if (na.invoice_not_sent.length > 0) {
    groups.push({
      key: "invoice",
      label: "Invoice Not Sent",
      cases: na.invoice_not_sent,
      color: "text-blue-600 bg-blue-50",
    });
  }
  if (na.outstanding_balance.length > 0) {
    groups.push({
      key: "balance",
      label: "Outstanding Balance",
      cases: na.outstanding_balance,
      color: "text-indigo-600 bg-indigo-50",
    });
  }

  return groups;
}

// ── Upcoming Services ──

interface ServiceDay {
  date: string;
  cases: FHCase[];
}

function groupByDate(cases: FHCase[]): ServiceDay[] {
  const map = new Map<string, FHCase[]>();
  for (const c of cases) {
    const d = c.service_date ?? "Unknown";
    if (!map.has(d)) map.set(d, []);
    map.get(d)!.push(c);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, cases]) => ({ date, cases }));
}

// ── Main Dashboard Component ──

export function FuneralHomeDashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<FHDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboardingPercent, setOnboardingPercent] = useState<number | null>(null);
  const [onboardingCompleted, setOnboardingCompleted] = useState(0);
  const [onboardingTotal, setOnboardingTotal] = useState(0);

  // Prefer new /onboarding-flow/status (accounts for visible_steps
  // including the skip-import-when-orders-exist rule). Fall back to
  // legacy tenant_onboarding_checklists when the new endpoint is empty.
  useEffect(() => {
    apiClient
      .get<{
        visible_steps?: string[];
        completed_steps?: string[];
        percent_complete?: number;
      }>("/onboarding-flow/status")
      .then(({ data }) => {
        const visible = (data.visible_steps || []).filter((s) => s !== "complete");
        const completed = (data.completed_steps || []).filter((s) => visible.includes(s));
        if (visible.length > 0) {
          setOnboardingPercent(data.percent_complete ?? 0);
          setOnboardingCompleted(completed.length);
          setOnboardingTotal(visible.length);
          return;
        }
        throw new Error("no_visible_steps");
      })
      .catch(() => {
        onboardingService
          .getChecklist()
          .then((checklist) => {
            const mustItems = checklist.items.filter((i) => i.tier === "must_complete");
            const done = mustItems.filter((i) => i.status === "completed").length;
            setOnboardingPercent(checklist.must_complete_percent);
            setOnboardingCompleted(done);
            setOnboardingTotal(mustItems.length);
          })
          .catch(() => {
            setOnboardingPercent(0);
            setOnboardingTotal(5);
          });
      });
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const d = await funeralHomeService.getDashboard();
      setData(d);
    } catch {
      toast.error("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Unable to load dashboard data.</p>
      </div>
    );
  }

  // Compute stats
  const allCases = Object.values(data.cases_by_status).flat();
  const activeCases = allCases.filter(
    (c) => c.status !== "closed" && c.status !== "cancelled",
  );
  const todayStr = new Date().toISOString().split("T")[0];
  const servicesToday = allCases.filter((c) => c.service_date === todayStr);
  const deliveriesToday = data.today_schedule.deliveries.length;
  const outstandingTotal = (data.needs_attention.outstanding_balance ?? []).reduce(
    (sum, c) => sum + (c.invoice?.balance_due ?? 0),
    0,
  );

  const attentionGroups = buildAttentionGroups(data);

  // Upcoming services for next 7 days
  const in7Days = new Date();
  in7Days.setDate(in7Days.getDate() + 7);
  const upcomingCases = allCases.filter((c) => {
    if (!c.service_date) return false;
    const sd = new Date(c.service_date);
    return sd >= new Date(todayStr) && sd <= in7Days;
  });
  const upcomingDays = groupByDate(upcomingCases);

  return (
    <div className="space-y-6">
      {/* Onboarding Banner */}
      {onboardingPercent !== null && onboardingPercent < 100 && (
        <Link
          to="/onboarding"
          className="block rounded-xl border-2 border-stone-200 bg-gradient-to-r from-stone-50 to-stone-100 p-5 transition-all hover:border-stone-300 hover:shadow-md"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-stone-200">
                <Rocket className="h-6 w-6 text-stone-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">
                  {onboardingCompleted === 0
                    ? "Let's get you set up"
                    : `${onboardingCompleted} of ${onboardingTotal} setup steps complete`}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {onboardingCompleted === 0
                    ? "Complete your setup to start managing cases — takes about 15 minutes"
                    : "Continue where you left off"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {onboardingTotal > 0 && (
                <div className="hidden sm:flex items-center gap-2">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-stone-200">
                    <div
                      className="h-full rounded-full bg-stone-500 transition-all"
                      style={{ width: `${onboardingPercent}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-muted-foreground">
                    {onboardingPercent}%
                  </span>
                </div>
              )}
              <div className="flex items-center gap-1 text-sm font-medium text-stone-600">
                Continue setup
                <ArrowRight className="h-4 w-4" />
              </div>
            </div>
          </div>
        </Link>
      )}

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {user?.first_name}
        </p>
      </div>

      {/* Top Row — Stat Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Active Cases"
          value={activeCases.length}
          icon={Briefcase}
          color="bg-stone-100 text-stone-600"
        />
        <StatCard
          label="Services Today"
          value={servicesToday.length}
          icon={Calendar}
          color="bg-blue-100 text-blue-600"
        />
        <StatCard
          label="Vault Deliveries Today"
          value={deliveriesToday}
          icon={Package}
          color="bg-purple-100 text-purple-600"
        />
        <StatCard
          label="Outstanding Invoices"
          value={outstandingTotal > 0 ? currency(outstandingTotal) : "$0"}
          icon={DollarSign}
          color="bg-green-100 text-green-600"
        />
      </div>

      {/* Main Content — Two Columns */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Cases Needing Attention — 2/3 width */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              Cases Needing Attention
            </CardTitle>
          </CardHeader>
          <CardContent>
            {attentionGroups.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                All cases are on track. Nice work!
              </p>
            ) : (
              <div className="space-y-4">
                {attentionGroups.map((group) => (
                  <div key={group.key}>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                          group.color,
                        )}
                      >
                        {group.label}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({group.cases.length})
                      </span>
                    </div>
                    <div className="space-y-1">
                      {group.cases.slice(0, 5).map((c) => (
                        <Link
                          key={c.id}
                          to={`/cases/${c.id}`}
                          className="flex items-center justify-between rounded-lg border px-4 py-2.5 hover:bg-muted/50 transition-colors"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {c.deceased_first_name} {c.deceased_last_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {c.case_number} &middot; {c.days_since_opened ?? daysBetween(c.created_at)} days open
                            </p>
                          </div>
                          <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        </Link>
                      ))}
                      {group.cases.length > 5 && (
                        <p className="text-xs text-muted-foreground text-center py-1">
                          + {group.cases.length - 5} more
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Upcoming Services — 1/3 width */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Calendar className="h-4 w-4 text-blue-500" />
              Upcoming Services
            </CardTitle>
          </CardHeader>
          <CardContent>
            {upcomingDays.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No services scheduled in the next 7 days.
              </p>
            ) : (
              <div className="space-y-4">
                {upcomingDays.map((day) => (
                  <div key={day.date}>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                      {day.date === todayStr ? "Today" : fmtDate(day.date)}
                    </p>
                    <div className="space-y-1.5">
                      {day.cases.map((c) => (
                        <Link
                          key={c.id}
                          to={`/cases/${c.id}`}
                          className="block rounded-lg border px-3 py-2 hover:bg-muted/50 transition-colors"
                        >
                          <p className="text-sm font-medium truncate">
                            {c.deceased_first_name} {c.deceased_last_name}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            {c.service_type && (
                              <span className="text-xs text-muted-foreground capitalize">
                                {c.service_type.replace(/_/g, " ")}
                              </span>
                            )}
                            {c.service_time && (
                              <span className="text-xs text-muted-foreground">
                                {c.service_time}
                              </span>
                            )}
                          </div>
                          {c.service_location && (
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                              {c.service_location}
                            </p>
                          )}
                          {c.vault_order && (
                            <div className="mt-1">
                              <Badge
                                variant="outline"
                                className={cn(
                                  "text-[10px]",
                                  c.vault_order.status === "delivered"
                                    ? "border-green-300 text-green-700"
                                    : "border-amber-300 text-amber-700",
                                )}
                              >
                                Vault: {c.vault_order.status.replace(/_/g, " ")}
                              </Badge>
                            </div>
                          )}
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* FTC Compliance Score */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4 text-green-600" />
              FTC Compliance Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-8">
              <ComplianceRing score={data.compliance_score} />
              <div className="flex-1 space-y-2">
                <p className="text-sm text-muted-foreground">
                  {data.compliance_score >= 90
                    ? "Excellent compliance standing."
                    : data.compliance_score >= 70
                      ? "Some items need attention."
                      : "Immediate action required."}
                </p>
                <div className="flex gap-2">
                  <Link
                    to="/compliance"
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    View Full Report
                  </Link>
                  <span className="text-xs text-muted-foreground">&middot;</span>
                  <Link
                    to="/compliance?action=generate"
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Generate Inspection Package
                  </Link>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-stone-500" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_activity.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No recent activity.
              </p>
            ) : (
              <div className="space-y-2">
                {data.recent_activity.slice(0, 10).map((a) => (
                  <div
                    key={a.id}
                    className="flex items-start gap-3 rounded-lg px-2 py-1.5"
                  >
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted flex-shrink-0 mt-0.5">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm truncate">{a.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(a.created_at).toLocaleString()}
                        {a.performed_by && ` by ${a.performed_by}`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Truck,
  Factory,
  FileText,
  ShieldCheck,
  Plus,
  ClipboardList,
  AlertTriangle,
  Clock,
  ChevronRight,
  ArrowRight,
  Rocket,
  Megaphone,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SpringBurialWidget } from "@/components/dashboard/spring-burial-widget";
import { MorningBriefingCard } from "@/components/morning-briefing-card";
import { MorningBriefingMobile } from "@/components/morning-briefing-mobile";
import { useDevice } from "@/contexts/device-context";
import * as onboardingService from "@/services/onboarding-service";
import apiClient from "@/lib/api-client";

// ── Types ──

interface DashboardStats {
  deliveriesToday: number;
  unitsToday: number;
  openInvoices: number;
  npcaScore: number;
}

interface ProductionEntry {
  id: string;
  product_name: string;
  quantity: number;
  unit: string;
  created_at: string;
  created_by_name?: string;
}

interface ActiveOrder {
  id: string;
  order_number: string;
  customer_name: string;
  status: string;
  delivery_date?: string;
  total: number;
  item_count: number;
}

interface UpcomingDelivery {
  id: string;
  order_number: string;
  customer_name: string;
  delivery_date: string;
  driver?: string;
  status: string;
}

interface ComplianceAlert {
  id: string;
  type: "npca" | "osha" | "other";
  severity: "critical" | "warning" | "info";
  message: string;
  created_at: string;
}

interface Announcement {
  id: string;
  title: string;
  body: string;
  urgency: string;
  created_at: string;
  created_by_name?: string;
}

// ── Helpers ──

const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const fmtDate = (d: string) => new Date(d).toLocaleDateString();
const fmtTime = (d: string) =>
  new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

// Phase II Batch 1a — status map now routes through StatusPill (Session 3)
// via its STATUS_MAP. Kept as a compatibility shim so existing callers using
// .tsx expressions like ORDER_STATUS_COLORS[order.status] still resolve.
// Prefer <StatusPill status={order.status}> directly for new work.
const ORDER_STATUS_COLORS: Record<string, string> = {
  pending: "bg-status-warning-muted text-status-warning",
  in_progress: "bg-status-info-muted text-status-info",
  ready: "bg-status-success-muted text-status-success",
  shipped: "bg-brass-subtle text-brass",
  delivered: "bg-surface-sunken text-content-muted",
};

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

// ── Compliance Ring ──

function ComplianceRing({
  score,
  label,
}: {
  score: number;
  label: string;
}) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 90
      ? "text-status-success"
      : score >= 70
        ? "text-status-warning"
        : "text-status-error";

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative h-20 w-20">
        <svg className="h-20 w-20 -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="7"
            className="text-muted"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="7"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={color}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("text-base font-bold", color)}>{score}%</span>
        </div>
      </div>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

// ── Main Dashboard ──

export function ManufacturingDashboard() {
  const { user, hasModule } = useAuth();
  const { effectiveDevice } = useDevice();
  const isMobile = effectiveDevice === "mobile" || effectiveDevice === "tablet";
  const isNpcaEnabled = hasModule("npca_audit_prep");

  const [stats, setStats] = useState<DashboardStats>({
    deliveriesToday: 0,
    unitsToday: 0,
    openInvoices: 0,
    npcaScore: 0,
  });
  const [productionEntries, setProductionEntries] = useState<ProductionEntry[]>([]);
  const [activeOrders, setActiveOrders] = useState<ActiveOrder[]>([]);
  const [upcomingDeliveries, setUpcomingDeliveries] = useState<UpcomingDelivery[]>([]);
  const [complianceAlerts, setComplianceAlerts] = useState<ComplianceAlert[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [dismissedAnnouncements, setDismissedAnnouncements] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem("dismissed-announcements");
      if (raw) return new Set(JSON.parse(raw));
    } catch { /* ignore */ }
    return new Set();
  });
  const [loading, setLoading] = useState(true);
  const [onboardingPercent, setOnboardingPercent] = useState<number | null>(null);
  const [onboardingCompleted, setOnboardingCompleted] = useState(0);
  const [onboardingTotal, setOnboardingTotal] = useState(0);

  // Fetch onboarding status — prefer the new /onboarding-flow/status
  // endpoint (returns visible_steps, which auto-excludes the import step
  // when orders already exist). Falls back to the legacy checklist system.
  useEffect(() => {
    apiClient
      .get<{
        visible_steps?: string[];
        completed_steps?: string[];
        percent_complete?: number;
      }>("/onboarding-flow/status")
      .then(({ data }) => {
        // Exclude the "complete" terminal step from the user-facing count
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
        // Legacy fallback
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

  const fetchDashboard = useCallback(async () => {
    try {
      const results = await Promise.allSettled([
        apiClient.get("/production/production-log/today").then((r) => r.data),
        apiClient.get("/sales-orders", { params: { status: "active", limit: 10 } }).then((r) => r.data),
        apiClient.get("/deliveries/upcoming", { params: { days: 7 } }).then((r) => r.data),
        apiClient.get("/compliance/alerts").then((r) => r.data),
        apiClient.get("/dashboard/manufacturing/stats").then((r) => r.data),
        apiClient.get("/announcements", { params: { limit: 5, active: true } }).then((r) => r.data),
      ]);

      // Production log
      if (results[0].status === "fulfilled") {
        const prodData = results[0].value;
        const entries = Array.isArray(prodData) ? prodData : prodData.entries ?? [];
        setProductionEntries(entries);
        const totalUnits = entries.reduce(
          (sum: number, e: ProductionEntry) => sum + (e.quantity || 0),
          0,
        );
        setStats((prev) => ({ ...prev, unitsToday: totalUnits }));
      }

      // Active orders
      if (results[1].status === "fulfilled") {
        const orderData = results[1].value;
        setActiveOrders(Array.isArray(orderData) ? orderData : orderData.items ?? []);
      }

      // Upcoming deliveries
      if (results[2].status === "fulfilled") {
        const delData = results[2].value;
        const deliveries = Array.isArray(delData) ? delData : delData.items ?? [];
        setUpcomingDeliveries(deliveries);
        const todayStr = new Date().toISOString().slice(0, 10);
        const todayCount = deliveries.filter(
          (d: UpcomingDelivery) => d.delivery_date?.slice(0, 10) === todayStr,
        ).length;
        setStats((prev) => ({ ...prev, deliveriesToday: todayCount }));
      }

      // Compliance alerts
      if (results[3].status === "fulfilled") {
        const alertData = results[3].value;
        setComplianceAlerts(
          Array.isArray(alertData) ? alertData : alertData.alerts ?? [],
        );
      }

      // Announcements
      if (results[5].status === "fulfilled") {
        const annData = results[5].value;
        const items = Array.isArray(annData) ? annData : annData.items ?? [];
        setAnnouncements(items);
      }

      // Stats
      if (results[4].status === "fulfilled") {
        const s = results[4].value;
        setStats((prev) => ({
          ...prev,
          openInvoices: s.open_invoices ?? prev.openInvoices,
          npcaScore: s.npca_score ?? prev.npcaScore,
          deliveriesToday: s.deliveries_today ?? prev.deliveriesToday,
          unitsToday: s.units_today ?? prev.unitsToday,
        }));
      }
    } catch {
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60_000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brass" />
      </div>
    );
  }

  const showProduction = hasModule("daily_production_log");

  return (
    <div className="space-y-6 p-6">
      {/* Morning Briefing */}
      {isMobile ? <MorningBriefingMobile /> : <MorningBriefingCard />}

      {/* Onboarding Banner — prominent, shows until setup is complete */}
      {onboardingPercent !== null && onboardingPercent < 100 && (
        <Link
          to="/onboarding"
          className="block rounded-xl border-2 border-primary/20 bg-gradient-to-r from-primary/5 to-primary/10 p-5 transition-all hover:border-primary/40 hover:shadow-md"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Rocket className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">
                  {onboardingCompleted === 0
                    ? "Let's get you set up"
                    : `${onboardingCompleted} of ${onboardingTotal} setup steps complete`}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {onboardingCompleted === 0
                    ? "Complete your setup to start using the platform — takes about 15 minutes"
                    : "Continue where you left off — your team will be ready in no time"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {onboardingTotal > 0 && (
                <div className="hidden sm:flex items-center gap-2">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-primary/10">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${onboardingPercent}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-muted-foreground">
                    {onboardingPercent}%
                  </span>
                </div>
              )}
              <div className="flex items-center gap-1 text-sm font-medium text-primary">
                Continue setup
                <ArrowRight className="h-4 w-4" />
              </div>
            </div>
          </div>
        </Link>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back, {user?.first_name}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/sales-orders/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Order
          </Link>
        </div>
      </div>

      {/* Snapshot Stats — Phase II Batch 1a: pastel icon backgrounds
          migrated from bg-{purple,green,blue,amber,red}-50 to brass-subtle
          + warm status-muted variants. Icons on the stat cards now read
          as "warm aged-brass detail" per DL §2 meta-anchor, not pastel
          highlight chrome. NPCA-score traffic-light threshold uses the
          DL status-family palette, auto-mode-switching. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Deliveries Today"
          value={stats.deliveriesToday}
          icon={Truck}
          color="bg-brass-subtle text-brass"
        />
        {showProduction && (
          <StatCard
            label="Units Produced Today"
            value={stats.unitsToday}
            icon={Factory}
            color="bg-status-success-muted text-status-success"
          />
        )}
        <StatCard
          label="Open Invoices"
          value={currency(stats.openInvoices)}
          icon={FileText}
          color="bg-status-info-muted text-status-info"
        />
        {isNpcaEnabled && (
          <StatCard
            label="NPCA Score"
            value={`${stats.npcaScore}%`}
            icon={ShieldCheck}
            color={cn(
              stats.npcaScore >= 90
                ? "bg-status-success-muted text-status-success"
                : stats.npcaScore >= 70
                  ? "bg-status-warning-muted text-status-warning"
                  : "bg-status-error-muted text-status-error",
            )}
          />
        )}
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 xl:grid-cols-[1fr_400px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Active Orders */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5 text-muted-foreground" />
                Active Orders
              </CardTitle>
              <Link
                to="/sales-orders"
                className="text-body-sm text-brass hover:text-brass-hover hover:underline flex items-center gap-1 focus-ring-brass rounded-sm"
              >
                View all <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </CardHeader>
            <CardContent>
              {activeOrders.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">
                  No active orders right now.
                </p>
              ) : (
                <div className="space-y-2">
                  {activeOrders.map((order) => (
                    <Link
                      key={order.id}
                      to={`/sales-orders/${order.id}`}
                      className="flex items-center justify-between rounded-lg border px-4 py-3 hover:bg-muted/50 transition-colors"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-muted-foreground">
                            {order.order_number}
                          </span>
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-medium",
                              ORDER_STATUS_COLORS[order.status] ??
                                "bg-surface-sunken text-content-muted",
                            )}
                          >
                            {order.status.replace(/_/g, " ")}
                          </span>
                        </div>
                        <p className="text-sm font-medium">{order.customer_name}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold">{currency(order.total)}</p>
                        {order.delivery_date && (
                          <p className="text-xs text-muted-foreground">
                            {fmtDate(order.delivery_date)}
                          </p>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upcoming Deliveries */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Truck className="h-5 w-5 text-muted-foreground" />
                Upcoming Deliveries
                <span className="text-sm font-normal text-muted-foreground">
                  (next 7 days)
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {upcomingDeliveries.length === 0 ? (
                <p className="py-8 text-center text-muted-foreground">
                  No deliveries scheduled.
                </p>
              ) : (
                <div className="space-y-2">
                  {upcomingDeliveries.map((del) => (
                    <div
                      key={del.id}
                      className="flex items-center justify-between rounded-lg border px-4 py-3"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-muted-foreground">
                            {del.order_number}
                          </span>
                          <span className="text-sm font-medium">
                            {del.customer_name}
                          </span>
                        </div>
                        {del.driver && (
                          <p className="text-xs text-muted-foreground">
                            Driver: {del.driver}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="text-sm">{fmtDate(del.delivery_date)}</p>
                        <span
                          className={cn(
                            "text-xs font-medium",
                            del.status === "confirmed"
                              ? "text-status-success"
                              : "text-status-warning",
                          )}
                        >
                          {del.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Production Today */}
          {showProduction && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Factory className="h-5 w-5 text-muted-foreground" />
                  Production Today
                </CardTitle>
                <Link
                  to="/production-log"
                  className="text-body-sm text-brass hover:text-brass-hover hover:underline flex items-center gap-1 focus-ring-brass rounded-sm"
                >
                  Log Entry <Plus className="h-3.5 w-3.5" />
                </Link>
              </CardHeader>
              <CardContent>
                <div className="mb-3 flex items-center gap-2 rounded-md bg-status-success-muted px-3 py-2">
                  <Factory className="h-4 w-4 text-status-success" />
                  <span className="text-body-sm font-medium text-status-success">
                    {stats.unitsToday} units today
                  </span>
                </div>
                {productionEntries.length === 0 ? (
                  <p className="py-4 text-center text-muted-foreground text-sm">
                    No production logged yet today.
                  </p>
                ) : (
                  <div
                    className="space-y-2 overflow-y-auto"
                    style={{ maxHeight: 280 }}
                  >
                    {productionEntries.map((entry) => (
                      <div
                        key={entry.id}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <div>
                          <p className="font-medium">{entry.product_name}</p>
                          {entry.created_by_name && (
                            <p className="text-xs text-muted-foreground">
                              {entry.created_by_name}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className="font-semibold">
                            {entry.quantity} {entry.unit}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {fmtTime(entry.created_at)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Announcements Widget */}
          {(() => {
            const visible = announcements.filter((a) => !dismissedAnnouncements.has(a.id)).slice(0, 3);
            if (visible.length === 0) return null;
            return (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Megaphone className="h-5 w-5 text-muted-foreground" />
                    Announcements
                  </CardTitle>
                  <Link
                    to="/announcements"
                    className="text-body-sm text-brass hover:text-brass-hover hover:underline flex items-center gap-1 focus-ring-brass rounded-sm"
                  >
                    View All <ChevronRight className="h-3.5 w-3.5" />
                  </Link>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {visible.map((ann) => (
                      <div
                        key={ann.id}
                        className={cn(
                          "flex items-start gap-2 rounded-md border px-3 py-2.5",
                          ann.urgency === "urgent"
                            ? "border-status-warning/30 bg-status-warning-muted/50"
                            : ann.urgency === "safety"
                              ? "border-status-error/30 bg-status-error-muted/50"
                              : "border-border-subtle",
                        )}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">{ann.title}</p>
                          {ann.body && (
                            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                              {ann.body}
                            </p>
                          )}
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {fmtDate(ann.created_at)}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            const next = new Set(dismissedAnnouncements);
                            next.add(ann.id);
                            setDismissedAnnouncements(next);
                            localStorage.setItem("dismissed-announcements", JSON.stringify([...next]));
                          }}
                          className="shrink-0 rounded p-0.5 text-muted-foreground/50 hover:text-muted-foreground"
                          title="Dismiss"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* Spring Burial Widget */}
          <SpringBurialWidget />

          {/* Compliance Widget */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-muted-foreground" />
                Compliance
              </CardTitle>
              <Link
                to="/compliance"
                className="text-body-sm text-brass hover:text-brass-hover hover:underline flex items-center gap-1 focus-ring-brass rounded-sm"
              >
                Full Report <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </CardHeader>
            <CardContent>
              {isNpcaEnabled && (
                <div className="flex items-center justify-around mb-4">
                  <ComplianceRing score={stats.npcaScore} label="NPCA" />
                </div>
              )}

              {/* Compliance alerts */}
              {complianceAlerts.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Alerts
                  </h4>
                  {complianceAlerts.slice(0, 5).map((alert) => (
                    <div
                      key={alert.id}
                      className={cn(
                        "flex items-start gap-2 rounded-md px-3 py-2 text-body-sm",
                        alert.severity === "critical"
                          ? "bg-status-error-muted text-status-error"
                          : alert.severity === "warning"
                            ? "bg-status-warning-muted text-status-warning"
                            : "bg-status-info-muted text-status-info",
                      )}
                    >
                      {alert.severity === "critical" ? (
                        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      ) : (
                        <Clock className="h-4 w-4 shrink-0 mt-0.5" />
                      )}
                      <span>{alert.message}</span>
                    </div>
                  ))}
                </div>
              )}

              {complianceAlerts.length === 0 && (
                <p className="text-center text-sm text-muted-foreground py-2">
                  No active alerts.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

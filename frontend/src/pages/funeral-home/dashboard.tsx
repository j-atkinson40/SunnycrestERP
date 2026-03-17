import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FHDashboardData, FHCase, FHCaseActivity, FHVaultOrder } from "@/types/funeral-home";
import { CASE_STATUS_COLORS, CASE_STATUS_LABELS } from "@/types/funeral-home";

const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "");
const fmtTime = (d?: string) => (d ? new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

function AttentionSection({
  title,
  cases,
  color,
  detail,
}: {
  title: string;
  cases: FHCase[];
  color: string;
  detail?: (c: FHCase) => string;
}) {
  if (cases.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className={cn("h-2.5 w-2.5 rounded-full", color)} />
        <h4 className="text-sm font-medium">{title}</h4>
        <Badge variant="secondary">{cases.length}</Badge>
      </div>
      <div className="space-y-1.5 ml-5">
        {cases.map((c) => (
          <Link
            key={c.id}
            to={`/cases/${c.id}`}
            className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
          >
            <div>
              <span className="font-mono text-xs mr-2">{c.case_number}</span>
              <span className="font-medium">
                {c.deceased_last_name}, {c.deceased_first_name}
              </span>
            </div>
            {detail && <span className="text-xs text-muted-foreground">{detail(c)}</span>}
          </Link>
        ))}
      </div>
    </div>
  );
}

function ComplianceWidget({ score }: { score: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 90 ? "text-green-500" : score >= 70 ? "text-amber-500" : "text-red-500";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-24 w-24">
        <svg className="h-24 w-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="currentColor" strokeWidth="8" className="text-muted" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={color}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("text-lg font-bold", color)}>{score}%</span>
        </div>
      </div>
      <span className="text-xs text-muted-foreground">FTC Compliance</span>
    </div>
  );
}

function ScheduleItem({ label, c }: { label: string; c: FHCase }) {
  return (
    <Link
      to={`/cases/${c.id}`}
      className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
    >
      <div>
        <span className="font-medium">
          {c.deceased_last_name}, {c.deceased_first_name}
        </span>
        <span className="ml-2 text-muted-foreground">{c.case_number}</span>
      </div>
      <div className="text-xs text-muted-foreground">
        <span>{label}</span>
        {c.service_time && <span className="ml-1">{c.service_time}</span>}
        {c.service_location && <span className="ml-1">at {c.service_location}</span>}
      </div>
    </Link>
  );
}

function DeliveryItem({ vo }: { vo: FHVaultOrder }) {
  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
      <div>
        <span className="font-medium">{vo.vault_product_name ?? "Vault"}</span>
        {vo.order_number && <span className="ml-2 text-muted-foreground">#{vo.order_number}</span>}
      </div>
      <Badge variant="outline">{vo.status}</Badge>
    </div>
  );
}

function ActivityItem({ a }: { a: FHCaseActivity }) {
  return (
    <div className="flex gap-3 text-sm">
      <div className="flex flex-col items-center">
        <div className="h-2 w-2 rounded-full bg-muted-foreground mt-1.5" />
        <div className="flex-1 w-px bg-muted" />
      </div>
      <div className="pb-3">
        <p className="text-muted-foreground">{a.description}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {fmtTime(a.created_at)} {a.performed_by ? `by ${a.performed_by}` : ""}
        </p>
      </div>
    </div>
  );
}

export default function FuneralHomeDashboard() {
  const [data, setData] = useState<FHDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

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
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading dashboard...</p>
      </div>
    );
  }

  const na = data.needs_attention;
  const totalAttention =
    na.needs_arrangement.length +
    na.vault_not_ordered.length +
    na.vault_at_risk.length +
    na.obituary_pending.length +
    na.invoice_not_sent.length +
    na.outstanding_balance.length;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Funeral Home Dashboard</h1>
        <Link
          to="/cases/new"
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          New First Call
        </Link>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Needs Attention */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Needs Attention
                {totalAttention > 0 && <Badge variant="destructive">{totalAttention}</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {totalAttention === 0 && (
                <p className="text-center text-muted-foreground py-4">
                  All clear! No items need attention.
                </p>
              )}
              <AttentionSection
                title="Needs Arrangement Conference"
                cases={na.needs_arrangement}
                color="bg-blue-500"
                detail={(c) => `${c.days_since_opened ?? 0}d since first call`}
              />
              <AttentionSection
                title="Vault Not Ordered"
                cases={na.vault_not_ordered}
                color="bg-amber-500"
                detail={(c) => (c.service_date ? `Service: ${fmtDate(c.service_date)}` : "")}
              />
              <AttentionSection
                title="Vault Delivery at Risk"
                cases={na.vault_at_risk}
                color="bg-red-500"
                detail={(c) => (c.service_date ? `Service: ${fmtDate(c.service_date)}` : "")}
              />
              <AttentionSection
                title="Obituary Pending Approval"
                cases={na.obituary_pending}
                color="bg-purple-500"
              />
              <AttentionSection
                title="Invoice Not Sent"
                cases={na.invoice_not_sent}
                color="bg-orange-500"
              />
              <AttentionSection
                title="Outstanding Balance"
                cases={na.outstanding_balance}
                color="bg-red-400"
                detail={(c) =>
                  c.invoice ? currency(c.invoice.balance_due) : ""
                }
              />
            </CardContent>
          </Card>

          {/* Today's Schedule */}
          <Card>
            <CardHeader>
              <CardTitle>Today's Schedule</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data.today_schedule.services.length === 0 &&
               data.today_schedule.visitations.length === 0 &&
               data.today_schedule.deliveries.length === 0 && (
                <p className="text-center text-muted-foreground py-4">Nothing scheduled for today.</p>
              )}

              {data.today_schedule.services.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Services</h4>
                  {data.today_schedule.services.map((c) => (
                    <ScheduleItem key={c.id} label="Service" c={c} />
                  ))}
                </div>
              )}

              {data.today_schedule.visitations.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Visitations</h4>
                  {data.today_schedule.visitations.map((c) => (
                    <ScheduleItem key={c.id} label="Visitation" c={c} />
                  ))}
                </div>
              )}

              {data.today_schedule.deliveries.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Vault Deliveries</h4>
                  {data.today_schedule.deliveries.map((vo) => (
                    <DeliveryItem key={vo.id} vo={vo} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Active Cases by Status */}
          <Card>
            <CardHeader>
              <CardTitle>Active Cases by Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3">
                {Object.entries(data.cases_by_status).map(([status, cases]) => (
                  <div
                    key={status}
                    className={cn(
                      "rounded-lg px-4 py-3 text-center min-w-[100px]",
                      CASE_STATUS_COLORS[status as keyof typeof CASE_STATUS_COLORS] ?? "bg-gray-100",
                    )}
                  >
                    <div className="text-2xl font-bold">{cases.length}</div>
                    <div className="text-xs font-medium">
                      {CASE_STATUS_LABELS[status as keyof typeof CASE_STATUS_LABELS] ?? status}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Compliance */}
          <Card>
            <CardHeader>
              <CardTitle>FTC Compliance</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-3">
              <ComplianceWidget score={data.compliance_score} />
              <Link
                to="/funeral-home/compliance"
                className="text-sm text-blue-600 hover:underline"
              >
                View Full Report
              </Link>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent
              className="space-y-0"
              style={{ maxHeight: "400px", overflowY: "auto" }}
            >
              {data.recent_activity.length === 0 && (
                <p className="text-center text-muted-foreground py-4">No recent activity.</p>
              )}
              {data.recent_activity.map((a) => (
                <ActivityItem key={a.id} a={a} />
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

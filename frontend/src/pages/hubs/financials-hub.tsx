import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  DollarSign, FileText, Receipt, TrendingUp, TrendingDown,
  ClipboardCheck, ClipboardList, CreditCard, PieChart, BookOpen,
  BarChart3, ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

interface FinancialsSummary {
  ar_outstanding: number;
  ar_overdue_count: number;
  ar_overdue_total: number;
  ap_due_this_week: number;
  ap_due_today: number;
  payments_today_total: number;
  payments_today_count: number;
}

const fmt = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function FinancialsHub() {
  const { hasPermission, isAdmin } = useAuth();
  const [summary, setSummary] = useState<FinancialsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get("/financials/summary")
      .then((r) => setSummary(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const canAR = isAdmin || hasPermission("ar.view");
  const canAP = isAdmin || hasPermission("ap.view");
  const canInvoice = isAdmin || hasPermission("invoices.view");

  return (
    <div className="space-y-6 p-6">
      <Breadcrumbs />
      <div>
        <h1 className="text-2xl font-bold">Financials</h1>
        <p className="text-muted-foreground text-sm">
          Your financial command center — AR, AP, billing, and reporting.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="AR Outstanding"
          value={loading ? "—" : fmt(summary?.ar_outstanding ?? 0)}
          icon={TrendingUp}
          color="text-blue-600"
        />
        <SummaryCard
          label="Overdue Invoices"
          value={loading ? "—" : String(summary?.ar_overdue_count ?? 0)}
          subtitle={loading ? "" : fmt(summary?.ar_overdue_total ?? 0)}
          icon={TrendingDown}
          color="text-red-500"
        />
        <SummaryCard
          label="AP Due This Week"
          value={loading ? "—" : fmt(summary?.ap_due_this_week ?? 0)}
          icon={Receipt}
          color="text-amber-600"
        />
        <SummaryCard
          label="Payments Today"
          value={loading ? "—" : fmt(summary?.payments_today_total ?? 0)}
          subtitle={loading ? "" : `${summary?.payments_today_count ?? 0} payment(s)`}
          icon={DollarSign}
          color="text-green-600"
        />
      </div>

      {/* Quick Access Tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {canAR && (
          <>
            <HubTile
              label="Financials Board"
              description="Full AR/AP command center"
              href="/financials/board"
              icon={BarChart3}
            />
            <HubTile
              label="Billing"
              description="Monthly billing & statements"
              href="/billing"
              icon={Receipt}
            />
            <HubTile
              label="Invoice Review"
              description="Review draft invoices"
              href="/ar/invoices/review"
              icon={ClipboardCheck}
            />
            <HubTile
              label="Orders"
              description="Sales orders & quotes"
              href="/ar/orders"
              icon={ClipboardList}
            />
            <HubTile
              label="Statements"
              description="Customer statements"
              href="/ar/statements"
              icon={FileText}
            />
            <HubTile
              label="AR Aging"
              description="Accounts receivable aging"
              href="/ar/aging"
              icon={TrendingDown}
            />
          </>
        )}
        {canAP && (
          <>
            <HubTile
              label="Vendors & Bills"
              description="AP bills & vendor management"
              href="/ap/bills"
              icon={Receipt}
            />
            <HubTile
              label="Purchase Orders"
              description="Manage purchase orders"
              href="/ap/purchase-orders"
              icon={ClipboardList}
            />
            <HubTile
              label="AP Aging"
              description="Accounts payable aging"
              href="/ap/aging"
              icon={TrendingUp}
            />
          </>
        )}
        {canInvoice && (
          <>
            <HubTile
              label="Payments"
              description="Customer payments received"
              href="/ar/payments"
              icon={CreditCard}
            />
          </>
        )}
        <HubTile
          label="Journal Entries"
          description="Manual journal entries"
          href="/journal-entries"
          icon={BookOpen}
        />
        <HubTile
          label="Reports"
          description="Financial reports & analytics"
          href="/reports"
          icon={PieChart}
        />
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  subtitle,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-5">
        <div className={cn("rounded-lg bg-muted p-2.5", color)}>
          <Icon className="size-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-bold">{value}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function HubTile({
  label,
  description,
  href,
  icon: Icon,
}: {
  label: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Link to={href}>
      <Card className="group hover:border-primary/30 hover:bg-accent/30 transition-all cursor-pointer h-full">
        <CardContent className="flex items-center gap-3 pt-4 pb-4">
          <div className="rounded-lg bg-muted p-2">
            <Icon className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">{label}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
        </CardContent>
      </Card>
    </Link>
  );
}

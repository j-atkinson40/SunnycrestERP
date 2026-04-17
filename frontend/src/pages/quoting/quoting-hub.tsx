import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import apiClient from "@/lib/api-client";
import { salesService } from "@/services/sales-service";
import type { Quote } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DollarSign,
  Clock,
  AlertTriangle,
  Trophy,
  Send,
  Copy,
  ArrowRightCircle,
} from "lucide-react";

interface QuoteSummary {
  pipeline_value: number;
  awaiting_response: number;
  expiring_soon: number;
  won_this_month: number;
  won_value_this_month: number;
}

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(n));
}

function fmtCurrencyCents(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function daysUntil(d: string | null): number | null {
  if (!d) return null;
  const ms = new Date(d).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

function quoteStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "sent":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Sent
        </Badge>
      );
    case "accepted":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Accepted
        </Badge>
      );
    case "rejected":
      return <Badge variant="destructive">Rejected</Badge>;
    case "expired":
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Expired
        </Badge>
      );
    case "converted":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Won
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: typeof DollarSign;
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-bold">{value}</p>
          {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
        </div>
        <div className={`rounded-md p-2 ${accent}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Card>
  );
}

export default function QuotingHubPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("ar.create_quote");
  const canConvert = hasPermission("ar.create_order");

  const [summary, setSummary] = useState<QuoteSummary | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"recent" | "value" | "expiry">("recent");
  const [busy, setBusy] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, listRes] = await Promise.all([
        apiClient.get<QuoteSummary>("/sales/quotes/summary"),
        salesService.getQuotes(1, 100, filterStatus || undefined),
      ]);
      setSummary(sumRes.data);
      setQuotes(listRes.items);
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const filtered = useMemo(() => {
    let rows = quotes;
    if (search.trim()) {
      const s = search.toLowerCase();
      rows = rows.filter(
        (q) =>
          q.number.toLowerCase().includes(s) ||
          (q.customer_name ?? "").toLowerCase().includes(s),
      );
    }
    const sorted = [...rows];
    if (sortBy === "value") {
      sorted.sort((a, b) => Number(b.total) - Number(a.total));
    } else if (sortBy === "expiry") {
      sorted.sort((a, b) => {
        const ax = a.expiry_date ? new Date(a.expiry_date).getTime() : Number.MAX_SAFE_INTEGER;
        const bx = b.expiry_date ? new Date(b.expiry_date).getTime() : Number.MAX_SAFE_INTEGER;
        return ax - bx;
      });
    }
    return sorted;
  }, [quotes, search, sortBy]);

  const doSend = async (id: string) => {
    setBusy(id);
    try {
      await apiClient.patch(`/sales/quotes/${id}/status`, { status: "sent" });
      await loadAll();
    } finally {
      setBusy(null);
    }
  };

  const doConvert = async (id: string) => {
    setBusy(id);
    try {
      const so = await salesService.convertQuote(id);
      navigate(`/ar/orders/${so.id}`);
    } finally {
      setBusy(null);
    }
  };

  const doDuplicate = async (id: string) => {
    setBusy(id);
    try {
      const r = await apiClient.post<Quote>(`/sales/quotes/${id}/duplicate`);
      navigate(`/quoting/${r.data.id}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Quoting</h1>
          <p className="text-muted-foreground">Track your active pipeline</p>
        </div>
        {canCreate && (
          <Button onClick={() => navigate("/ar/quotes/new")}>New Quote</Button>
        )}
      </div>

      {/* Pipeline widgets */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          icon={DollarSign}
          label="Pipeline Value"
          value={summary ? fmtCurrency(summary.pipeline_value) : "…"}
          sub="Draft + sent quotes"
          accent="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200"
        />
        <StatCard
          icon={Clock}
          label="Awaiting Response"
          value={summary ? summary.awaiting_response : "…"}
          sub="Sent, not yet acted on"
          accent="bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200"
        />
        <StatCard
          icon={AlertTriangle}
          label="Expiring Soon"
          value={summary ? summary.expiring_soon : "…"}
          sub="Within 7 days"
          accent="bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200"
        />
        <StatCard
          icon={Trophy}
          label="Won This Month"
          value={summary ? summary.won_this_month : "…"}
          sub={summary ? fmtCurrency(summary.won_value_this_month) : ""}
          accent="bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search quote # or customer..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
          <option value="converted">Won</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as "recent" | "value" | "expiry")}
        >
          <option value="recent">Most Recent</option>
          <option value="value">Highest Value</option>
          <option value="expiry">Expiring Soonest</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Quote #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Expiry</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No quotes found
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((q) => {
                const du = daysUntil(q.expiry_date);
                const expiringSoon =
                  q.status === "sent" && du !== null && du <= 7 && du >= 0;
                return (
                  <TableRow key={q.id}>
                    <TableCell className="font-medium">
                      <Link to={`/quoting/${q.id}`} className="hover:underline">
                        {q.number}
                      </Link>
                    </TableCell>
                    <TableCell>{q.customer_name || "\u2014"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {fmtDate(q.quote_date)}
                    </TableCell>
                    <TableCell
                      className={
                        expiringSoon
                          ? "font-medium text-rose-600"
                          : "text-muted-foreground"
                      }
                    >
                      {fmtDate(q.expiry_date)}
                      {expiringSoon && du !== null && (
                        <span className="ml-1 text-xs">
                          ({du}d)
                        </span>
                      )}
                    </TableCell>
                    <TableCell>{quoteStatusBadge(q.status)}</TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtCurrencyCents(q.total)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {q.status === "draft" && canCreate && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy === q.id}
                            onClick={() => doSend(q.id)}
                            title="Mark sent"
                          >
                            <Send className="h-4 w-4" />
                          </Button>
                        )}
                        {["sent", "accepted", "draft"].includes(q.status) &&
                          canConvert && (
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={busy === q.id}
                              onClick={() => doConvert(q.id)}
                              title="Convert to order"
                            >
                              <ArrowRightCircle className="h-4 w-4" />
                            </Button>
                          )}
                        {canCreate && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy === q.id}
                            onClick={() => doDuplicate(q.id)}
                            title="Duplicate"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { Quote, SalesStats } from "@/types/sales";
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
        <Badge
          variant="outline"
          className="text-muted-foreground"
        >
          Expired
        </Badge>
      );
    case "converted":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Converted
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

export default function QuotesPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("ar.create_quote");

  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<SalesStats | null>(null);

  const loadQuotes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getQuotes(
        page,
        20,
        filterStatus || undefined,
      );
      setQuotes(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus]);

  const loadStats = useCallback(async () => {
    try {
      setStats(await salesService.getStats());
    } catch {
      /* non-critical */
    }
  }, []);

  useEffect(() => {
    loadQuotes();
  }, [loadQuotes]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const totalPages = Math.ceil(total / 20);

  const filteredQuotes = search
    ? quotes.filter(
        (q) =>
          q.number.toLowerCase().includes(search.toLowerCase()) ||
          (q.customer_name ?? "").toLowerCase().includes(search.toLowerCase()),
      )
    : quotes;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Quotes</h1>
          <p className="text-muted-foreground">{total} quotes</p>
        </div>
        {canCreate && (
          <Button onClick={() => navigate("/ar/quotes/new")}>
            New Quote
          </Button>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Quotes</p>
            <p className="text-2xl font-bold">{stats.total_quotes}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Open Quotes</p>
            <p className="text-2xl font-bold text-blue-600">
              {stats.open_quotes}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Orders</p>
            <p className="text-2xl font-bold text-green-600">
              {stats.total_orders}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Outstanding AR</p>
            <p className="text-2xl font-bold">
              {fmtCurrency(stats.total_ar_outstanding)}
            </p>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search quote numbers or customers..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
          <option value="converted">Converted</option>
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : filteredQuotes.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  No quotes found
                </TableCell>
              </TableRow>
            ) : (
              filteredQuotes.map((quote) => (
                <TableRow key={quote.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/ar/quotes/${quote.id}`}
                      className="hover:underline"
                    >
                      {quote.number}
                    </Link>
                  </TableCell>
                  <TableCell>{quote.customer_name || "\u2014"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(quote.quote_date)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(quote.expiry_date)}
                  </TableCell>
                  <TableCell>{quoteStatusBadge(quote.status)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(quote.total)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

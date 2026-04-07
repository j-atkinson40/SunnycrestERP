import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X, Search } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import { salesService } from "@/services/sales-service";
import type { Invoice } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function isOverdue(dueDate: string, status: string) {
  if (["paid", "void", "write_off", "draft"].includes(status)) return false;
  return new Date(dueDate) < new Date();
}

function invoiceStatusBadge(status: string) {
  const s = status.toLowerCase();
  switch (s) {
    case "draft":
      return <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">Draft</Badge>;
    case "open":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Open</Badge>;
    case "sent":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Sent
        </Badge>
      );
    case "partial":
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          Partial
        </Badge>
      );
    case "paid":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Paid
        </Badge>
      );
    case "overdue":
      return <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">Overdue</Badge>;
    case "void":
      return (
        <Badge className="bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
          Void
        </Badge>
      );
    case "write_off":
      return (
        <Badge className="bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
          Write-Off
        </Badge>
      );
    default:
      return <Badge className="bg-gray-100 text-gray-700">{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
  }
}

const PER_PAGE = 20;
const SYNC_BANNER_DISMISS_KEY = "invoice_sync_error_banner_dismissed";

function providerLabel(provider: string | undefined): string {
  switch (provider) {
    case "quickbooks_online":
      return "QuickBooks Online";
    case "quickbooks_desktop":
      return "QuickBooks Desktop";
    case "sage_100":
      return "Sage 100";
    default:
      return "your accounting software";
  }
}

export default function InvoicesPage() {
  useAuth();

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncBannerDismissed, setSyncBannerDismissed] = useState(() => {
    return sessionStorage.getItem(SYNC_BANNER_DISMISS_KEY) === "true";
  });

  let tenantSettings: Record<string, unknown> = {};
  try {
    const theme = usePresetTheme();
    tenantSettings = theme.tenantSettings;
  } catch {
    // PresetThemeProvider may not be available in all contexts
  }

  const connectionStatus = tenantSettings.accounting_connection_status as string | undefined;
  const lastSyncError = tenantSettings.last_sync_error as string | undefined;
  const provider = tenantSettings.accounting_provider as string | undefined;
  const showSyncBanner =
    !syncBannerDismissed &&
    connectionStatus === "connected" &&
    !!lastSyncError;

  const dismissSyncBanner = () => {
    sessionStorage.setItem(SYNC_BANNER_DISMISS_KEY, "true");
    setSyncBannerDismissed(true);
  };

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        per_page: String(PER_PAGE),
      };
      if (filterStatus) params.status = filterStatus;
      if (searchQuery) params.q = searchQuery;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const data = await salesService.getInvoices(
        page,
        PER_PAGE,
        filterStatus || undefined,
        undefined,
        searchQuery || undefined,
        dateFrom || undefined,
        dateTo || undefined,
      );
      setInvoices(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus, searchQuery, dateFrom, dateTo]);

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="space-y-6">
      {/* Sync error banner */}
      {showSyncBanner && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-center justify-between gap-4">
          <p className="text-sm text-amber-900">
            Accounting sync error — invoices failed to sync to{" "}
            {providerLabel(provider)}.{" "}
            <Link
              to="/settings/integrations/accounting"
              className="font-medium underline hover:text-amber-700"
            >
              View and fix errors →
            </Link>
          </p>
          <button
            type="button"
            onClick={dismissSyncBanner}
            className="shrink-0 text-amber-600 hover:text-amber-800 transition-colors"
            aria-label="Dismiss sync error banner"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Invoices</h1>
          <p className="text-muted-foreground">{total} invoices</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by customer or invoice #..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="pl-9"
          />
        </div>
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
          <option value="open">Open</option>
          <option value="sent">Sent</option>
          <option value="partial">Partial</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="void">Void</option>
        </select>
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          className="w-[140px] h-9"
          placeholder="From"
        />
        <span className="text-muted-foreground text-sm">\u2013</span>
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          className="w-[140px] h-9"
          placeholder="To"
        />
        {(searchQuery || dateFrom || dateTo || filterStatus) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setSearchQuery(""); setDateFrom(""); setDateTo(""); setFilterStatus(""); setPage(1); }}
          >
            <X className="h-4 w-4 mr-1" /> Clear
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice #</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Invoice Date</TableHead>
              <TableHead>Due Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="text-right">Paid</TableHead>
              <TableHead className="text-right">Balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : invoices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  No invoices found
                </TableCell>
              </TableRow>
            ) : (
              invoices.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/ar/invoices/${invoice.id}`}
                      className="hover:underline"
                    >
                      {invoice.number}
                    </Link>
                  </TableCell>
                  <TableCell>{invoice.customer_name || "\u2014"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(invoice.invoice_date)}
                  </TableCell>
                  <TableCell>
                    <span
                      className={
                        isOverdue(invoice.due_date, invoice.status)
                          ? "text-red-600 font-medium"
                          : "text-muted-foreground"
                      }
                    >
                      {fmtDate(invoice.due_date)}
                    </span>
                  </TableCell>
                  <TableCell>{invoiceStatusBadge(invoice.status)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(invoice.total)}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(invoice.amount_paid)}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(invoice.balance_remaining)}
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

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { Invoice } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

function isOverdue(dueDate: string, status: string) {
  if (["paid", "void", "write_off", "draft"].includes(status)) return false;
  return new Date(dueDate) < new Date();
}

function invoiceStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
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
      return <Badge variant="destructive">Overdue</Badge>;
    case "void":
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Void
        </Badge>
      );
    case "write_off":
      return (
        <Badge variant="outline" className="text-muted-foreground">
          Write-Off
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

const PER_PAGE = 20;

export default function InvoicesPage() {
  useAuth();

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getInvoices(
        page,
        PER_PAGE,
        filterStatus || undefined,
      );
      setInvoices(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus]);

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Invoices</h1>
          <p className="text-muted-foreground">{total} invoices</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="partial">Partial</option>
          <option value="paid">Paid</option>
          <option value="overdue">Overdue</option>
          <option value="void">Void</option>
        </select>
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
                  <TableCell>{invoice.customer_name || "—"}</TableCell>
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

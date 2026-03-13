import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { vendorBillService } from "@/services/vendor-bill-service";
import type { VendorBillListItem } from "@/types/vendor-bill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function billStatusBadge(status: string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "pending":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Pending
        </Badge>
      );
    case "approved":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Approved
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
    case "void":
      return <Badge variant="destructive">Void</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function isOverdue(dueDate: string, status: string) {
  if (["paid", "void"].includes(status)) return false;
  return new Date(dueDate) < new Date();
}

export default function VendorBillsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canCreate = hasPermission("ap.create_bill");

  const [bills, setBills] = useState<VendorBillListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const loadBills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await vendorBillService.getAll(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
      );
      setBills(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus]);

  useEffect(() => {
    loadBills();
  }, [loadBills]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Vendor Bills</h1>
          <p className="text-muted-foreground">{total} total bills</p>
        </div>
        {canCreate && (
          <Button onClick={() => navigate("/ap/bills/new")}>
            New Bill
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search bill numbers..."
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
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="partial">Partially Paid</option>
          <option value="paid">Paid</option>
          <option value="void">Void</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Bill #</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Invoice #</TableHead>
              <TableHead>Bill Date</TableHead>
              <TableHead>Due Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
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
            ) : bills.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  No bills found
                </TableCell>
              </TableRow>
            ) : (
              bills.map((bill) => (
                <TableRow key={bill.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/ap/bills/${bill.id}`}
                      className="hover:underline"
                    >
                      {bill.number}
                    </Link>
                  </TableCell>
                  <TableCell>{bill.vendor_name || "\u2014"}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {bill.vendor_invoice_number || "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(bill.bill_date)}
                  </TableCell>
                  <TableCell>
                    <span
                      className={
                        isOverdue(bill.due_date, bill.status)
                          ? "text-red-600 font-medium"
                          : "text-muted-foreground"
                      }
                    >
                      {fmtDate(bill.due_date)}
                      {isOverdue(bill.due_date, bill.status) && " (overdue)"}
                    </span>
                  </TableCell>
                  <TableCell>{billStatusBadge(bill.status)}</TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(bill.total)}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(bill.balance_remaining)}
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

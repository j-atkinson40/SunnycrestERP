import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { salesService } from "@/services/sales-service";
import type { CustomerPayment } from "@/types/sales";
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
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function methodBadge(method: string) {
  switch (method) {
    case "check":
      return <Badge variant="outline">Check</Badge>;
    case "ach":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          ACH
        </Badge>
      );
    case "credit_card":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Credit Card
        </Badge>
      );
    case "cash":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Cash
        </Badge>
      );
    case "wire":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Wire
        </Badge>
      );
    default:
      return <Badge variant="outline">{method}</Badge>;
  }
}

function appliedTo(payment: CustomerPayment): string {
  if (!payment.applications || payment.applications.length === 0) return "\u2014";
  return payment.applications
    .map((a) => a.invoice_number ?? a.invoice_id)
    .filter(Boolean)
    .join(", ");
}

const PER_PAGE = 20;

export default function CustomerPaymentsPage() {
  // useAuth is consumed here to keep the hook usage consistent with the rest
  // of the app (e.g. future permission gates on AR recording).
  useAuth();

  const [payments, setPayments] = useState<CustomerPayment[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await salesService.getPayments(page, PER_PAGE);
      setPayments(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Customer Payments</h1>
        <p className="text-muted-foreground">{total} payments</p>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Reference #</TableHead>
              <TableHead>Applied To</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : payments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  No payments found
                </TableCell>
              </TableRow>
            ) : (
              payments.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">
                    {p.customer_name ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {fmtDate(p.payment_date)}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(p.total_amount)}
                  </TableCell>
                  <TableCell>{methodBadge(p.payment_method)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {p.reference_number ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {appliedTo(p)}
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

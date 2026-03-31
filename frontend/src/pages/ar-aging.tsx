import { useCallback, useEffect, useState } from "react";
import { ContextualExplanation } from "@/components/contextual-explanation";
import { salesService } from "@/services/sales-service";
import type { ARAgingReport } from "@/types/sales";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { CreditCard } from "lucide-react";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

export default function ARAgingPage() {
  const [report, setReport] = useState<ARAgingReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [paymentCustomer, setPaymentCustomer] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const fetchReport = useCallback(async () => {
    try {
      const data = await salesService.getARAgingReport();
      setReport(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">No data available.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <h1 className="text-2xl font-semibold">AR Aging Report</h1>
      <ContextualExplanation explanationKey="ar_aging_buckets" />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Current</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.current)}</p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">1-30 Days</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.days_1_30)}</p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">31-60 Days</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.days_31_60)}</p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">61-90 Days</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.days_61_90)}</p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">90+ Days</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.days_over_90)}</p>
        </div>
        <div className="rounded-lg border p-4">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="text-2xl font-bold">{fmtCurrency(report.company_summary.total)}</p>
        </div>
      </div>

      {/* Customer Detail Table */}
      {report.customers.length === 0 ? (
        <p className="text-muted-foreground">No outstanding receivables.</p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Account #</TableHead>
                <TableHead className="text-right">Current</TableHead>
                <TableHead className="text-right">1-30</TableHead>
                <TableHead className="text-right">31-60</TableHead>
                <TableHead className="text-right">61-90</TableHead>
                <TableHead className="text-right">90+</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.customers.map((customer) => (
                <TableRow key={customer.customer_id}>
                  <TableCell>{customer.customer_name}</TableCell>
                  <TableCell>{customer.account_number ?? "—"}</TableCell>
                  <TableCell className="text-right">{fmtCurrency(customer.buckets.current)}</TableCell>
                  <TableCell className="text-right">{fmtCurrency(customer.buckets.days_1_30)}</TableCell>
                  <TableCell className="text-right">{fmtCurrency(customer.buckets.days_31_60)}</TableCell>
                  <TableCell className="text-right">{fmtCurrency(customer.buckets.days_61_90)}</TableCell>
                  <TableCell className="text-right">{fmtCurrency(customer.buckets.days_over_90)}</TableCell>
                  <TableCell className="text-right font-medium">{fmtCurrency(customer.buckets.total)}</TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() =>
                        setPaymentCustomer({
                          id: customer.customer_id,
                          name: customer.customer_name,
                        })
                      }
                    >
                      <CreditCard className="w-3.5 h-3.5 mr-1" />
                      Pay
                    </Button>
                  </TableCell>
                </TableRow>
              ))}

              {/* Footer totals row */}
              <TableRow className="border-t-2 font-bold">
                <TableCell colSpan={2}>Total</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.current)}</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.days_1_30)}</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.days_31_60)}</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.days_61_90)}</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.days_over_90)}</TableCell>
                <TableCell className="text-right">{fmtCurrency(report.company_summary.total)}</TableCell>
                <TableCell />
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}

      {/* Per-customer payment dialog */}
      {paymentCustomer && (
        <RecordPaymentDialog
          open={!!paymentCustomer}
          onClose={() => setPaymentCustomer(null)}
          onSuccess={() => {
            fetchReport();
            setPaymentCustomer(null);
          }}
          customerId={paymentCustomer.id}
          customerName={paymentCustomer.name}
        />
      )}
    </div>
  );
}

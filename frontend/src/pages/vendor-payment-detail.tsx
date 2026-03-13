import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { vendorPaymentService } from "@/services/vendor-payment-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { VendorPayment } from "@/types/vendor-payment";
import { Button } from "@/components/ui/button";
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
import { toast } from "sonner";

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
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
    case "wire":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Wire
        </Badge>
      );
    case "credit_card":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Credit Card
        </Badge>
      );
    case "cash":
      return <Badge variant="secondary">Cash</Badge>;
    default:
      return <Badge variant="outline">{method}</Badge>;
  }
}

export default function VendorPaymentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canDelete = hasPermission("ap.record_payment");

  const [payment, setPayment] = useState<VendorPayment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPayment = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await vendorPaymentService.get(id);
      setPayment(data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load payment"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadPayment();
  }, [loadPayment]);

  async function handleDelete() {
    if (!id) return;
    if (
      !window.confirm(
        "Delete this payment? Bill balances will be reversed.",
      )
    )
      return;
    try {
      await vendorPaymentService.delete(id);
      toast.success("Payment deleted");
      navigate("/ap/payments");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to delete payment"));
    }
  }

  if (loading) return <div className="p-8 text-center">Loading...</div>;
  if (error)
    return (
      <div className="p-8 text-center text-destructive">{error}</div>
    );
  if (!payment) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/ap/payments"
            className="text-sm text-muted-foreground hover:underline"
          >
            &larr; Payments
          </Link>
          <h1 className="text-3xl font-bold">
            Payment — {fmtCurrency(payment.total_amount)}
          </h1>
          <p className="text-muted-foreground">
            Vendor: {payment.vendor_name || "\u2014"}
          </p>
        </div>
        {canDelete && (
          <Button variant="destructive" size="sm" onClick={handleDelete}>
            Delete Payment
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Payment Date</p>
          <p className="font-medium">
            {new Date(payment.payment_date).toLocaleDateString()}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Method</p>
          <div className="mt-1">{methodBadge(payment.payment_method)}</div>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Reference</p>
          <p className="font-medium">
            {payment.reference_number || "\u2014"}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="text-xl font-bold">
            {fmtCurrency(payment.total_amount)}
          </p>
        </Card>
      </div>

      {payment.notes && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Notes</p>
          <p className="text-sm whitespace-pre-wrap">{payment.notes}</p>
        </Card>
      )}

      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Applied to Bills</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bill #</TableHead>
                <TableHead className="text-right">Amount Applied</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payment.applications.map((app) => (
                <TableRow key={app.id}>
                  <TableCell className="font-medium">
                    {app.bill_number ? (
                      <Link
                        to={`/ap/bills/${app.bill_id}`}
                        className="hover:underline"
                      >
                        {app.bill_number}
                      </Link>
                    ) : (
                      app.bill_id
                    )}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {fmtCurrency(app.amount_applied)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <div className="text-xs text-muted-foreground space-y-0.5">
        {payment.created_by_name && (
          <p>Created by: {payment.created_by_name}</p>
        )}
        <p>Created: {new Date(payment.created_at).toLocaleString()}</p>
      </div>
    </div>
  );
}

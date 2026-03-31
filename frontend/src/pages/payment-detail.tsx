import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PaymentDetailData {
  id: string;
  customer_id: string;
  payment_date: string | null;
  total_amount: number;
  payment_method: string;
  reference_number?: string | null;
  notes?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  applications: Array<{
    invoice_id: string;
    invoice_number: string;
    invoice_date?: string | null;
    amount_applied: number;
    notes?: string | null;
  }>;
}

const METHOD_LABELS: Record<string, string> = {
  check: "Check",
  ach: "ACH",
  wire: "Wire",
  credit_card: "Credit Card",
  cash: "Cash",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PaymentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [payment, setPayment] = useState<PaymentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [voiding, setVoiding] = useState(false);
  const [confirmVoid, setConfirmVoid] = useState(false);

  useEffect(() => {
    if (!id) return;
    apiClient
      .get(`/sales/payments/${id}`)
      .then((r) => setPayment(r.data))
      .catch((err) => toast.error(getApiErrorMessage(err, "Failed to load payment")))
      .finally(() => setLoading(false));
  }, [id]);

  const handleVoid = async () => {
    if (!id) return;
    setVoiding(true);
    try {
      await apiClient.post(`/sales/payments/${id}/void`);
      toast.success("Payment voided");
      navigate("/ar/payments");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to void payment"));
    } finally {
      setVoiding(false);
      setConfirmVoid(false);
    }
  };

  const fmtDate = (s?: string | null) =>
    s
      ? new Date(s).toLocaleDateString("en-US", {
          month: "long",
          day: "numeric",
          year: "numeric",
        })
      : "\u2014";

  const fmtCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!payment) return null;

  return (
    <div className="space-y-6 p-6 max-w-3xl">
      {/* Back button */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/ar/payments")}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
      </div>

      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold">
          Payment{payment.reference_number ? ` #${payment.reference_number}` : ""}
        </h1>
        <p className="text-muted-foreground">
          {fmtDate(payment.payment_date)} &middot;{" "}
          {METHOD_LABELS[payment.payment_method] ?? payment.payment_method} &middot;{" "}
          {fmtCurrency(payment.total_amount)}
        </p>
      </div>

      {/* Payment Details card */}
      <Card className="p-5 space-y-3">
        <h2 className="font-semibold">Payment Details</h2>
        <div className="grid grid-cols-2 gap-y-2 text-sm">
          <span className="text-muted-foreground">Date</span>
          <span>{fmtDate(payment.payment_date)}</span>

          <span className="text-muted-foreground">Method</span>
          <span>{METHOD_LABELS[payment.payment_method] ?? payment.payment_method}</span>

          {payment.reference_number && (
            <>
              <span className="text-muted-foreground">Reference</span>
              <span>{payment.reference_number}</span>
            </>
          )}

          <span className="text-muted-foreground">Amount</span>
          <span className="font-semibold">{fmtCurrency(payment.total_amount)}</span>

          {payment.notes && (
            <>
              <span className="text-muted-foreground">Notes</span>
              <span>{payment.notes}</span>
            </>
          )}

          {payment.created_at && (
            <>
              <span className="text-muted-foreground">Recorded</span>
              <span>{fmtDate(payment.created_at)}</span>
            </>
          )}
        </div>
      </Card>

      {/* Applied To card */}
      <Card className="p-5">
        <h2 className="font-semibold mb-3">Applied To</h2>
        {payment.applications.length === 0 ? (
          <p className="text-sm text-muted-foreground">No invoice applications recorded.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                <th className="text-left pb-2">Invoice #</th>
                <th className="text-left pb-2">Date</th>
                <th className="text-right pb-2">Applied</th>
                <th className="text-left pb-2 pl-3">Notes</th>
              </tr>
            </thead>
            <tbody>
              {payment.applications.map((app) => (
                <tr key={app.invoice_id} className="border-b last:border-0">
                  <td className="py-2 font-mono text-xs">{app.invoice_number}</td>
                  <td className="py-2 text-muted-foreground">{fmtDate(app.invoice_date)}</td>
                  <td className="py-2 text-right font-medium">
                    {fmtCurrency(app.amount_applied)}
                  </td>
                  <td className="py-2 pl-3 text-xs text-green-600">{app.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Void section */}
      {!confirmVoid ? (
        <Button
          variant="outline"
          className="text-destructive border-destructive/30 hover:bg-destructive/5"
          onClick={() => setConfirmVoid(true)}
        >
          Void Payment
        </Button>
      ) : (
        <Card className="p-4 border-destructive/30 bg-destructive/5 space-y-3">
          <p className="text-sm font-medium text-destructive">Void this payment?</p>
          <p className="text-sm text-muted-foreground">
            This will reverse {fmtCurrency(payment.total_amount)} applied to{" "}
            {payment.applications.length} invoice
            {payment.applications.length !== 1 ? "s" : ""}. Those invoices will return to
            unpaid status.
          </p>
          <div className="flex gap-2">
            <Button
              variant="destructive"
              size="sm"
              onClick={handleVoid}
              disabled={voiding}
            >
              {voiding ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin mr-1" /> Voiding...
                </>
              ) : (
                "Void Payment"
              )}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setConfirmVoid(false)}>
              Cancel
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

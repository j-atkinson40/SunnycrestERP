import type { InvoicePeek } from "@/types/peek";
import { PeekField, StatusBadge, fmtCurrency, fmtDate } from "./_shared";


export function InvoicePeekRenderer({ data }: { data: InvoicePeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-invoice">
      <PeekField label="Invoice #" value={data.invoice_number} />
      <PeekField label="Customer" value={data.customer_name} />
      <PeekField label="Total" value={fmtCurrency(data.amount_total)} />
      <PeekField label="Paid" value={fmtCurrency(data.amount_paid)} />
      <PeekField label="Due" value={fmtCurrency(data.amount_due)} />
      <PeekField label="Due date" value={fmtDate(data.due_date)} />
      <div className="pt-1">
        <StatusBadge status={data.status} />
      </div>
    </div>
  );
}

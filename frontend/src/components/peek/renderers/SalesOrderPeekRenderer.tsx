import type { SalesOrderPeek } from "@/types/peek";
import { PeekField, StatusBadge, fmtCurrency, fmtDate } from "./_shared";


export function SalesOrderPeekRenderer({ data }: { data: SalesOrderPeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-sales_order">
      <PeekField label="Order #" value={data.order_number} />
      <PeekField label="Customer" value={data.customer_name} />
      <PeekField label="Deceased" value={data.deceased_name} />
      <PeekField label="Required" value={fmtDate(data.required_date)} />
      <PeekField label="Total" value={fmtCurrency(data.total)} />
      <PeekField
        label="Lines"
        value={`${data.line_count} item${data.line_count === 1 ? "" : "s"}`}
      />
      <div className="pt-1">
        <StatusBadge status={data.status} />
      </div>
    </div>
  );
}

export interface POLine {
  id: string;
  po_id: string;
  product_id: string | null;
  product_name: string | null;
  description: string;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: number;
  line_total: number;
  sort_order: number;
  created_at: string;
}

export interface POLineCreate {
  product_id?: string | null;
  description: string;
  quantity_ordered: number;
  unit_cost: number;
  sort_order?: number;
}

export interface PurchaseOrder {
  id: string;
  company_id: string;
  number: string;
  vendor_id: string;
  vendor_name: string | null;
  status: string;
  order_date: string;
  expected_date: string | null;
  shipping_address: string | null;
  subtotal: number;
  tax_amount: number;
  total: number;
  notes: string | null;
  sent_at: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  lines: POLine[];
}

export interface PurchaseOrderListItem {
  id: string;
  number: string;
  vendor_id: string;
  vendor_name: string | null;
  status: string;
  order_date: string;
  expected_date: string | null;
  subtotal: number;
  tax_amount: number;
  total: number;
  created_at: string;
}

export interface PurchaseOrderCreate {
  vendor_id: string;
  order_date?: string;
  expected_date?: string;
  shipping_address?: string;
  tax_amount?: number;
  notes?: string;
  lines: POLineCreate[];
}

export interface PurchaseOrderUpdate {
  vendor_id?: string;
  order_date?: string;
  expected_date?: string;
  shipping_address?: string;
  tax_amount?: number;
  notes?: string;
  lines?: POLineCreate[];
}

export interface PaginatedPurchaseOrders {
  items: PurchaseOrderListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface POStats {
  total_pos: number;
  draft: number;
  sent: number;
  partial: number;
  received: number;
  closed: number;
}

export interface ReceiveLineItem {
  po_line_id: string;
  quantity_received: number;
}

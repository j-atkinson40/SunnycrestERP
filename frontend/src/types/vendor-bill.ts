export interface BillLine {
  id: string;
  bill_id: string;
  po_line_id: string | null;
  description: string;
  quantity: number | null;
  unit_cost: number | null;
  amount: number;
  expense_category: string | null;
  sort_order: number;
  created_at: string;
}

export interface BillLineCreate {
  po_line_id?: string | null;
  description: string;
  quantity?: number | null;
  unit_cost?: number | null;
  amount: number;
  expense_category?: string | null;
  sort_order?: number;
}

export interface VendorBill {
  id: string;
  company_id: string;
  number: string;
  vendor_id: string;
  vendor_name: string | null;
  vendor_invoice_number: string | null;
  po_id: string | null;
  po_number: string | null;
  status: string;
  bill_date: string;
  due_date: string;
  subtotal: number;
  tax_amount: number;
  total: number;
  amount_paid: number;
  balance_remaining: number;
  payment_terms: string | null;
  notes: string | null;
  approved_by: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  lines: BillLine[];
}

export interface VendorBillListItem {
  id: string;
  number: string;
  vendor_id: string;
  vendor_name: string | null;
  vendor_invoice_number: string | null;
  status: string;
  bill_date: string;
  due_date: string;
  total: number;
  amount_paid: number;
  balance_remaining: number;
  created_at: string;
}

export interface VendorBillCreate {
  vendor_id: string;
  vendor_invoice_number?: string;
  po_id?: string;
  bill_date: string;
  due_date?: string;
  subtotal?: number;
  tax_amount?: number;
  total?: number;
  payment_terms?: string;
  notes?: string;
  lines?: BillLineCreate[];
}

export interface VendorBillUpdate {
  vendor_id?: string;
  vendor_invoice_number?: string;
  po_id?: string;
  bill_date?: string;
  due_date?: string;
  tax_amount?: number;
  payment_terms?: string;
  notes?: string;
  lines?: BillLineCreate[];
}

export interface PaginatedVendorBills {
  items: VendorBillListItem[];
  total: number;
  page: number;
  per_page: number;
}

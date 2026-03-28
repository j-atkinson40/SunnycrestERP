// ---------------------------------------------------------------------------
// Quote Lines
// ---------------------------------------------------------------------------

export interface QuoteLine {
  id: string;
  quote_id: string;
  product_id: string | null;
  product_name: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
}

export interface QuoteLineCreate {
  product_id?: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  sort_order?: number;
}

// ---------------------------------------------------------------------------
// Quotes
// ---------------------------------------------------------------------------

export interface Quote {
  id: string;
  company_id: string;
  number: string;
  customer_id: string;
  customer_name: string | null;
  status: string;
  quote_date: string;
  expiry_date: string;
  payment_terms: string | null;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  lines: QuoteLine[];
}

export interface QuoteCreate {
  customer_id: string;
  quote_date: string;
  expiry_date: string;
  payment_terms?: string | null;
  tax_rate?: string;
  notes?: string | null;
  lines: QuoteLineCreate[];
}

export interface QuoteUpdate {
  status?: string;
  expiry_date?: string;
  payment_terms?: string | null;
  notes?: string | null;
}

export interface PaginatedQuotes {
  items: Quote[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Sales Order Lines
// ---------------------------------------------------------------------------

export interface SalesOrderLine {
  id: string;
  sales_order_id: string;
  product_id: string | null;
  product_name: string | null;
  description: string;
  quantity: string;
  quantity_shipped: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
  has_conditional_pricing?: boolean;
  is_call_office?: boolean;
  price_without_our_product?: string | null;
}

export interface SalesOrderLineCreate {
  product_id?: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  sort_order?: number;
}

// ---------------------------------------------------------------------------
// Sales Orders
// ---------------------------------------------------------------------------

export interface SalesOrder {
  id: string;
  company_id: string;
  number: string;
  customer_id: string;
  customer_name: string | null;
  quote_id: string | null;
  status: string;
  order_date: string;
  required_date: string | null;
  shipped_date: string | null;
  payment_terms: string | null;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  ship_to_name: string | null;
  ship_to_address: string | null;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  lines: SalesOrderLine[];
}

export interface SalesOrderCreate {
  customer_id: string;
  quote_id?: string | null;
  order_date: string;
  required_date?: string | null;
  payment_terms?: string | null;
  tax_rate?: string;
  ship_to_name?: string | null;
  ship_to_address?: string | null;
  notes?: string | null;
  lines: SalesOrderLineCreate[];
}

export interface SalesOrderUpdate {
  status?: string;
  required_date?: string | null;
  shipped_date?: string | null;
  notes?: string | null;
}

export interface PaginatedSalesOrders {
  items: SalesOrder[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Invoice Lines
// ---------------------------------------------------------------------------

export interface InvoiceLine {
  id: string;
  invoice_id: string;
  product_id: string | null;
  product_name: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  sort_order: number;
}

export interface InvoiceLineCreate {
  product_id?: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  sort_order?: number;
}

// ---------------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------------

export interface Invoice {
  id: string;
  company_id: string;
  number: string;
  customer_id: string;
  customer_name: string | null;
  sales_order_id: string | null;
  status: string;
  invoice_date: string;
  due_date: string;
  payment_terms: string | null;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  total: string;
  amount_paid: string;
  balance_remaining: string;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  lines: InvoiceLine[];
}

export interface InvoiceCreate {
  customer_id: string;
  sales_order_id?: string | null;
  invoice_date: string;
  due_date: string;
  payment_terms?: string | null;
  tax_rate?: string;
  notes?: string | null;
  lines: InvoiceLineCreate[];
}

export interface InvoiceUpdate {
  status?: string;
  notes?: string | null;
}

export interface PaginatedInvoices {
  items: Invoice[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Payment Applications
// ---------------------------------------------------------------------------

export interface PaymentApplication {
  id: string;
  payment_id: string;
  invoice_id: string;
  invoice_number: string | null;
  amount_applied: string;
}

export interface PaymentApplicationCreate {
  invoice_id: string;
  amount_applied: string;
}

// ---------------------------------------------------------------------------
// Customer Payments
// ---------------------------------------------------------------------------

export interface CustomerPayment {
  id: string;
  company_id: string;
  customer_id: string;
  customer_name: string | null;
  payment_date: string;
  total_amount: string;
  payment_method: string;
  reference_number: string | null;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  modified_at: string | null;
  applications: PaymentApplication[];
}

export interface CustomerPaymentCreate {
  customer_id: string;
  payment_date: string;
  total_amount: string;
  payment_method: string;
  reference_number?: string | null;
  notes?: string | null;
  applications: PaymentApplicationCreate[];
}

export interface PaginatedCustomerPayments {
  items: CustomerPayment[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// AR Aging
// ---------------------------------------------------------------------------

export interface ARAgingBucket {
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_over_90: string;
  total: string;
}

export interface ARAgingCustomer {
  customer_id: string;
  customer_name: string;
  account_number: string | null;
  buckets: ARAgingBucket;
}

export interface ARAgingReport {
  company_summary: ARAgingBucket;
  customers: ARAgingCustomer[];
}

// ---------------------------------------------------------------------------
// Sales Stats
// ---------------------------------------------------------------------------

export interface SalesStats {
  total_quotes: number;
  open_quotes: number;
  total_orders: number;
  open_orders: number;
  total_invoices: number;
  outstanding_invoices: number;
  total_ar_outstanding: string;
}

// ---------------------------------------------------------------------------
// Payment Import
// ---------------------------------------------------------------------------

export interface PaymentImportResultRow {
  row: number;
  message: string;
}

export interface PaymentImportResult {
  created: number;
  skipped: number;
  errors: PaymentImportResultRow[];
}

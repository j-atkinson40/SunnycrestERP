export interface PaymentApplication {
  id: string;
  payment_id: string;
  bill_id: string;
  bill_number: string | null;
  amount_applied: number;
  created_at: string;
}

export interface PaymentApplicationCreate {
  bill_id: string;
  amount_applied: number;
}

export interface VendorPayment {
  id: string;
  company_id: string;
  vendor_id: string;
  vendor_name: string | null;
  payment_date: string;
  total_amount: number;
  payment_method: string;
  reference_number: string | null;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  applications: PaymentApplication[];
}

export interface VendorPaymentListItem {
  id: string;
  vendor_id: string;
  vendor_name: string | null;
  payment_date: string;
  total_amount: number;
  payment_method: string;
  reference_number: string | null;
  created_at: string;
}

export interface VendorPaymentCreate {
  vendor_id: string;
  payment_date: string;
  total_amount: number;
  payment_method: string;
  reference_number?: string;
  notes?: string;
  applications: PaymentApplicationCreate[];
}

export interface PaginatedVendorPayments {
  items: VendorPaymentListItem[];
  total: number;
  page: number;
  per_page: number;
}

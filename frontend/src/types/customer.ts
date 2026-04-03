export interface CustomerContact {
  id: string;
  customer_id: string;
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  created_at: string;
}

export interface CustomerContactCreate {
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
}

export interface CustomerContactUpdate {
  name?: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
}

export interface CustomerNote {
  id: string;
  customer_id: string;
  note_type: string;
  content: string;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface CustomerNoteCreate {
  note_type?: string;
  content: string;
}

export interface Customer {
  id: string;
  company_id: string;
  name: string;
  account_number: string | null;
  email: string | null;
  phone: string | null;
  fax: string | null;
  contact_name: string | null;
  website: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  country: string | null;
  billing_address_line1: string | null;
  billing_address_line2: string | null;
  billing_city: string | null;
  billing_state: string | null;
  billing_zip: string | null;
  billing_country: string | null;
  credit_limit: number | null;
  payment_terms: string | null;
  account_status: string;
  current_balance: number;
  credit_balance?: number | null;
  tax_exempt: boolean;
  tax_id: string | null;
  notes: string | null;
  sage_customer_id: string | null;
  master_company_id: string | null;
  customer_type: string | null;
  classification_confidence: number | null;
  classification_method: string | null;
  classification_reasoning: string | null;
  // Funeral home order preferences
  prefers_placer: boolean;
  preferred_confirmation_method: string | null;
  invoice_delivery_preference: string;
  is_active: boolean;
  setup_complete: boolean;
  created_at: string;
  updated_at: string;
  contacts: CustomerContact[];
  recent_notes: CustomerNote[];
}

export interface CustomerListItem {
  id: string;
  name: string;
  account_number: string | null;
  email: string | null;
  phone: string | null;
  contact_name: string | null;
  city: string | null;
  state: string | null;
  account_status: string;
  current_balance: number;
  credit_limit: number | null;
  payment_terms: string | null;
  customer_type: string | null;
  billing_profile: string | null;
  is_active: boolean;
  setup_complete: boolean;
  created_at: string;
  // Classification metadata (added in r19)
  classification_confidence: number | null;
  classification_method: string | null;
  classification_reasoning: string | null;
  is_extension_hidden: boolean;
  // Funeral home order preferences (r25)
  prefers_placer: boolean;
  preferred_confirmation_method: string | null;
  invoice_delivery_preference: string;
  display_name?: string;
}

// ---------------------------------------------------------------------------
// Cemetery types
// ---------------------------------------------------------------------------

export interface Cemetery {
  id: string;
  company_id: string;
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  county: string | null;
  zip_code: string | null;
  phone: string | null;
  contact_name: string | null;
  cemetery_provides_lowering_device: boolean;
  cemetery_provides_grass: boolean;
  cemetery_provides_tent: boolean;
  cemetery_provides_chairs: boolean;
  equipment_note: string | null;
  access_notes: string | null;
  // New fields from r20_cemetery_experience
  customer_id: string | null;
  latitude: number | null;
  longitude: number | null;
  tax_county_confirmed: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CemeteryCreate {
  name: string;
  state?: string;
  county?: string;
  city?: string;
  address?: string;
  zip_code?: string;
  phone?: string;
  contact_name?: string;
  cemetery_provides_lowering_device?: boolean;
  cemetery_provides_grass?: boolean;
  cemetery_provides_tent?: boolean;
  cemetery_provides_chairs?: boolean;
  access_notes?: string;
}

export interface CemeteryUpdate extends Partial<CemeteryCreate> {
  tax_county_confirmed?: boolean;
}

export interface PaginatedCemeteries {
  items: Cemetery[];
  total: number;
  page: number;
  per_page: number;
}

export interface EquipmentPrefill {
  can_provide: string[];
  cemetery_provides: string[];
  equipment_note: string;
  suggestion_label: string;
  nothing_needed: boolean;
}

export interface CemeteryShortlistItem {
  cemetery_id: string;
  cemetery_name: string;
  city?: string | null;
  state?: string | null;
  county?: string | null;
  order_count: number;
  last_order_date: string | null;
}

export interface CustomerCreate {
  name: string;
  account_number?: string;
  email?: string;
  phone?: string;
  fax?: string;
  contact_name?: string;
  website?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  credit_limit?: number;
  payment_terms?: string;
  account_status?: string;
  tax_exempt?: boolean;
  notes?: string;
  sage_customer_id?: string;
  customer_type?: string;
}

export interface CustomerUpdate extends Partial<CustomerCreate> {
  is_active?: boolean;
  billing_address_line1?: string;
  billing_address_line2?: string;
  billing_city?: string;
  billing_state?: string;
  billing_zip?: string;
  billing_country?: string;
  tax_id?: string;
  address_line2?: string;
  // Funeral home order preferences
  prefers_placer?: boolean;
  preferred_confirmation_method?: string | null;
  invoice_delivery_preference?: string;
}

export interface PaginatedCustomers {
  items: CustomerListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface CustomerStats {
  total_customers: number;
  active_customers: number;
  on_hold: number;
  suspended: number;
  total_outstanding: number;
  over_limit_count: number;
}

export interface CreditCheckResult {
  allowed: boolean;
  credit_limit: number | null;
  current_balance: number;
  available_credit: number | null;
  requested_amount: number;
}

export interface BalanceAdjustment {
  id: string;
  customer_id: string;
  adjustment_type: string;
  amount: number;
  description: string | null;
  reference_number: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface BalanceAdjustmentCreate {
  adjustment_type: "charge" | "payment";
  amount: number;
  description?: string;
  reference_number?: string;
}

export interface PaginatedBalanceAdjustments {
  items: BalanceAdjustment[];
  total: number;
  page: number;
  per_page: number;
}

export interface CustomerImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}

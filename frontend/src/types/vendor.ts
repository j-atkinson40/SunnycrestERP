export interface VendorContact {
  id: string;
  vendor_id: string;
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  created_at: string;
}

export interface VendorContactCreate {
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
}

export interface VendorContactUpdate {
  name?: string;
  title?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
}

export interface VendorNote {
  id: string;
  vendor_id: string;
  note_type: string;
  content: string;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface VendorNoteCreate {
  note_type?: string;
  content: string;
}

export interface Vendor {
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
  payment_terms: string | null;
  vendor_status: string;
  lead_time_days: number | null;
  minimum_order: number | null;
  tax_id: string | null;
  notes: string | null;
  sage_vendor_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  contacts: VendorContact[];
  recent_notes: VendorNote[];
}

export interface VendorListItem {
  id: string;
  name: string;
  account_number: string | null;
  email: string | null;
  phone: string | null;
  contact_name: string | null;
  city: string | null;
  state: string | null;
  vendor_status: string;
  payment_terms: string | null;
  lead_time_days: number | null;
  minimum_order: number | null;
  is_active: boolean;
  created_at: string;
}

export interface VendorCreate {
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
  payment_terms?: string;
  vendor_status?: string;
  lead_time_days?: number;
  minimum_order?: number;
  tax_id?: string;
  notes?: string;
  sage_vendor_id?: string;
}

export interface VendorUpdate extends Partial<VendorCreate> {
  is_active?: boolean;
  address_line2?: string;
}

export interface PaginatedVendors {
  items: VendorListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface VendorStats {
  total_vendors: number;
  active_vendors: number;
  on_hold: number;
}

export interface VendorImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}

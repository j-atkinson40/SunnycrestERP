// ── Cremation ────────────────────────────────────────────────

export type CremationAuthStatus = 'not_applicable' | 'pending' | 'signed' | 'received';
export type RemainsDisposition = 'family_pickup' | 'delivery' | 'interment' | 'scattering' | 'pending';

export interface CremationStatus {
  cremation_authorization_status: CremationAuthStatus | null;
  cremation_authorization_signed_at: string | null;
  cremation_authorization_signed_by: string | null;
  cremation_scheduled_date: string | null;
  cremation_completed_date: string | null;
  remains_disposition: RemainsDisposition | null;
  remains_released_at: string | null;
  remains_released_to: string | null;
  cremation_provider: string | null;
  cremation_provider_case_number: string | null;
}

// ── Case ──────────────────────────────────────────────────────

export interface FHCase {
  id: string;
  company_id: string;
  case_number: string;
  status: FHCaseStatus;
  deceased_first_name: string;
  deceased_middle_name?: string;
  deceased_last_name: string;
  deceased_date_of_birth?: string;
  deceased_date_of_death: string;
  deceased_place_of_death?: string;
  deceased_place_of_death_name?: string;
  deceased_place_of_death_city?: string;
  deceased_place_of_death_state?: string;
  deceased_gender?: string;
  deceased_age_at_death?: number;
  deceased_ssn_last_four?: string;
  deceased_veteran: boolean;
  disposition_type?: string;
  disposition_date?: string;
  disposition_location?: string;
  disposition_city?: string;
  disposition_state?: string;
  service_type?: string;
  service_date?: string;
  service_time?: string;
  service_location?: string;
  visitation_date?: string;
  visitation_start_time?: string;
  visitation_end_time?: string;
  visitation_location?: string;
  primary_contact_id?: string;
  assigned_director_id?: string;
  referred_by?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  closed_at?: string;
  // Joined data
  primary_contact?: FHCaseContact;
  assigned_director_name?: string;
  vault_order?: FHVaultOrder;
  obituary?: FHObituary;
  invoice?: FHInvoice;
  days_since_opened?: number;
  // Cremation fields
  cremation_authorization_status?: CremationAuthStatus | null;
  cremation_authorization_signed_at?: string | null;
  cremation_authorization_signed_by?: string | null;
  cremation_scheduled_date?: string | null;
  cremation_completed_date?: string | null;
  remains_disposition?: RemainsDisposition | null;
  remains_released_at?: string | null;
  remains_released_to?: string | null;
  cremation_provider?: string | null;
  cremation_provider_case_number?: string | null;
}

export type FHCaseStatus =
  | "first_call"
  | "in_progress"
  | "services_scheduled"
  | "services_complete"
  | "pending_invoice"
  | "invoiced"
  | "closed"
  | "cancelled";

export const CASE_STATUS_LABELS: Record<FHCaseStatus, string> = {
  first_call: "First Call",
  in_progress: "In Progress",
  services_scheduled: "Services Scheduled",
  services_complete: "Services Complete",
  pending_invoice: "Pending Invoice",
  invoiced: "Invoiced",
  closed: "Closed",
  cancelled: "Cancelled",
};

export const CASE_STATUS_COLORS: Record<FHCaseStatus, string> = {
  first_call: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  services_scheduled: "bg-purple-100 text-purple-800",
  services_complete: "bg-green-100 text-green-800",
  pending_invoice: "bg-orange-100 text-orange-800",
  invoiced: "bg-indigo-100 text-indigo-800",
  closed: "bg-gray-100 text-gray-800",
  cancelled: "bg-red-100 text-red-800",
};

export const CASE_STATUS_FLOW: FHCaseStatus[] = [
  "first_call",
  "in_progress",
  "services_scheduled",
  "services_complete",
  "pending_invoice",
  "invoiced",
  "closed",
];

// ── Contact ───────────────────────────────────────────────────

export interface FHCaseContact {
  id: string;
  case_id: string;
  contact_type: string;
  first_name: string;
  last_name: string;
  relationship_to_deceased?: string;
  phone_primary?: string;
  phone_secondary?: string;
  email?: string;
  address?: string;
  city?: string;
  state?: string;
  zip?: string;
  is_primary: boolean;
  receives_portal_access: boolean;
  portal_invite_sent_at?: string;
  portal_last_login_at?: string;
  notes?: string;
}

// ── Service Line Item ─────────────────────────────────────────

export interface FHServiceItem {
  id: string;
  case_id: string;
  service_category: string;
  service_code?: string;
  service_name: string;
  description?: string;
  quantity: number;
  unit_price: number;
  extended_price: number;
  is_required: boolean;
  is_selected: boolean;
  is_package_item: boolean;
  package_id?: string;
  notes?: string;
  sort_order: number;
}

// ── Price List / GPL ──────────────────────────────────────────

export interface FHPriceListItem {
  id: string;
  item_code: string;
  category: string;
  item_name: string;
  description?: string;
  unit_price: number;
  price_type: string;
  is_ftc_required_disclosure: boolean;
  ftc_disclosure_text?: string;
  is_required_by_law: boolean;
  is_active: boolean;
  effective_date?: string;
  sort_order: number;
}

export interface FHPriceListVersion {
  id: string;
  version_number: number;
  effective_date: string;
  notes?: string;
  created_by?: string;
  pdf_url?: string;
  created_at: string;
}

// ── Vault Order ───────────────────────────────────────────────

export interface FHVaultOrder {
  id: string;
  case_id: string;
  manufacturer_tenant_id: string;
  order_number?: string;
  status: string;
  vault_product_id?: string;
  vault_product_name?: string;
  vault_product_sku?: string;
  quantity: number;
  unit_price?: number;
  requested_delivery_date?: string;
  confirmed_delivery_date?: string;
  delivery_address?: string;
  delivery_contact_name?: string;
  delivery_contact_phone?: string;
  special_instructions?: string;
  manufacturer_order_id?: string;
  delivery_status_last_updated_at?: string;
  notes?: string;
  created_at: string;
}

export const VAULT_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  confirmed: "Confirmed",
  in_production: "In Production",
  ready: "Ready",
  scheduled_for_delivery: "Scheduled",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export const VAULT_STATUS_FLOW = [
  "draft",
  "submitted",
  "confirmed",
  "in_production",
  "ready",
  "scheduled_for_delivery",
  "delivered",
];

// ── Obituary ──────────────────────────────────────────────────

export interface FHObituary {
  id: string;
  case_id: string;
  content?: string;
  status: string;
  generated_by?: string;
  ai_prompt_used?: string;
  family_approved_at?: string;
  family_approved_by_contact_id?: string;
  family_approval_notes?: string;
  version: number;
  published_locations?: string[];
  created_at: string;
}

// ── Invoice ───────────────────────────────────────────────────

export interface FHInvoice {
  id: string;
  case_id: string;
  invoice_number: string;
  status: string;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  balance_due: number;
  due_date?: string;
  sent_at?: string;
  sent_to_email?: string;
  notes?: string;
}

// ── Payment ───────────────────────────────────────────────────

export interface FHPayment {
  id: string;
  case_id: string;
  invoice_id: string;
  payment_date: string;
  amount: number;
  payment_method: string;
  reference_number?: string;
  received_by?: string;
  notes?: string;
}

// ── Document ──────────────────────────────────────────────────

export interface FHDocument {
  id: string;
  case_id: string;
  document_type: string;
  document_name: string;
  file_url: string;
  uploaded_by?: string;
  notes?: string;
  created_at: string;
}

export const DOCUMENT_TYPES = [
  "death_certificate",
  "burial_permit",
  "cremation_authorization",
  "embalming_authorization",
  "disposition_authorization",
  "insurance_assignment",
  "pre_need_contract",
  "signed_contract",
  "other",
] as const;

export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  death_certificate: "Death Certificate",
  burial_permit: "Burial Permit",
  cremation_authorization: "Cremation Authorization",
  embalming_authorization: "Embalming Authorization",
  disposition_authorization: "Disposition Authorization",
  insurance_assignment: "Insurance Assignment",
  pre_need_contract: "Pre-Need Contract",
  signed_contract: "Signed Contract",
  other: "Other",
};

// ── Activity ──────────────────────────────────────────────────

export interface FHCaseActivity {
  id: string;
  case_id: string;
  activity_type: string;
  description: string;
  performed_by?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

// ── Manufacturer Relationship ─────────────────────────────────

export interface FHManufacturerRelationship {
  id: string;
  funeral_home_tenant_id: string;
  manufacturer_tenant_id: string;
  account_number?: string;
  default_delivery_instructions?: string;
  is_primary: boolean;
  negotiated_price_tier?: string;
  status: string;
  manufacturer_name?: string;
}

// ── Vault Product (from manufacturer catalog) ─────────────────

export interface FHVaultProduct {
  id: string;
  product_name: string;
  sku: string;
  description?: string;
  unit_price: number;
  image_url?: string;
}

// ── Portal Data ───────────────────────────────────────────────

export interface FHPortalData {
  deceased: { first_name: string; last_name: string; date_of_death: string; photo_url?: string; date_of_birth?: string };
  service?: { date?: string; time?: string; location?: string; type?: string };
  visitation?: { date?: string; start_time?: string; end_time?: string; location?: string };
  obituary?: { content?: string; status: string; can_approve: boolean };
  vault_status?: { status: string; label: string };
  invoice?: { total_amount: number; amount_paid: number; balance_due: number };
  documents: FHDocument[];
  funeral_home: { name: string };
  // Cremation timeline (present only for cremation cases)
  cremation?: CremationStatus;
  // Optional extension-driven sections
  flowers?: { provider_url: string; message?: string };
  livestream_url?: string;
  merchandise?: { items: { id: string; name: string; price: number; image_url?: string }[] };
}

// ── FTC Compliance ────────────────────────────────────────────

export interface FTCComplianceReport {
  all_required_items_present: boolean;
  missing_items: string[];
  items_missing_prices: string[];
  items_missing_disclosure: string[];
  gpl_age_days: number;
  gpl_overdue: boolean;
  compliance_score: number;
  issues: string[];
  total_cases: number;
  cases_missing_gpl_record: number;
  last_review_date?: string;
  gpl_versions: FHPriceListVersion[];
}

// ── Dashboard ─────────────────────────────────────────────────

export interface FHDashboardData {
  cases_by_status: Record<string, FHCase[]>;
  needs_attention: {
    needs_arrangement: FHCase[];
    vault_not_ordered: FHCase[];
    vault_at_risk: FHCase[];
    obituary_pending: FHCase[];
    invoice_not_sent: FHCase[];
    outstanding_balance: FHCase[];
    awaiting_cremation_auth: FHCase[];
  };
  today_schedule: { services: FHCase[]; visitations: FHCase[]; deliveries: FHVaultOrder[] };
  recent_activity: FHCaseActivity[];
  compliance_score: number;
}

// ── Director (user summary) ───────────────────────────────────

export interface FHDirector {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
}

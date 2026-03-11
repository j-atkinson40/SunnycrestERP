export interface Company {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  address_street: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  phone: string | null;
  email: string | null;
  timezone: string | null;
  logo_url: string | null;
  created_at: string;
}

export interface CompanyUpdate {
  name?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
  phone?: string;
  email?: string;
  timezone?: string;
  logo_url?: string;
}

export interface CompanyRegisterRequest {
  company_name: string;
  company_slug: string;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface CompanyRegisterResponse {
  company: Company;
  user: import("./auth").User;
}

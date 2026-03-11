export interface Company {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
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

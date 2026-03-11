export interface EmployeeProfile {
  id: string;
  user_id: string;
  phone: string | null;
  position: string | null;
  department: string | null;
  hire_date: string | null;
  address_street: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeProfileUpdate {
  phone?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
}

export interface EmployeeProfileAdminUpdate extends EmployeeProfileUpdate {
  position?: string;
  department?: string;
  hire_date?: string;
  notes?: string;
}

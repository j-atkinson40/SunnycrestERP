import type { User } from "./auth";

export interface UserCreate {
  first_name: string;
  last_name: string;
  track?: string;
  email?: string;
  password?: string;
  username?: string;
  pin?: string;
  console_access?: string[];
  idle_timeout_minutes?: number;
  role_id?: string;
}

export interface UserUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
  role_id?: string;
  is_active?: boolean;
  username?: string;
  console_access?: string[];
  idle_timeout_minutes?: number;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  per_page: number;
}

export interface BulkCreateResponse {
  created: User[];
  errors: { index: number; identifier: string; detail: string }[];
}

import type { User } from "./auth";

export interface UserCreate {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role_id: string;
}

export interface UserUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
  role_id?: string;
  is_active?: boolean;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  per_page: number;
}

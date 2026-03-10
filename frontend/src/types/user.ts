import type { Role, User } from "./auth";

export interface UserCreate {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: Role;
}

export interface UserUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: Role;
  is_active?: boolean;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  per_page: number;
}

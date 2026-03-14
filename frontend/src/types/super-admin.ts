export interface TenantOverview {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  user_count: number;
  created_at: string;
  subscription_status: string | null;
  plan_name: string | null;
  last_sync_at: string | null;
  sync_status: "green" | "yellow" | "red" | null;
}

export interface SystemHealth {
  total_tenants: number;
  active_tenants: number;
  inactive_tenants: number;
  total_users: number;
  active_users: number;
  total_jobs_24h: number;
  failed_jobs_24h: number;
  redis_connected: boolean;
  db_connected: boolean;
}

export interface SuperDashboard {
  system_health: SystemHealth;
  tenants: TenantOverview[];
  billing_mrr: string;
  billing_active: number;
  billing_past_due: number;
}

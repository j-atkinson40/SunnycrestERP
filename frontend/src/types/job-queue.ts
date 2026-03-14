export interface Job {
  id: string;
  company_id: string;
  job_type: string;
  payload: string | null;
  priority: number;
  status: "pending" | "running" | "completed" | "failed" | "dead";
  retry_count: number;
  max_retries: number;
  error_message: string | null;
  result: string | null;
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  created_by: string | null;
}

export interface QueueStats {
  pending: number;
  running: number;
  completed: number;
  failed: number;
  dead: number;
  redis_queue_depth: number;
  redis_dlq_size: number;
  redis_connected: boolean;
}

export interface SyncHealthTenant {
  company_id: string;
  company_name: string;
  status: "green" | "yellow" | "red";
  last_sync_at: string | null;
  last_sync_type: string | null;
  last_sync_status: string | null;
  error_message: string | null;
  total_syncs_24h: number;
  failed_syncs_24h: number;
}

export interface SyncDashboard {
  tenants: SyncHealthTenant[];
  queue_stats: QueueStats;
}

export interface PaginatedJobs {
  items: Job[];
  total: number;
  page: number;
  per_page: number;
}

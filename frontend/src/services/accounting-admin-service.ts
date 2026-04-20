/**
 * Vault → Accounting admin API client — Phase V-1e.
 *
 * Thin axios wrapper around the `/api/v1/vault/accounting/*` endpoints
 * plus the existing agent-schedule + tax + statement-template + agent-
 * jobs endpoints used by the Accounting admin sub-tabs.
 *
 * Types reflect the backend Pydantic responses verbatim — keep in
 * lock-step with `backend/app/api/routes/vault_accounting.py`.
 */

import apiClient from "@/lib/api-client";

// ── Periods + Locks ──────────────────────────────────────────────────

export interface PeriodRow {
  id: string;
  period_month: number;
  period_year: number;
  display_name: string;
  status: "open" | "closed" | string;
  closed_at: string | null;
  closed_by: string | null;
}

export interface PeriodListResponse {
  periods: PeriodRow[];
}

export interface PeriodAuditRow {
  id: string;
  action: "period_locked" | "period_unlocked" | string;
  entity_id: string | null;
  user_id: string | null;
  created_at: string;
  changes: {
    period_month?: number;
    period_year?: number;
    previous_status?: string;
    new_status?: string;
    display_name?: string;
  } | null;
}

export interface PeriodAuditResponse {
  events: PeriodAuditRow[];
}

export interface PendingCloseRow {
  job_id: string;
  period_month: number;
  period_year: number;
  display_name: string;
  completed_at: string | null;
  anomaly_count: number;
}

export interface PendingCloseResponse {
  pending: PendingCloseRow[];
}

// ── GL Classification Queue ──────────────────────────────────────────

export interface ClassificationRow {
  id: string;
  mapping_type: string;
  source_id: string | null;
  source_name: string;
  platform_category: string | null;
  confidence: number | null;
  reasoning: string | null;
  alternative: string | null;
  status: "pending" | "confirmed" | "rejected" | string;
  is_stale: boolean;
  created_at: string;
}

export interface ClassificationPendingResponse {
  pending: ClassificationRow[];
}

// ── COA Templates ────────────────────────────────────────────────────

export interface CoaTemplateRow {
  category_type: string; // revenue / ar / cogs / ap / expenses
  platform_category: string;
}

export interface CoaTemplateResponse {
  templates: CoaTemplateRow[];
}

// ── Agent schedules ──────────────────────────────────────────────────

export interface AgentScheduleRow {
  id: string;
  job_type: string;
  is_enabled: boolean;
  cron_expression: string | null;
  run_day_of_month: number | null;
  run_hour: number | null;
  timezone: string;
  auto_approve: boolean;
  notify_emails: string[];
  last_run_at: string | null;
  last_job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentScheduleUpdate {
  job_type: string;
  is_enabled: boolean;
  cron_expression?: string | null;
  run_day_of_month?: number | null;
  run_hour?: number | null;
  timezone?: string;
  auto_approve?: boolean;
  notify_emails?: string[];
}

export interface AgentJobListItem {
  id: string;
  job_type: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  dry_run: boolean;
  anomaly_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── Tax config ───────────────────────────────────────────────────────

export interface TaxRate {
  id: string;
  rate_name: string;
  rate_percentage: number;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
  gl_account_id: string | null;
}

export interface TaxJurisdiction {
  id: string;
  jurisdiction_name: string;
  state: string;
  county: string;
  zip_codes: string[] | null;
  tax_rate_id: string;
  is_active: boolean;
}

// ── Statement templates ──────────────────────────────────────────────

export interface StatementTemplate {
  id: string;
  tenant_id: string | null;
  template_key: string;
  template_name: string;
  customer_type: string;
  is_default_for_type: boolean;
  sections: string[];
  logo_enabled: boolean;
  show_aging_summary: boolean;
  show_account_number: boolean;
  show_payment_instructions: boolean;
  remittance_address: string | null;
  payment_instructions: string | null;
}

// ── Service ──────────────────────────────────────────────────────────

export const accountingAdminService = {
  // Periods + Locks
  async listPeriods(year?: number): Promise<PeriodListResponse> {
    const params: Record<string, number> = {};
    if (year !== undefined) params.year = year;
    const { data } = await apiClient.get<PeriodListResponse>(
      "/vault/accounting/periods",
      { params },
    );
    return data;
  },

  async lockPeriod(
    id: string,
  ): Promise<{ status: string; period_id: string; closed_at: string }> {
    const { data } = await apiClient.post(
      `/vault/accounting/periods/${id}/lock`,
    );
    return data;
  },

  async unlockPeriod(
    id: string,
  ): Promise<{ status: string; period_id: string }> {
    const { data } = await apiClient.post(
      `/vault/accounting/periods/${id}/unlock`,
    );
    return data;
  },

  async listPeriodAudit(limit: number = 50): Promise<PeriodAuditResponse> {
    const { data } = await apiClient.get<PeriodAuditResponse>(
      "/vault/accounting/period-audit",
      { params: { limit } },
    );
    return data;
  },

  async listPendingClose(): Promise<PendingCloseResponse> {
    const { data } = await apiClient.get<PendingCloseResponse>(
      "/vault/accounting/pending-close",
    );
    return data;
  },

  // Classification
  async listPendingClassifications(
    limit: number = 50,
    mappingType?: string,
  ): Promise<ClassificationPendingResponse> {
    const params: Record<string, string | number> = { limit };
    if (mappingType) params.mapping_type = mappingType;
    const { data } = await apiClient.get<ClassificationPendingResponse>(
      "/vault/accounting/classification/pending",
      { params },
    );
    return data;
  },

  async confirmClassification(
    id: string,
    platformCategory?: string,
  ): Promise<{ status: string; id: string; platform_category: string }> {
    const body = platformCategory
      ? { platform_category: platformCategory }
      : {};
    const { data } = await apiClient.post(
      `/vault/accounting/classification/${id}/confirm`,
      body,
    );
    return data;
  },

  async rejectClassification(
    id: string,
  ): Promise<{ status: string; id: string }> {
    const { data } = await apiClient.post(
      `/vault/accounting/classification/${id}/reject`,
    );
    return data;
  },

  // COA Templates
  async listCoaTemplates(): Promise<CoaTemplateResponse> {
    const { data } = await apiClient.get<CoaTemplateResponse>(
      "/vault/accounting/coa-templates",
    );
    return data;
  },

  // Agent schedules (tenant-wide list)
  async listAgentSchedules(): Promise<AgentScheduleRow[]> {
    const { data } = await apiClient.get<AgentScheduleRow[]>(
      "/agents/schedules",
    );
    return data;
  },

  async upsertAgentSchedule(
    body: AgentScheduleUpdate,
  ): Promise<AgentScheduleRow> {
    const { data } = await apiClient.post<AgentScheduleRow>(
      "/agents/schedules",
      body,
    );
    return data;
  },

  async toggleAgentSchedule(
    jobType: string,
  ): Promise<{ job_type: string; is_enabled: boolean }> {
    const { data } = await apiClient.post(
      `/agents/schedules/${jobType}/toggle`,
    );
    return data;
  },

  // Agent jobs (tenant-wide tail)
  async listRecentJobs(limit: number = 20): Promise<AgentJobListItem[]> {
    const { data } = await apiClient.get<AgentJobListItem[]>("/agents/jobs", {
      params: { limit },
    });
    return data;
  },

  // Tax config (delegates to existing /tax/* endpoints)
  async listTaxRates(): Promise<TaxRate[]> {
    const { data } = await apiClient.get<TaxRate[]>("/tax/rates");
    return data;
  },

  async listTaxJurisdictions(): Promise<TaxJurisdiction[]> {
    const { data } = await apiClient.get<TaxJurisdiction[]>(
      "/tax/jurisdictions",
    );
    return data;
  },

  // Statement templates
  async listStatementTemplates(): Promise<StatementTemplate[]> {
    const { data } =
      await apiClient.get<StatementTemplate[]>("/statements/templates");
    return data;
  },
};

import apiClient from "@/lib/api-client";

// ── Types ──────────────────────────────────────────────────────────────

export interface DocumentTemplateListItem {
  id: string;
  company_id: string | null;
  template_key: string;
  document_type: string;
  output_format: "pdf" | "html" | "text";
  description: string | null;
  supports_variants: boolean;
  is_active: boolean;
  current_version_number: number | null;
  current_version_activated_at: string | null;
  scope: "platform" | "tenant";
  has_draft?: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentTemplateVersion {
  id: string;
  template_id: string;
  version_number: number;
  status: string;
  body_template: string;
  subject_template: string | null;
  variable_schema: Record<string, unknown> | null;
  sample_context: Record<string, unknown> | null;
  css_variables: Record<string, unknown> | null;
  changelog: string | null;
  activated_at: string | null;
  activated_by_user_id: string | null;
  created_at: string;
}

export interface DocumentTemplateVersionSummary {
  id: string;
  version_number: number;
  status: string;
  changelog: string | null;
  activated_at: string | null;
  created_at: string;
}

export interface DocumentTemplateDetail {
  id: string;
  company_id: string | null;
  template_key: string;
  document_type: string;
  output_format: "pdf" | "html" | "text";
  description: string | null;
  supports_variants: boolean;
  is_active: boolean;
  scope: "platform" | "tenant";
  created_at: string;
  updated_at: string;
  current_version: DocumentTemplateVersion | null;
  version_summaries: DocumentTemplateVersionSummary[];
}

export interface DocumentTemplateListResponse {
  items: DocumentTemplateListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentLogItem {
  id: string;
  company_id: string;
  document_type: string;
  title: string;
  status: string;
  file_size_bytes: number | null;
  template_key: string | null;
  template_version: number | null;
  entity_type: string | null;
  entity_id: string | null;
  intelligence_execution_id: string | null;
  caller_workflow_run_id: string | null;
  caller_module: string | null;
  rendered_at: string | null;
  created_at: string;
}

export interface DocumentListItem {
  id: string;
  company_id: string;
  document_type: string;
  title: string;
  description: string | null;
  status: string;
  storage_key: string;
  mime_type: string;
  file_size_bytes: number | null;
  template_key: string | null;
  template_version: number | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  storage_key: string;
  mime_type: string;
  file_size_bytes: number | null;
  rendered_at: string;
  rendering_context_hash: string | null;
  render_reason: string | null;
  is_current: boolean;
}

export interface DocumentDetail extends DocumentListItem {
  // Linkage fields
  sales_order_id: string | null;
  fh_case_id: string | null;
  disinterment_case_id: string | null;
  invoice_id: string | null;
  customer_statement_id: string | null;
  price_list_version_id: string | null;
  safety_program_generation_id: string | null;
  caller_module: string | null;
  caller_workflow_run_id: string | null;
  caller_workflow_step_id: string | null;
  intelligence_execution_id: string | null;
  rendered_at: string | null;
  rendering_duration_ms: number | null;
  rendering_context_hash: string | null;
  versions: DocumentVersion[];
}

// ── Editing + audit (Phase D-3) ────────────────────────────────────────

export interface TemplateEditPermission {
  can_edit: boolean;
  reason: string | null;
  requires_super_admin: boolean;
  requires_confirmation_text: boolean;
  can_fork: boolean;
}

export interface ValidationIssue {
  severity: "error" | "warning";
  issue_type: string;
  message: string;
  variable_name: string | null;
}

export interface TemplateAuditLogEntry {
  id: string;
  template_id: string;
  version_id: string | null;
  action: string;
  actor_user_id: string | null;
  actor_email: string | null;
  changelog_summary: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

export interface TestRenderResponse {
  output_format: "pdf" | "html" | "text";
  rendered_content: string | null;
  rendered_subject: string | null;
  document_id: string | null;
  download_url: string | null;
  errors: string[];
}

// ── Filters ────────────────────────────────────────────────────────────

export interface TemplateListFilters {
  document_type?: string;
  output_format?: string;
  scope?: "platform" | "tenant" | "both";
  search?: string;
  status?: "active" | "all";
  limit?: number;
  offset?: number;
}

export interface DocumentLogFilters {
  document_type?: string;
  template_key?: string;
  status?: string;
  entity_type?: string;
  intelligence_generated?: boolean;
  include_test_renders?: boolean;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

// ── Service ────────────────────────────────────────────────────────────

export const documentsV2Service = {
  // Templates
  async listTemplates(
    filters: TemplateListFilters = {}
  ): Promise<DocumentTemplateListResponse> {
    const { data } = await apiClient.get("/documents-v2/admin/templates", {
      params: filters,
    });
    return data;
  },

  async getTemplate(templateId: string): Promise<DocumentTemplateDetail> {
    const { data } = await apiClient.get(
      `/documents-v2/admin/templates/${templateId}`
    );
    return data;
  },

  async getTemplateVersion(
    templateId: string,
    versionId: string
  ): Promise<DocumentTemplateVersion> {
    const { data } = await apiClient.get(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}`
    );
    return data;
  },

  // Documents (D-2 log endpoint)
  async listDocumentLog(
    filters: DocumentLogFilters = {}
  ): Promise<DocumentLogItem[]> {
    const { data } = await apiClient.get("/documents-v2/log", {
      params: filters,
    });
    return data;
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    const { data } = await apiClient.get(`/documents-v2/${documentId}`);
    return data;
  },

  getDownloadUrl(documentId: string): string {
    return `/api/v1/documents-v2/${documentId}/download`;
  },

  getVersionDownloadUrl(documentId: string, versionId: string): string {
    return `/api/v1/documents-v2/${documentId}/versions/${versionId}/download`;
  },

  async regenerate(
    documentId: string,
    reason: string,
    contextOverride?: Record<string, unknown>
  ): Promise<void> {
    await apiClient.post(`/documents-v2/${documentId}/regenerate`, {
      reason,
      context_override: contextOverride,
    });
  },

  // ── Phase D-3 editing ────────────────────────────────────────────────

  async getEditPermission(
    templateId: string
  ): Promise<TemplateEditPermission> {
    const { data } = await apiClient.get(
      `/documents-v2/admin/templates/${templateId}/edit-permission`
    );
    return data;
  },

  async createDraft(
    templateId: string,
    payload: { base_version_id?: string; changelog?: string } = {}
  ): Promise<DocumentTemplateVersion> {
    const { data } = await apiClient.post(
      `/documents-v2/admin/templates/${templateId}/versions/draft`,
      payload
    );
    return data;
  },

  async updateDraft(
    templateId: string,
    versionId: string,
    patch: Partial<{
      body_template: string;
      subject_template: string | null;
      variable_schema: Record<string, unknown> | null;
      css_variables: Record<string, unknown> | null;
      changelog: string | null;
    }>
  ): Promise<DocumentTemplateVersion> {
    const { data } = await apiClient.patch(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}`,
      patch
    );
    return data;
  },

  async deleteDraft(
    templateId: string,
    versionId: string
  ): Promise<void> {
    await apiClient.delete(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}`
    );
  },

  async activateVersion(
    templateId: string,
    versionId: string,
    payload: { changelog: string; confirmation_text?: string }
  ): Promise<DocumentTemplateVersion> {
    const { data } = await apiClient.post(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/activate`,
      payload
    );
    return data;
  },

  async rollbackVersion(
    templateId: string,
    versionId: string,
    payload: { changelog: string; confirmation_text?: string }
  ): Promise<DocumentTemplateVersion> {
    const { data } = await apiClient.post(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/rollback`,
      payload
    );
    return data;
  },

  async forkToTenant(
    templateId: string,
    targetCompanyId: string
  ): Promise<DocumentTemplateDetail> {
    const { data } = await apiClient.post(
      `/documents-v2/admin/templates/${templateId}/fork-to-tenant`,
      { target_company_id: targetCompanyId }
    );
    return data;
  },

  async testRender(
    templateId: string,
    versionId: string,
    context: Record<string, unknown>
  ): Promise<TestRenderResponse> {
    const { data } = await apiClient.post(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/test-render`,
      { context }
    );
    return data;
  },

  async listAudit(
    templateId: string,
    opts: { limit?: number; offset?: number } = {}
  ): Promise<TemplateAuditLogEntry[]> {
    const { data } = await apiClient.get(
      `/documents-v2/admin/templates/${templateId}/audit`,
      { params: opts }
    );
    return data;
  },

  // ── Phase D-6: cross-tenant sharing ─────────────────────────────────

  async createShare(
    documentId: string,
    payload: { target_company_id: string; reason?: string }
  ): Promise<DocumentShare> {
    const { data } = await apiClient.post(
      `/documents-v2/${documentId}/shares`,
      payload
    );
    return data;
  },

  async listShares(
    documentId: string,
    includeRevoked = false
  ): Promise<DocumentShare[]> {
    const { data } = await apiClient.get(
      `/documents-v2/${documentId}/shares`,
      { params: { include_revoked: includeRevoked } }
    );
    return data;
  },

  async revokeShare(
    shareId: string,
    revokeReason?: string
  ): Promise<DocumentShare> {
    const { data } = await apiClient.post(
      `/documents-v2/shares/${shareId}/revoke`,
      { revoke_reason: revokeReason }
    );
    return data;
  },

  async listShareEvents(shareId: string): Promise<DocumentShareEvent[]> {
    const { data } = await apiClient.get(
      `/documents-v2/shares/${shareId}/events`
    );
    return data;
  },

  async listInbox(
    filters: {
      document_type?: string;
      include_revoked?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<InboxItem[]> {
    const { data } = await apiClient.get("/documents-v2/inbox", {
      params: filters,
    });
    return data;
  },

  // Phase D-8: per-user inbox read tracking.
  async markShareRead(shareId: string): Promise<{ marked_count: number }> {
    const { data } = await apiClient.post(
      `/documents-v2/shares/${shareId}/mark-read`
    );
    return data;
  },

  async markAllInboxRead(): Promise<{ marked_count: number }> {
    const { data } = await apiClient.post(
      "/documents-v2/inbox/mark-all-read"
    );
    return data;
  },

  // ── Phase D-7: deliveries ─────────────────────────────────────────

  async listDeliveries(
    filters: {
      channel?: string;
      status?: string;
      date_from?: string;
      date_to?: string;
      document_id?: string;
      template_key?: string;
      recipient_search?: string;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<DeliveryListItem[]> {
    const { data } = await apiClient.get("/documents-v2/deliveries", {
      params: filters,
    });
    return data;
  },

  async getDelivery(deliveryId: string): Promise<DeliveryDetail> {
    const { data } = await apiClient.get(
      `/documents-v2/deliveries/${deliveryId}`
    );
    return data;
  },

  async resendDelivery(deliveryId: string): Promise<DeliveryDetail> {
    const { data } = await apiClient.post(
      `/documents-v2/deliveries/${deliveryId}/resend`
    );
    return data;
  },
};

// ── Phase D-6 types ────────────────────────────────────────────────

export interface DocumentShare {
  id: string;
  document_id: string;
  owner_company_id: string;
  target_company_id: string;
  permission: string;
  reason: string | null;
  granted_by_user_id: string | null;
  granted_at: string;
  revoked_by_user_id: string | null;
  revoked_at: string | null;
  revoke_reason: string | null;
  source_module: string | null;
}

export interface DocumentShareEvent {
  id: string;
  share_id: string;
  document_id: string | null;
  event_type: string;
  actor_user_id: string | null;
  actor_company_id: string | null;
  ip_address: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

export interface InboxItem {
  share_id: string;
  document_id: string;
  document_type: string;
  document_title: string;
  document_status: string;
  owner_company_id: string;
  owner_company_name: string | null;
  granted_at: string;
  revoked_at: string | null;
  reason: string | null;
  source_module: string | null;
  // Phase D-8: per-user read state (scoped to the current user).
  is_read: boolean;
  read_at: string | null;
}

// ── Phase D-7: deliveries ──────────────────────────────────────────

export interface DeliveryListItem {
  id: string;
  company_id: string;
  document_id: string | null;
  channel: string;
  recipient_type: string;
  recipient_value: string;
  recipient_name: string | null;
  subject: string | null;
  template_key: string | null;
  status: string;
  provider: string | null;
  provider_message_id: string | null;
  retry_count: number;
  sent_at: string | null;
  failed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface DeliveryDetail extends DeliveryListItem {
  body_preview: string | null;
  provider_response: Record<string, unknown> | null;
  error_code: string | null;
  max_retries: number;
  scheduled_for: string | null;
  delivered_at: string | null;
  caller_module: string | null;
  caller_workflow_run_id: string | null;
  caller_workflow_step_id: string | null;
  caller_intelligence_execution_id: string | null;
  caller_signature_envelope_id: string | null;
  metadata_json: Record<string, unknown> | null;
  updated_at: string;
}

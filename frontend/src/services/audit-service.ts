import apiClient from "@/lib/api-client";
import type {
  AuditLogEntry,
  AuditLogFilters,
  PaginatedAuditLogs,
} from "@/types/audit";

export const auditService = {
  async getAuditLogs(
    page = 1,
    perPage = 50,
    filters?: AuditLogFilters
  ): Promise<PaginatedAuditLogs> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (filters?.user_id) params.set("user_id", filters.user_id);
    if (filters?.action) params.set("action", filters.action);
    if (filters?.entity_type) params.set("entity_type", filters.entity_type);
    if (filters?.entity_id) params.set("entity_id", filters.entity_id);
    if (filters?.date_from) params.set("date_from", filters.date_from);
    if (filters?.date_to) params.set("date_to", filters.date_to);

    const response = await apiClient.get<PaginatedAuditLogs>(
      `/audit-logs?${params.toString()}`
    );
    return response.data;
  },

  async getAuditLog(logId: string): Promise<AuditLogEntry> {
    const response = await apiClient.get<AuditLogEntry>(
      `/audit-logs/${logId}`
    );
    return response.data;
  },
};

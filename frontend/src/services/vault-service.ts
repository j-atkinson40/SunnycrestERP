/**
 * Vault Hub API client — V-1a + V-1b.
 *
 * Thin wrapper around the tenant-scoped `/api/v1/vault/*` endpoints
 * that back the Vault Hub. This file is distinct from the existing
 * single-purpose services (`vault-item-service` etc.) — those deal
 * with VaultItem data rows; this one deals with hub structure
 * (which services appear, which overview widgets are visible).
 */

import apiClient from "@/lib/api-client";

// ── /services — V-1a ────────────────────────────────────────────────

export interface VaultServiceEntry {
  service_key: string;
  display_name: string;
  icon: string;
  route_prefix: string;
  sort_order: number;
}

export interface VaultServicesResponse {
  services: VaultServiceEntry[];
}

// ── /overview/widgets — V-1b ───────────────────────────────────────

export interface VaultOverviewWidgetEntry {
  widget_id: string;
  service_key: string;
  display_name: string;
  default_size: string;
  default_position: number;
  is_available: boolean;
  unavailable_reason: string | null;
}

export interface VaultOverviewLayoutEntry {
  widget_id: string;
  position: number;
  size: string;
}

export interface VaultOverviewWidgetsResponse {
  widgets: VaultOverviewWidgetEntry[];
  default_layout: VaultOverviewLayoutEntry[];
}

// ── /activity/recent — V-1c ─────────────────────────────────────────

export interface VaultActivityItem {
  id: string;
  activity_type: string;
  title: string | null;
  body: string | null;
  is_system_generated: boolean;
  company_id: string;
  company_name: string;
  created_at: string;
  logged_by: string | null;
}

export interface VaultRecentActivityResponse {
  activities: VaultActivityItem[];
}

// ── Service ─────────────────────────────────────────────────────────

export const vaultService = {
  async getServices(): Promise<VaultServicesResponse> {
    const { data } = await apiClient.get<VaultServicesResponse>(
      "/vault/services",
    );
    return data;
  },

  async getOverviewWidgets(): Promise<VaultOverviewWidgetsResponse> {
    const { data } = await apiClient.get<VaultOverviewWidgetsResponse>(
      "/vault/overview/widgets",
    );
    return data;
  },

  async getRecentActivity(params?: {
    limit?: number;
    sinceDays?: number;
  }): Promise<VaultRecentActivityResponse> {
    const query: Record<string, number> = {};
    if (params?.limit) query.limit = params.limit;
    if (params?.sinceDays) query.since_days = params.sinceDays;
    const { data } = await apiClient.get<VaultRecentActivityResponse>(
      "/vault/activity/recent",
      { params: query },
    );
    return data;
  },
};

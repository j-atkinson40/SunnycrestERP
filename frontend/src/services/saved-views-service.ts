/**
 * Saved Views API client.
 *
 * Eight endpoints under /api/v1/saved-views. Mirrors
 * `backend/app/api/routes/saved_views.py`.
 *
 * No local cache. Every call hits the server. Caching here would
 * hide visibility / role / sharing changes made by other tabs or
 * users, and the execute endpoint is already inside the
 * 150ms-p50 / 500ms-p99 CI gate.
 */

import apiClient from "@/lib/api-client";
import type {
  EntityType,
  EntityTypeMetadata,
  SavedView,
  SavedViewConfig,
  SavedViewResult,
} from "@/types/saved-views";

// ── List / get / create / update / delete ───────────────────────

export async function listSavedViews(
  entityType?: EntityType,
): Promise<SavedView[]> {
  const params = entityType ? { entity_type: entityType } : undefined;
  const resp = await apiClient.get<SavedView[]>("/saved-views", { params });
  return resp.data;
}

export async function getSavedView(viewId: string): Promise<SavedView> {
  const resp = await apiClient.get<SavedView>(`/saved-views/${viewId}`);
  return resp.data;
}

export interface CreateSavedViewBody {
  title: string;
  description?: string | null;
  config: SavedViewConfig;
}

export async function createSavedView(
  body: CreateSavedViewBody,
): Promise<SavedView> {
  const resp = await apiClient.post<SavedView>("/saved-views", body);
  return resp.data;
}

export interface UpdateSavedViewBody {
  title?: string;
  description?: string | null;
  config?: SavedViewConfig;
}

export async function updateSavedView(
  viewId: string,
  body: UpdateSavedViewBody,
): Promise<SavedView> {
  const resp = await apiClient.patch<SavedView>(
    `/saved-views/${viewId}`,
    body,
  );
  return resp.data;
}

export async function deleteSavedView(viewId: string): Promise<void> {
  await apiClient.delete(`/saved-views/${viewId}`);
}

// ── Duplicate ────────────────────────────────────────────────────

export async function duplicateSavedView(
  viewId: string,
  newTitle: string,
): Promise<SavedView> {
  const resp = await apiClient.post<SavedView>(
    `/saved-views/${viewId}/duplicate`,
    { new_title: newTitle },
  );
  return resp.data;
}

// ── Execute ──────────────────────────────────────────────────────

export async function executeSavedView(
  viewId: string,
): Promise<SavedViewResult> {
  const resp = await apiClient.post<SavedViewResult>(
    `/saved-views/${viewId}/execute`,
  );
  return resp.data;
}

// ── Preview (follow-up 3) ────────────────────────────────────────

/**
 * Execute a transient config without saving — backs the builder's
 * live preview pane. Server caps rows at 100 regardless of caller
 * limit; caller derives `truncated` from `rows.length < total_count`.
 *
 * Accepts an optional AbortSignal so the preview pane can cancel
 * in-flight requests when the debounced config changes before the
 * previous response lands.
 */
export async function previewSavedView(
  config: SavedViewConfig,
  options?: { signal?: AbortSignal },
): Promise<SavedViewResult> {
  const resp = await apiClient.post<SavedViewResult>(
    "/saved-views/preview",
    { config },
    { signal: options?.signal },
  );
  return resp.data;
}

// ── Entity types ─────────────────────────────────────────────────

export async function listEntityTypes(): Promise<EntityTypeMetadata[]> {
  const resp = await apiClient.get<EntityTypeMetadata[]>(
    "/saved-views/entity-types",
  );
  return resp.data;
}

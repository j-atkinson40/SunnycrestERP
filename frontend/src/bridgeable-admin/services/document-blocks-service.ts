/**
 * Document blocks service — Phase D-10 + D-11 (June 2026).
 *
 * Wraps the block CRUD + document type catalog endpoints on the
 * `/api/v1/documents-v2/admin/*` router. Goes through `apiClient`
 * (tenant axios) because the document substrate is mounted on the
 * tenant router with `require_admin` gating — same pattern as the
 * existing `services/documents-v2-service.ts`.
 *
 * The visual editor's Documents tab consumes this service. This is
 * a deliberate small architectural boundary cross — the visual
 * editor is platform-tree but the document substrate it edits is
 * mounted tenant-side.
 */
import apiClient from "@/lib/api-client"


// ─── Types ────────────────────────────────────────────────────


export interface TemplateBlock {
  id: string
  template_version_id: string
  block_kind: string
  position: number
  config: Record<string, unknown>
  condition: string | null
  parent_block_id: string | null
  created_at: string
  updated_at: string
}


export interface BlockKindMetadata {
  kind: string
  display_name: string
  description: string
  config_schema: Record<string, unknown>
  accepts_children: boolean
}


export interface DocumentTypeStarterBlock {
  block_kind: string
  config: Record<string, unknown>
  condition: string | null
}


export interface DocumentTypeMetadata {
  type_id: string
  display_name: string
  category: string
  description: string
  starter_blocks: DocumentTypeStarterBlock[]
  recommended_variables: string[]
}


export interface DocumentTypeCategory {
  category_id: string
  display_name: string
}


export interface DocumentTypeCatalog {
  categories: DocumentTypeCategory[]
  types: DocumentTypeMetadata[]
}


// ─── Block CRUD ───────────────────────────────────────────────


export const documentBlocksService = {
  async list(templateId: string, versionId: string): Promise<TemplateBlock[]> {
    const { data } = await apiClient.get<TemplateBlock[]>(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/blocks`,
    )
    return data
  },

  async add(
    templateId: string,
    versionId: string,
    body: {
      block_kind: string
      position?: number | null
      config?: Record<string, unknown>
      condition?: string | null
      parent_block_id?: string | null
    },
  ): Promise<TemplateBlock> {
    const { data } = await apiClient.post<TemplateBlock>(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/blocks`,
      body,
    )
    return data
  },

  async update(
    templateId: string,
    versionId: string,
    blockId: string,
    body: {
      config?: Record<string, unknown>
      condition?: string | null
    },
  ): Promise<TemplateBlock> {
    const { data } = await apiClient.patch<TemplateBlock>(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/blocks/${blockId}`,
      body,
    )
    return data
  },

  async remove(
    templateId: string,
    versionId: string,
    blockId: string,
  ): Promise<void> {
    await apiClient.delete(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/blocks/${blockId}`,
    )
  },

  async reorder(
    templateId: string,
    versionId: string,
    body: { block_id_order: string[]; parent_block_id?: string | null },
  ): Promise<TemplateBlock[]> {
    const { data } = await apiClient.post<TemplateBlock[]>(
      `/documents-v2/admin/templates/${templateId}/versions/${versionId}/blocks/reorder`,
      body,
    )
    return data
  },

  async listBlockKinds(): Promise<BlockKindMetadata[]> {
    const { data } = await apiClient.get<BlockKindMetadata[]>(
      "/documents-v2/admin/block-kinds",
    )
    return data
  },

  async listDocumentTypes(): Promise<DocumentTypeCatalog> {
    const { data } = await apiClient.get<DocumentTypeCatalog>(
      "/documents-v2/admin/document-types",
    )
    return data
  },
}

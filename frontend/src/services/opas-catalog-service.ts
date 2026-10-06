/** Reads for the Opas catalog panes. Three endpoints, all read-only. */
// ⚠️ DEFAULT IMPORT. `api-client` default-exports; `import { apiClient }` compiles to
// undefined at runtime. CLAUDE.md §11 records a mock that declared `{ apiClient }` against
// this very module and made five tests pass against a member that does not exist — tsc
// caught it here, which is the difference between a typed import and a hand-written double.
import apiClient from "@/lib/api-client"

export interface CatalogVariant {
  variant_template_id: string
  name: string
  kind: string
  option_label?: string
  sku?: string
  family_slug?: string
  product_name?: string
}

export interface VariantDetail extends CatalogVariant {
  description?: string
  /** ⚠️ ABSENT when the variant has no specs. Never `{}` — the server omits the key, and
   *  the pane's "render only what exists" rule depends on that. */
  specs?: Record<string, string>
  aliases?: string[]
  personalization?: { question_id: string; label: string; permitted_answers: string[] }[]
}

export interface ResolveResult {
  phrase: string
  normalized: string
  resolved: boolean
  candidates: CatalogVariant[]
  discriminators: string[]
}

export async function listVariants(): Promise<CatalogVariant[]> {
  const r = await apiClient.get<{ variants: CatalogVariant[] }>("/catalog-pane/variants")
  return r.data.variants
}

export async function getVariant(id: string): Promise<VariantDetail> {
  const r = await apiClient.get<VariantDetail>(`/catalog-pane/variants/${id}`)
  return r.data
}

export async function resolvePhrase(phrase: string): Promise<ResolveResult> {
  const r = await apiClient.post<ResolveResult>("/catalog-pane/resolve", { phrase })
  return r.data
}

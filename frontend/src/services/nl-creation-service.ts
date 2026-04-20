/**
 * NL Creation API client.
 *
 * Three endpoints under /api/v1/nl-creation. Live calls, no
 * caching — the extract endpoint is called on every debounced
 * keystroke and must reflect current input.
 */

import apiClient from "@/lib/api-client";
import type {
  CreateRequest,
  CreateResponse,
  ExtractRequest,
  ExtractionResult,
  NLEntityTypeInfo,
} from "@/types/nl-creation";

export async function extractFields(
  body: ExtractRequest,
  signal?: AbortSignal,
): Promise<ExtractionResult> {
  const r = await apiClient.post<ExtractionResult>(
    "/nl-creation/extract",
    body,
    { signal },
  );
  return r.data;
}

export async function createEntity(
  body: CreateRequest,
): Promise<CreateResponse> {
  const r = await apiClient.post<CreateResponse>(
    "/nl-creation/create",
    body,
  );
  return r.data;
}

export async function listNLEntityTypes(): Promise<NLEntityTypeInfo[]> {
  const r = await apiClient.get<NLEntityTypeInfo[]>(
    "/nl-creation/entity-types",
  );
  return r.data;
}

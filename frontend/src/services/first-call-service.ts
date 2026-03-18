import apiClient from "@/lib/api-client";
import type { FirstCallExtractionResult } from "@/types/first-call";

export async function extractFirstCall(
  text: string,
  existingValues: Record<string, unknown>,
): Promise<FirstCallExtractionResult> {
  const { data } = await apiClient.post("/cases/extract-first-call", {
    text,
    existing_values: existingValues,
  });
  return data;
}

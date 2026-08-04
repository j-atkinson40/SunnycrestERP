/**
 * Books Review Arc B B-4.5 — recipient search for the "Ask someone" flag flow.
 * The CALLER owns debounce + abort (this is just the fetch); the RankedRows
 * primitive renders whatever rows it's handed.
 */
import apiClient from "@/lib/api-client"

export interface FlagRecipient {
  id: string
  name: string
  email: string
  /** How many "Ask someone" flags are already open on this person. */
  waiting_count: number
}

export async function searchFlagRecipients(
  q: string,
  signal?: AbortSignal,
): Promise<FlagRecipient[]> {
  const { data } = await apiClient.get<{ recipients: FlagRecipient[] }>(
    "/reconciliation/flag-recipients",
    { params: { q }, signal },
  )
  return data.recipients
}

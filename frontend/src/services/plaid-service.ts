/**
 * Plaid banking service (B-1) — the connect moment's reads + writes.
 *
 * SECURITY SHAPE: the backend's item_summary carries NO token field by
 * design; the access token never reaches the browser. link-token +
 * exchange are tenant-admin routes (403 for others); items reads are
 * any-tenant-user so the setup card can show the honest connected /
 * ask-an-admin states.
 */
import apiClient from "@/lib/api-client"

export interface PlaidBankAccount {
  id: string
  name: string
  mask: string | null
  account_type: string
  account_subtype: string | null
  is_credit: boolean
  financial_account_id: string | null
}

export interface PlaidItemSummary {
  id: string
  institution_name: string | null
  institution_id: string | null
  status: "active" | "login_required" | "pending_expiration" | "error" | "disconnected"
  last_synced_at: string | null
  accounts: PlaidBankAccount[]
}

export async function getPlaidItems(): Promise<PlaidItemSummary[]> {
  const { data } = await apiClient.get("/plaid/items")
  return data
}

/** Admin-only. Pass item_id for UPDATE MODE (re-auth of a degraded item). */
export async function createLinkToken(itemId?: string): Promise<string> {
  const { data } = await apiClient.post("/plaid/link-token", itemId ? { item_id: itemId } : {})
  return data.link_token
}

/** Admin-only. Institution metadata rides from Link's onSuccess. */
export async function exchangePublicToken(input: {
  public_token: string
  institution_id?: string | null
  institution_name?: string | null
}): Promise<PlaidItemSummary> {
  const { data } = await apiClient.post("/plaid/exchange", input)
  return data
}

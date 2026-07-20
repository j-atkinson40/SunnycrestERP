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
  // Session-1 cash wire: the strip died — balances travel with as-of.
  current_balance: number | null
  available_balance: number | null
  balance_as_of: string | null
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


export interface ReconAccount {
  id: string
  account_name: string
  account_type: string
}

export async function getReconciliationAccounts(): Promise<ReconAccount[]> {
  const { data } = await apiClient.get("/reconciliation/accounts")
  return data
}

/** Admin-only. null unlinks (honest). */
export async function linkBankAccount(
  accountId: string, financialAccountId: string | null,
): Promise<void> {
  await apiClient.patch(`/plaid/accounts/${accountId}/link`, {
    financial_account_id: financialAccountId,
  })
}

/** Admin-only. The feed stops; history and matches remain. */
export async function disconnectPlaidItem(itemId: string): Promise<void> {
  await apiClient.post(`/plaid/items/${itemId}/disconnect`)
}

// ── B-3: the category-map settings surface ──────────────────────────────

export interface CategoryMapping {
  plaid_category: string
  expense_category: string
  source: "seeded" | "yours"
}

export interface CategoryMapResponse {
  mappings: CategoryMapping[]
  uncategorized_count: number
  expense_categories: string[]
}

export async function getCategoryMappings(): Promise<CategoryMapResponse> {
  const { data } = await apiClient.get("/plaid/category-mappings")
  return data
}

/** Admin-only; null clears the tenant override (the seeded row returns).
 * FORWARD-ONLY: changes apply to new transactions. */
export async function setCategoryOverride(
  plaidCategory: string, expenseCategory: string | null,
): Promise<void> {
  await apiClient.put("/plaid/category-mappings", {
    plaid_category: plaidCategory, expense_category: expenseCategory,
  })
}

export interface UncategorizedTxn {
  id: string
  date: string
  description: string
  amount: string
  plaid_category_primary: string | null
  plaid_category_detailed: string | null
}

export async function getUncategorized(): Promise<UncategorizedTxn[]> {
  const { data } = await apiClient.get("/plaid/transactions/uncategorized")
  return data
}

// ── Session-1 cash wire ──────────────────────────────────────────────────

export interface CashPositionAccount {
  id: string
  institution: string | null
  item_status: string
  name: string
  mask: string | null
  account_type: string
  account_subtype: string | null
  is_credit: boolean
  current_balance: number | null
  available_balance: number | null
  balance_as_of: string | null
}

export interface CashPosition {
  connected: boolean
  accounts: CashPositionAccount[]
  cash_on_hand: number
  credit_owed: number
  as_of: string | null
  definition: string
}

export async function getCashPosition(): Promise<CashPosition> {
  const { data } = await apiClient.get("/plaid/cash-position")
  return data
}

export interface BankActivityItem {
  id: string
  date: string
  account_name: string
  account_mask: string | null
  description: string
  amount: string
  pending: boolean
  expense_category: string | null
  plaid_category_primary: string | null
}

export async function getBankActivity(params: {
  account_id?: string
  start?: string
  end?: string
  page?: number
  per_page?: number
}): Promise<{ total: number; page: number; per_page: number; items: BankActivityItem[] }> {
  const { data } = await apiClient.get("/plaid/transactions", { params })
  return data
}

/**
 * GLAccountPicker — the one way to choose a GL account (Ledger Posting L-2.1d).
 *
 * Three call sites: the journal-entry line editor (migrated here in the same
 * commit that created this file — a "shared" component with the oldest caller
 * still holding its own copy is a third implementation, not a removed one), the
 * reconciliation keyword→GL map, and a bank account's contra.
 *
 * SOURCE: `GET /journal-entries/gl-accounts` — tenant-scoped, active-only,
 * ordered by account_number. Its filter is exactly `validate_gl_account`'s minus
 * the id, so anything this picker offers will pass validation at write.
 *
 * CALLER-SUPPLIED LIST, per the WorkflowPicker precedent — this component does
 * NOT fetch. The journal-entry form loads the list once for a whole entry; a
 * self-fetching picker would turn a ten-line entry into ten requests for 224
 * rows. `fetchGLAccounts` is exported for callers that need it.
 *
 * SEARCH, unlike WorkflowPicker. That component deferred search on the stated
 * grounds that ~30 workflows are within a Select's native typeahead. Production
 * has **224 active GL mappings**; typeahead over an unsorted-by-name list of
 * that size is not a control. Filtering is local — the list is already in hand.
 *
 * NO CATEGORY FILTER, deliberately, and this is not an oversight to optimize
 * away later: 73 of those 224 rows carry `platform_category = "other"`,
 * including `6450 DIRECT LABOR` and `6600 PAYROLL TAX EXPENSE-MFG`. Filtering to
 * "expense" for a bank-fee mapping would hide accounts an operator legitimately
 * needs and make this component an opinion about a chart it does not own. The
 * category is shown as information; it is never a gate.
 */
import { useMemo, useRef, useState } from "react"
import { Check, ChevronsUpDown, Search, TriangleAlert } from "lucide-react"

import apiClient from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export interface GLAccount {
  id: string
  account_number: string
  account_name: string
  category?: string
}

export interface GLAccountPickerProps {
  /** Caller-supplied and caller-cached. See the header note on fetching. */
  accounts: GLAccount[]
  value: string | null
  /**
   * `null` means "no account". Callers that must distinguish *cleared* from
   * *untouched* on the wire do that at their payload layer — this component
   * only ever reports what the operator chose.
   */
  onChange: (glAccountId: string | null) => void
  /** Renders an explicit clear row. Without it there is no way back to null. */
  allowNone?: boolean
  noneLabel?: string
  placeholder?: string
  disabled?: boolean
  /** Table-row sizing: smaller type and tighter padding. */
  compact?: boolean
  "aria-label"?: string
  "data-testid"?: string
}

/** "8801 — BANK FEES". One label shape everywhere the chart is shown. */
export function glAccountLabel(a: GLAccount): string {
  return `${a.account_number} — ${a.account_name}`
}

/**
 * Pure, and exported so the matching rules can be tested without a DOM.
 *
 * Matches account NUMBER and NAME, never category — see the header. Number
 * matching is `startsWith` first so typing "88" surfaces the 8800s ahead of an
 * account that merely contains "88" somewhere, which is how anyone who knows
 * their chart actually searches.
 */
export function filterGLAccounts(accounts: GLAccount[], query: string): GLAccount[] {
  const q = query.trim().toLowerCase()
  if (!q) return accounts
  const starts: GLAccount[] = []
  const contains: GLAccount[] = []
  for (const a of accounts) {
    const num = a.account_number?.toLowerCase() ?? ""
    const name = a.account_name?.toLowerCase() ?? ""
    if (num.startsWith(q)) starts.push(a)
    else if (num.includes(q) || name.includes(q)) contains.push(a)
  }
  return [...starts, ...contains]
}

export async function fetchGLAccounts(): Promise<GLAccount[]> {
  const res = await apiClient.get("/journal-entries/gl-accounts")
  return res.data as GLAccount[]
}

export function GLAccountPicker({
  accounts,
  value,
  onChange,
  allowNone = false,
  noneLabel = "No account",
  placeholder = "Select account…",
  disabled = false,
  compact = false,
  "aria-label": ariaLabel,
  "data-testid": testId,
}: GLAccountPickerProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const selected = useMemo(
    () => (value ? accounts.find((a) => a.id === value) ?? null : null),
    [accounts, value],
  )
  // A value we hold but cannot name. The journal-entry form can reach this: its
  // AI parse returns whatever the model wrote for `gl_account_id`, unresolved
  // against the chart, and the old native <select> rendered it as BLANK while
  // still submitting it — so the operator learned about it from a 400 at save.
  // Say it here instead. Critically, we do NOT clear the value: silently
  // discarding something the caller is holding is the worse failure.
  const unknown = value !== null && selected === null

  const filtered = useMemo(
    () => filterGLAccounts(accounts, query),
    [accounts, query],
  )

  const pick = (id: string | null) => {
    onChange(id)
    setQuery("")
    setOpen(false)
  }

  const triggerText = selected
    ? glAccountLabel(selected)
    : unknown
      ? "Unrecognised account"
      : placeholder

  return (
    <Popover
      open={open}
      onOpenChange={(next: boolean) => {
        setOpen(next)
        if (!next) setQuery("")
      }}
    >
      <PopoverTrigger
        disabled={disabled}
        aria-label={ariaLabel ?? "GL account"}
        data-testid={testId}
        className={cn(
          "focus-ring-accent flex w-full items-center justify-between gap-2 rounded-md border bg-surface-raised text-left text-content-base disabled:opacity-50",
          compact ? "px-1.5 py-1 text-caption" : "px-2.5 py-2 text-body-sm",
          unknown ? "border-status-warning" : "border-border-base",
        )}
      >
        <span
          className={cn(
            "truncate",
            !selected && !unknown && "text-content-subtle",
            unknown && "text-status-warning",
          )}
        >
          {unknown ? (
            <span className="inline-flex items-center gap-1">
              <TriangleAlert size={compact ? 11 : 13} />
              {triggerText}
            </span>
          ) : (
            triggerText
          )}
        </span>
        <ChevronsUpDown size={compact ? 11 : 13} className="shrink-0 text-content-subtle" />
      </PopoverTrigger>

      {/* Fixed width rather than the trigger's: the trigger may be a narrow
          table cell, and account names are long. */}
      <PopoverContent align="start" className="w-80 max-w-(--available-width) p-0">
        <div className="flex items-center gap-2 border-b border-border-subtle px-2.5 py-2">
          <Search size={13} className="shrink-0 text-content-subtle" />
          <input
            ref={inputRef}
            // The popup mounts on open, so this lands focus in the search box
            // every time — 224 accounts means typing is the primary gesture.
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Number or name"
            aria-label="Search GL accounts"
            data-testid={testId ? `${testId}-search` : undefined}
            className="w-full bg-transparent text-body-sm text-content-base outline-none placeholder:text-content-subtle"
          />
        </div>

        {unknown && (
          <p className="border-b border-border-subtle px-2.5 py-2 text-caption text-status-warning">
            The account currently set is not in your chart of accounts. Choose one
            below to replace it.
          </p>
        )}

        <ul className="max-h-64 overflow-y-auto py-1" role="listbox">
          {allowNone && (
            <li>
              <button
                type="button"
                role="option"
                aria-selected={value === null}
                onClick={() => pick(null)}
                data-testid={testId ? `${testId}-none` : undefined}
                className="focus-ring-accent flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-body-sm text-content-muted hover:bg-accent-subtle"
              >
                <span className="w-3.5 shrink-0">
                  {value === null && <Check size={13} />}
                </span>
                {noneLabel}
              </button>
            </li>
          )}
          {filtered.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                role="option"
                aria-selected={a.id === value}
                onClick={() => pick(a.id)}
                data-testid={`gl-account-option-${a.account_number}`}
                className="focus-ring-accent flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-body-sm text-content-base hover:bg-accent-subtle"
              >
                <span className="w-3.5 shrink-0">
                  {a.id === value && <Check size={13} />}
                </span>
                <span className="font-plex-mono text-caption tabular-nums text-content-muted">
                  {a.account_number}
                </span>
                <span className="truncate">{a.account_name}</span>
                {a.category && (
                  // Information, never a filter. See the header.
                  <span className="ml-auto shrink-0 text-micro text-content-subtle">
                    {a.category}
                  </span>
                )}
              </button>
            </li>
          ))}
          {filtered.length === 0 && (
            <li className="px-2.5 py-3 text-body-sm text-content-subtle">
              No account matches “{query}”.
            </li>
          )}
        </ul>
      </PopoverContent>
    </Popover>
  )
}

/**
 * What makes two panes the same pane.
 *
 * ⚠️ JAMES'S FIRST MULTI-PANE RULE (2026-10-19): "Opening a record that's already open
 * focuses that pane; never a duplicate." Needed now that panes chain — an order opens
 * its vault, a vault's order list opens orders back, and walking a loop used to leave a
 * stack of identical panes behind.
 *
 * ⚠️ IT WAS ALREADY HALF-DONE, IN ONE PLACE, FOR ONE KIND. `OpasHost.openSalesOrder`
 * checked for an open pane with the same `salesOrderId` and raised it. Nothing did the
 * same for a product, so opening the Monticello from two different orders made two
 * Monticello panes. Moving the rule into the context makes it true for every caller
 * rather than for the one that remembered.
 *
 * ⚠️ EVERY KIND IS CLASSIFIED AND A TEST ENFORCES IT, the same argument as
 * `pane-mode.ts`: `PANE_IDENTITY` is `Record<OpasPaneKind, …>`, so a new kind will not
 * compile without a row, and `pane-identity.test.ts` enumerates the union as DATA so
 * that widening `OpasPaneKind` to `string` fails there rather than silently.
 *
 * `null` means NEVER DEDUPE. That is not "no identity yet" — it is a decision:
 *
 *   capture       two captures are two different orders being typed. Deduping them
 *                 would hand the second one the first one's half-typed order.
 *   product-list  the catalog, a numbered pick, and an unmatched phrase are three
 *                 different lists under one kind, and `OpasHost` already replaces the
 *                 open one by its own route. Deduping on kind would make a numbered
 *                 pick raise the unfiltered catalog instead of showing the pick.
 */
import type { OpasPane, OpasPaneKind } from "@/contexts/opas-context"

/** The identity of a pane, or `null` when panes of this kind never dedupe. */
export type PaneIdentity = (pane: Omit<OpasPane, "id">) => string | null

/** ⚠️ EXHAUSTIVE BY TYPE. Adding a kind without a row here will not compile. */
export const PANE_IDENTITY: Record<OpasPaneKind, PaneIdentity> = {
  capture: () => null,
  "product-list": () => null,
  product: (p) => (p.variantTemplateId !== undefined ? `product:${p.variantTemplateId}` : null),
  // ⚠️ A SINGLETON, WHICH IS WHY THE IDENTITY IS CONSTANT. There is one order list and a
  // new question updates it in place (`settleOrderAnswer` patches the open one) rather
  // than opening a second. The constant says so; a `null` here would let a second list
  // open and the patching caller would then update the wrong one.
  "order-list": () => "order-list",
  "sales-order": (p) => (p.salesOrderId !== undefined ? `order:${p.salesOrderId}` : null),
  // ⚠️ "Opening one already open focuses it; never a duplicate" (James, 2026-10-24),
  // which is the same rule as the order and the product. It earns its keep here more
  // than anywhere: a customer is reachable three ways in this slice — the bar, the
  // funeral home link on an order, and "the customer" with an order in front — so
  // walking order -> customer -> order -> customer is the ordinary path, not a corner.
  customer: (p) => (p.customerId !== undefined ? `customer:${p.customerId}` : null),
  // ⚠️ AND A CEMETERY NEEDS IT FOR A FOURTH REASON, which is the walk James gave with
  // the slice: cemetery -> order -> back to the cemetery via the order's own link. That
  // last step MUST focus the pane already open, or the desk ends up holding two
  // St. Mary's.
  cemetery: (p) => (p.cemeteryId !== undefined ? `cemetery:${p.cemeteryId}` : null),
  // ⚠️ A SINGLETON, LIKE THE ORDER LIST. There is one rulebook per tenant, so asking
  // for it twice must focus the open one — two copies could disagree about which rules
  // are switched off the moment one of them was edited.
  rulebook: () => "rulebook",
}

/** ⚠️ NO FALLBACK, DELIBERATELY — see the module docstring. */
export function paneIdentity(pane: Omit<OpasPane, "id">): string | null {
  return PANE_IDENTITY[pane.kind](pane)
}

/**
 * The already-open pane this one would duplicate, or `undefined`.
 *
 * ⚠️ IT COMPARES IDENTITIES, NOT KINDS. A product pane with no `variantTemplateId` has
 * no identity and therefore duplicates nothing — which is correct and is the case a
 * kind comparison would get wrong.
 */
export function findDuplicate(
  panes: readonly OpasPane[],
  pane: Omit<OpasPane, "id">,
): OpasPane | undefined {
  const identity = paneIdentity(pane)
  if (identity === null) return undefined
  return panes.find((open) => paneIdentity(open) === identity)
}

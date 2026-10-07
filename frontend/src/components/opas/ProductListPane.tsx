/**
 * The Product List pane — the catalog, grouped by kind.
 *
 * ⚠️ READS THE PLATFORM CATALOG, NOT TENANT PRODUCTS, by ruling. The two populations are
 * disjoint: `products.variant_template_id` is 0 of 27 populated and no SKU matches, so a
 * tenant product cannot reach a spec, an availability or an alias.
 */
import { useEffect, useMemo, useState } from "react"

import { listVariants, type CatalogVariant } from "@/services/opas-catalog-service"
import { resolveRowLabels } from "./option-label"

/** Readable labels for `product_templates.form`. Unknown kinds fall through verbatim
 *  rather than being hidden — an unlabelled group is a visible gap, a dropped one is not. */
const KIND_LABEL: Record<string, string> = {
  burial_vault: "Burial vaults",
  urn_vault: "Urn vaults",
  urn: "Urns",
  grave_liner: "Grave liners",
  equipment: "Cemetery equipment",
  infant: "Infant",
}

export function ProductListPane({
  candidateIds,
  unmatchedPhrase,
  onOpenProduct,
}: {
  candidateIds?: readonly string[]
  unmatchedPhrase?: string
  onOpenProduct: (variantTemplateId: string) => void
}) {
  const [rows, setRows] = useState<CatalogVariant[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    listVariants()
      .then((v) => alive && setRows(v))
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
    }
  }, [])

  const shown = useMemo(() => {
    if (rows === null) return null
    // ⚠️ A NUMBERED PICK filters to the resolver's candidates and NOTHING ELSE. The list is
    // the pick; the overlay still does not choose.
    if (candidateIds !== undefined) {
      const want = new Set(candidateIds)
      return rows.filter((r) => want.has(r.variant_template_id))
    }
    return rows
  }, [rows, candidateIds])

  // ⚠️ RESOLVED OVER THE WHOLE SHOWN SET, NOT PER GROUP, because a collision is defined
  // within a group and the function keys on kind itself. Computing it per group would work
  // too; doing it once keeps a single source for the labels the rows read.
  const labels = useMemo(() => resolveRowLabels(shown ?? []), [shown])

  const groups = useMemo(() => {
    if (shown === null) return null
    // The server already orders by kind, so grouping preserves its order rather than
    // re-sorting — a client sort here would silently override the catalog's own sequence.
    const out: { kind: string; items: CatalogVariant[] }[] = []
    for (const r of shown) {
      const last = out[out.length - 1]
      if (last !== undefined && last.kind === r.kind) last.items.push(r)
      else out.push({ kind: r.kind, items: [r] })
    }
    return out
  }, [shown])

  if (failed) {
    return (
      <p data-testid="opas-list-failed" style={{ fontSize: 13, color: "#cc7452", margin: 0 }}>
        The catalog could not be read.
      </p>
    )
  }
  if (groups === null) {
    return (
      <p data-testid="opas-list-loading" style={{ fontSize: 13, color: "#5e5e5e", margin: 0 }}>
        Reading the catalog…
      </p>
    )
  }

  return (
    <div data-testid="opas-product-list">
      {/* ⚠️ The unmatched phrase is SAID, not silently swallowed. A list that simply
          appeared would leave the director thinking their phrase had matched everything. */}
      {unmatchedPhrase !== undefined && (
        <p
          data-testid="opas-list-unmatched"
          style={{ fontSize: 13, color: "#cc7452", margin: "0 0 10px" }}
        >
          Nothing matched “{unmatchedPhrase}”. The whole catalog:
        </p>
      )}
      {candidateIds !== undefined && (
        <p
          data-testid="opas-list-pick"
          style={{ fontSize: 13, color: "#9a9a9a", margin: "0 0 10px" }}
        >
          Which one?
        </p>
      )}
      {groups.map((g) => (
        <section key={g.kind} data-testid={`opas-list-group-${g.kind}`}>
          <h3
            style={{
              fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase",
              color: "#5e5e5e", margin: "14px 0 4px", fontWeight: 400,
            }}
          >
            {KIND_LABEL[g.kind] ?? g.kind}
          </h3>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {g.items.map((r, i) => (
              <li key={r.variant_template_id}>
                <button
                  type="button"
                  data-testid={`opas-list-row-${r.variant_template_id}`}
                  onClick={() => onOpenProduct(r.variant_template_id)}
                  style={{
                    display: "flex", gap: 8, alignItems: "baseline", width: "100%",
                    textAlign: "left", background: "none", border: 0,
                    borderTop: "1px solid rgba(255,255,255,.08)", padding: "8px 0",
                    cursor: "pointer", color: "#f2f2f2", fontSize: 14,
                  }}
                >
                  {/* ⚠️ The number only appears in a pick. A permanent index would read as
                      a catalog ordering the catalog does not have. */}
                  {candidateIds !== undefined && (
                    <span style={{ color: "#5e5e5e", fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>
                      {i + 1}
                    </span>
                  )}
                  <span>{r.name}</span>
                  {/* ⚠️ The label shows only when it ADDS something, and where two rows
                      would otherwise look identical it becomes the LINE NAME. Both rules
                      live in `resolveRowLabels`; `!== r.name` was too weak to start with —
                      it let "Bronze" through on "Wilbert Bronze Burial Vault". */}
                  {labels[r.variant_template_id] !== undefined && (
                    <span data-testid={`opas-list-label-${r.variant_template_id}`}
                          style={{ color: "#9a9a9a", fontSize: 12 }}>
                      {labels[r.variant_template_id]}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

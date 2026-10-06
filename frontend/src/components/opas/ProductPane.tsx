/**
 * The Product pane. Renders ONLY what the data establishes.
 *
 * ⚠️ SECTIONS IN SPEC ORDER, AND THE ABSENT ONES ARE ABSENT — no placeholders, no dashes,
 * no "coming soon". Measured 2026-10-06 over 52 variants: 29 have at least one spec, 5 have
 * a confirmed alias, and **0 have personalization availability** (of 3
 * `wilbert_program_enrollments` rows all 3 carry a config and none has an `availability`
 * key). So the Personalization pill is coded and will not render for any product today.
 *
 * ⚠️ NOT SHOWN, BY RULING: price (no price column exists on any platform tier), the
 * made-here/bought-in chip (`is_manufactured` NULL on all 27 products), Recent orders,
 * Price history, Stock, Right now, Order one, Send spec sheet, Roles.
 */
import { useEffect, useState } from "react"

import { getVariant, type VariantDetail } from "@/services/opas-catalog-service"

const KIND_LABEL: Record<string, string> = {
  burial_vault: "Burial vault", urn_vault: "Urn vault", urn: "Urn",
  grave_liner: "Grave liner", equipment: "Cemetery equipment", infant: "Infant",
}

/** Spec keys in render order, with the labels the pane shows. */
const SPEC_ROWS: readonly [string, string][] = [
  ["outside_length_in", "Outside length"],
  ["outside_width_in", "Outside width"],
  ["outside_height_in", "Outside height"],
  ["inside_length_in", "Inside length"],
  ["inside_width_in", "Inside width"],
  ["inside_height_in", "Inside height"],
  ["weight_lb", "Weight"],
]

const UNIT: Record<string, string> = { weight_lb: " lb", default: " in" }

export function ProductPane({ variantTemplateId }: { variantTemplateId: string }) {
  const [d, setD] = useState<VariantDetail | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    setD(null)
    setFailed(false)
    getVariant(variantTemplateId)
      .then((v) => alive && setD(v))
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
    }
  }, [variantTemplateId])

  if (failed) {
    return (
      <p data-testid="opas-product-failed" style={{ fontSize: 13, color: "#cc7452", margin: 0 }}>
        That product could not be read.
      </p>
    )
  }
  if (d === null) {
    return (
      <p data-testid="opas-product-loading" style={{ fontSize: 13, color: "#5e5e5e", margin: 0 }}>
        Reading…
      </p>
    )
  }

  const specRows = SPEC_ROWS.filter(([k]) => d.specs?.[k] !== undefined)

  return (
    <div data-testid="opas-product-pane">
      <div style={{ fontSize: 20, fontWeight: 300, lineHeight: 1.2 }}>{d.name}</div>
      <div data-testid="opas-product-meta" style={{ fontSize: 13, color: "#9a9a9a", marginTop: 2 }}>
        {KIND_LABEL[d.kind] ?? d.kind}
        {/* ⚠️ SKU only when the platform row carries one. */}
        {d.sku !== undefined && (
          <>
            {" · "}
            <span data-testid="opas-product-sku" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
              {d.sku}
            </span>
          </>
        )}
      </div>

      {/* SPECS — the whole section is absent when nothing is established. */}
      {specRows.length > 0 && (
        <section data-testid="opas-product-specs" style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e", margin: "0 0 4px", fontWeight: 400 }}>
            Specs
          </h3>
          <dl style={{ margin: 0 }}>
            {specRows.map(([k, label]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 16, padding: "5px 0", borderTop: "1px solid rgba(255,255,255,.08)", fontSize: 13 }}>
                <dt style={{ color: "#5e5e5e" }}>{label}</dt>
                <dd style={{ margin: 0 }}>
                  {d.specs![k]}
                  {UNIT[k] ?? UNIT.default}
                </dd>
              </div>
            ))}
          </dl>
          {/* ⚠️ `spec_source` travels with the specs — r193 made it the membership marker,
              and a dimension with no stated source is a number with no provenance. */}
          {d.specs?.spec_source !== undefined && (
            <p data-testid="opas-product-spec-source" style={{ fontSize: 11, color: "#5e5e5e", margin: "6px 0 0" }}>
              from {d.specs.spec_source}
            </p>
          )}
        </section>
      )}

      {/* PERSONALIZATION — coded, and renders for nothing today. See the module docstring. */}
      {d.personalization !== undefined && d.personalization.length > 0 && (
        <section data-testid="opas-product-personalization" style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e", margin: "0 0 4px", fontWeight: 400 }}>
            Personalization
          </h3>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 6 }}>
            {d.personalization.map((q) => (
              <li key={q.question_id} style={{ border: "1px solid rgba(255,255,255,.12)", borderRadius: 999, padding: "2px 10px", fontSize: 12, color: "#f2f2f2" }}>
                {q.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* WHAT OPAS KNOWS — confirmed aliases only. An unconfirmed alias is a guess nobody
          accepted, and showing it here would present a guess as knowledge. */}
      {d.aliases !== undefined && d.aliases.length > 0 && (
        <section data-testid="opas-product-aliases" style={{ marginTop: 14 }}>
          <h3 style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#5e5e5e", margin: "0 0 4px", fontWeight: 400 }}>
            What Opas knows
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {d.aliases.map((a) => (
              <span key={a} style={{ border: "1px dashed rgba(255,255,255,.16)", borderRadius: 999, padding: "2px 10px", fontSize: 12, color: "#9a9a9a" }}>
                also “{a}”
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

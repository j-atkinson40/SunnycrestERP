/**
 * TAX-4 — the onboarding step that asks whether your customers can be taxed.
 *
 * ⚠️ AN OBLIGATION, NOT A GATE. A tenant with 400 imported customers and 30 bad
 * addresses must be able to finish onboarding — the 30 surface at the till once
 * the order path refuses, and blocking platform use over them would be the wrong
 * trade. What this page exists to guarantee is that the tenant KNEW. Opening it
 * is what completes the step; reaching zero unresolved is not required and is
 * not implied anywhere in the copy.
 *
 * ⚠️ AND IT NAMES THE ROWS. A count sends someone hunting. Each unresolved
 * customer carries the sentence the resolver produced for it — including, for an
 * ambiguous ZIP, the counties it spans and their differing rates. Same
 * discipline as a migration pre-flight: report which, not how many.
 *
 * Nothing is cached. The answer changes every time a customer is edited, and a
 * stored readiness count is a second producer of a fact derived from `customers`
 * — the `setup_complete` shape, where a flag outlives what it described.
 */
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, ArrowRight, CheckCircle2, MapPin, RefreshCw } from "lucide-react"

import apiClient from "@/lib/api-client"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface UnresolvedCustomer {
  customer_id: string
  customer_name: string
  zip_code: string | null
  reason: string
}

interface ResolvedCustomer {
  customer_id: string
  customer_name: string
  county: string
  rate_percentage: number
}

interface ReadinessReport {
  total_customers: number
  resolves: number
  unresolved: number
  counts: Record<string, number>
  customers: {
    no_address: UnresolvedCustomer[]
    ambiguous: UnresolvedCustomer[]
    unconfigured: UnresolvedCustomer[]
    resolves: ResolvedCustomer[]
  }
  verdict: "complete" | "partial" | "reported_none"
}

/* Worst first, and each names a different action — the reason three states
   exist rather than one "unresolved" bucket. */
const GROUPS: { key: keyof ReadinessReport["customers"]; label: string; action: string }[] = [
  { key: "no_address", label: "No address on file", action: "Add a ZIP code to these customers" },
  { key: "ambiguous", label: "ZIP spans more than one county", action: "Set the tax county on these customers" },
  { key: "unconfigured", label: "County not configured", action: "Add these counties in tax settings" },
]

export default function TaxReadinessPage() {
  const [report, setReport] = useState<ReadinessReport | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    apiClient
      .get("/tax/readiness")
      .then((r) => setReport(r.data))
      /* ⚠️ A BARE `.catch` IS SAFE HERE AND WAS NOT SAFE ON THE EXEMPTIONS TAB,
         AND THE DIFFERENCE IS THE DATA SHAPE — not the catch.
         There, a swallowed failure left an empty ARRAY, which renders as a
         legitimate "nothing to report" and is exactly how a 500-ing endpoint
         reported all-clear for as long as it existed. Here a failure leaves
         `report` NULL, which is not a state the API can legitimately return, so
         `!report` below is a real guard rather than an indistinguishable one.

         A separate `failed` flag was tried first and was dead state: removing
         the `.catch` entirely still rendered the error card, so the flag proved
         nothing and a test asserting it would have been measuring itself. */
      .catch(() => setReport(null))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-300" />
      </div>
    )
  }

  if (!report) {
    return (
      <Card className="border-red-200 max-w-2xl">
        <CardContent className="p-8 text-center space-y-2">
          <p className="text-sm font-medium text-red-700">Couldn&rsquo;t check tax readiness</p>
          <p className="text-xs text-gray-500">
            This is not a clean result — customers may be unresolved and are not shown.
          </p>
          <Button variant="outline" size="sm" onClick={load}>Try again</Button>
        </CardContent>
      </Card>
    )
  }

  const { verdict, total_customers, resolves, unresolved } = report

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Check your customers can be taxed</h1>
        <p className="text-sm text-gray-600 mt-1">
          Sales tax resolves from a customer&rsquo;s address. A customer that
          doesn&rsquo;t resolve is charged no tax — which is not the same as being
          exempt.
        </p>
      </div>

      {verdict === "reported_none" ? (
        <Card>
          <CardContent className="p-8 text-center space-y-1">
            <p className="text-sm text-gray-600">No customers yet</p>
            {/* Distinct from "everything resolves" — nothing has been checked,
                and saying so keeps an empty result from reading as a clean one. */}
            <p className="text-xs text-gray-400">
              There&rsquo;s nothing to check until you import or add customers. Come
              back after that.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Card>
              <CardContent className="p-3 text-center">
                <p className="text-2xl font-bold text-gray-900">{total_customers}</p>
                <p className="text-xs text-gray-500">Active customers</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <p className="text-2xl font-bold text-green-600">{resolves}</p>
                <p className="text-xs text-gray-500">Resolve to a county</p>
              </CardContent>
            </Card>
            <Card className={unresolved > 0 ? "border-amber-200" : ""}>
              <CardContent className="p-3 text-center">
                <p className="text-2xl font-bold text-amber-600">{unresolved}</p>
                <p className="text-xs text-gray-500">Cannot be taxed yet</p>
              </CardContent>
            </Card>
          </div>

          {verdict === "complete" ? (
            <Card className="border-green-200">
              <CardContent className="p-6 flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Every customer resolves to a tax county</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    This is true of your customers as they are today — it changes
                    when you add or edit one, so it&rsquo;s worth checking again after
                    an import.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-amber-200">
              <CardContent className="p-4 flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-sm">
                  {/* ⚠️ THE STEP DOES NOT REQUIRE ZERO, AND SAYS SO. Otherwise a
                      tenant reads an unfinishable checklist as their fault. */}
                  <p className="font-medium">You can finish setting up with these unresolved.</p>
                  <p className="text-xs text-gray-600 mt-1">
                    They won&rsquo;t stop you using the platform. Each one will be
                    caught when you try to take an order for that customer, so
                    fixing them now is faster than fixing them at the counter.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {GROUPS.map(({ key, label, action }) => {
            const rows = report.customers[key] as UnresolvedCustomer[]
            if (!rows?.length) return null
            return (
              <div key={key} className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <h2 className="text-sm font-semibold text-gray-900">
                    {label} <span className="text-gray-400 font-normal">({rows.length})</span>
                  </h2>
                  <span className="text-xs text-gray-500">{action}</span>
                </div>
                {rows.map((c) => (
                  <Card key={c.customer_id}>
                    <CardContent className="p-3 flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <Link
                          to={`/customers/${c.customer_id}`}
                          className="text-sm font-medium hover:underline"
                        >
                          {c.customer_name}
                        </Link>
                        {/* The resolver's own sentence, verbatim — it already
                            names the counties and their differing rates. */}
                        <p className="text-xs text-gray-500 mt-0.5">{c.reason}</p>
                      </div>
                      <Link
                        to={`/customers/${c.customer_id}`}
                        className="text-xs text-gray-400 hover:text-gray-600 shrink-0 flex items-center gap-1"
                      >
                        Fix <ArrowRight className="h-3 w-3" />
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )
          })}

          {report.counts.unconfigured > 0 && (
            <Link
              to="/settings/tax"
              className={cn(
                "inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700",
              )}
            >
              <MapPin className="h-3 w-3" /> Add a missing county in tax settings
            </Link>
          )}
        </>
      )}
    </div>
  )
}

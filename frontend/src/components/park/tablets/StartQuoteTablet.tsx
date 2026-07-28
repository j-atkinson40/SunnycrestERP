/**
 * StartQuoteTablet (park.start-quote) — the ESCALATING act. S-5 slice 1.
 *
 * The architecturally important tablet. It:
 *  1. RE-HOSTS the existing S-2 `surface.quote-preview` via
 *     getWidgetRenderer, unchanged — the 4th-host proof (Act-inline /
 *     Focus-core / Focus-pin / park-tablet, same registry, same props).
 *  2. Reuses the S-3b portaled add-line combobox to build the draft.
 *  3. ESCALATES via the declarative registry: "Build this out →" calls
 *     `usePark().escalate(widgetId)`, which reads the act-type's declared
 *     escalation Focus (`start-quote → quote-building`) — no hardcode —
 *     opens it with the draft as params (the S-3a crossing from park),
 *     and park SUSPENDS behind the Focus. On Focus close park resumes
 *     with this tablet intact (suspend-and-return).
 *
 * The draft is an ExtractionContext held in the park session; nothing is
 * committed here — the quote Document materializes only inside the Focus
 * at save (which S-3b itself defers). So on return, this tablet reflects
 * the "still-drafting" branch: it stays in park showing its draft.
 */

import { useEffect, useState } from "react"
import { ArrowRight } from "lucide-react"

import type { ExtractionContext } from "@/components/command-bar-surfaces/types"
import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers"
import {
  getWidgetRenderer,
  registerWidgetRenderer,
} from "@/components/focus/canvas/widget-renderers"
import { AddLineCombobox } from "@/components/quote-focus/AddLineCombobox"
import { Button } from "@/components/ui/button"
import { usePark } from "@/contexts/park-context"
import { customerService } from "@/services/customer-service"

import { TabletFrame } from "./_shell"

function emptyExtraction(): ExtractionContext {
  return { entryIntent: "quote", customer: null, lines: [], rawInput: "" }
}

export function StartQuoteTablet({ widgetId }: WidgetRendererProps) {
  const { tablets, updateDraft, escalate, canEscalate } = usePark()
  const raw = tablets.find((t) => t.tabletId === widgetId)?.draft
  const draft = (raw && "entryIntent" in raw ? raw : emptyExtraction()) as
    ExtractionContext
  const [seeded, setSeeded] = useState(false)

  // Seed a customer once so the re-hosted preview has something to price.
  useEffect(() => {
    if (seeded || draft.customer) return
    let cancelled = false
    customerService
      .getCustomers(1, 1)
      .then((res) => {
        const c = res.items?.[0]
        if (cancelled) return
        setSeeded(true)
        if (c) {
          updateDraft(widgetId, (prev) => ({
            ...emptyExtraction(),
            ...(prev as unknown as ExtractionContext),
            customer: { id: c.id, name: c.name },
          }))
        }
      })
      .catch(() => {
        if (!cancelled) setSeeded(true)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widgetId, seeded, draft.customer])

  // RE-HOST: the existing S-2 quote-preview surface, mounted unchanged.
  const QuotePreview = getWidgetRenderer("surface.quote-preview")
  const escalatable = canEscalate(widgetId)

  return (
    <TabletFrame
      title={draft.customer?.name ? `Quote · ${draft.customer.name}` : "Quote"}
      footer={
        <div className="flex items-center justify-between gap-2">
          <AddLineCombobox
            onAdd={(l) =>
              updateDraft(widgetId, (prev) => {
                const base = {
                  ...emptyExtraction(),
                  ...(prev as unknown as ExtractionContext),
                }
                return {
                  ...base,
                  lines: [
                    ...base.lines,
                    {
                      productRef: l.productRef,
                      productId: l.productId,
                      quantity: 1,
                    },
                  ],
                }
              })
            }
          />
          {escalatable && (
            <Button
              size="sm"
              onClick={() => escalate(widgetId)}
              data-testid="park-quote-escalate"
            >
              Build this out
              <ArrowRight className="size-3.5" />
            </Button>
          )}
        </div>
      }
    >
      <QuotePreview
        widgetId={`${widgetId}:preview`}
        surface="park"
        config={{ customer: draft.customer, lines: draft.lines }}
      />
    </TabletFrame>
  )
}

registerWidgetRenderer("park.start-quote", StartQuoteTablet)

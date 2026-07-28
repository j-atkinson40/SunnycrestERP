/**
 * ReplyDmTablet (park.reply-dm) — a LIGHT act. S-5 slice 1.
 *
 * The DM-fan-out's first light tablet: reply to the sender. Declares no
 * Focus (a message send is an atomic gesture), so it stays in park. Its
 * draft lives in the park session in memory; it commits ONLY at the Send
 * gesture — nothing is written on summon, arrange, draft, or session end.
 *
 * No internal message-send endpoint exists yet (same missing-channel gap
 * the S-5 investigation flagged for free-form email), so slice 1 logs the
 * reply to the sender's customer record via the shipped
 * `customerService.createNote` (note_type "communication"). A true
 * message channel joins in slice 2 alongside email.
 */

import { useEffect, useState } from "react"
import { Loader2, Send } from "lucide-react"

import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { usePark } from "@/contexts/park-context"
import { customerService } from "@/services/customer-service"

import { TabletFrame } from "./_shell"

interface ReplyDraft {
  senderId?: string
  senderName?: string
  text?: string
  sent?: boolean
}

export function ReplyDmTablet({ widgetId }: WidgetRendererProps) {
  const { tablets, updateDraft } = usePark()
  const draft = (tablets.find((t) => t.tabletId === widgetId)?.draft ??
    {}) as ReplyDraft
  const [sending, setSending] = useState(false)

  // Seed the sender once from the customer list (the DM's "sender"). A
  // real DM context would carry the sender; slice 1 resolves the first
  // customer as a stand-in so the reply has a real record to log to.
  useEffect(() => {
    if (draft.senderId) return
    let cancelled = false
    customerService
      .getCustomers(1, 1)
      .then((res) => {
        const c = res.items?.[0]
        if (cancelled || !c) return
        updateDraft(widgetId, (prev) => ({
          ...prev,
          senderId: c.id,
          senderName: c.name,
        }))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widgetId, draft.senderId])

  async function send() {
    if (!draft.senderId || !draft.text?.trim() || draft.sent) return
    setSending(true)
    try {
      await customerService.createNote(draft.senderId, {
        note_type: "communication",
        content: draft.text.trim(),
      })
      updateDraft(widgetId, (prev) => ({ ...prev, sent: true }))
    } finally {
      setSending(false)
    }
  }

  return (
    <TabletFrame
      title={draft.senderName ? `Reply to ${draft.senderName}` : "Reply"}
      footer={
        <div className="flex items-center justify-between">
          <span className="text-caption text-content-subtle">
            {draft.sent ? "Sent — logged to record" : "Not sent"}
          </span>
          <Button
            size="sm"
            onClick={send}
            disabled={
              sending || draft.sent || !draft.senderId || !draft.text?.trim()
            }
            data-testid="park-reply-send"
          >
            {sending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Send className="size-3.5" />
            )}
            Send
          </Button>
        </div>
      }
    >
      <Textarea
        value={draft.text ?? ""}
        disabled={draft.sent}
        placeholder="Type your reply…"
        onChange={(e) =>
          updateDraft(widgetId, (prev) => ({ ...prev, text: e.target.value }))
        }
        className="h-full min-h-[7rem] resize-none tabular-nums"
        data-testid="park-reply-text"
      />
    </TabletFrame>
  )
}

registerWidgetRenderer("park.reply-dm", ReplyDmTablet)

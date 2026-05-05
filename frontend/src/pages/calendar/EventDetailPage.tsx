/**
 * EventDetailPage — Phase W-4b Layer 1 Calendar Step 5.
 *
 * Native event detail page implementing [DESIGN_LANGUAGE.md §14.10.3](
 * ../../../../DESIGN_LANGUAGE.md) chrome canon verbatim. Mounted at
 * route `/calendar/events/:eventId` per Q4 confirmation.
 *
 * **Composition** — Pattern 2 card with internal sections:
 *   1. Subject + time strip (font-plex-serif h2 + relative-time mono)
 *   2. Metadata strip (status pill + location + transparency + cross-
 *      tenant indicator + attendee count)
 *   3. Recurrence section (conditional on `recurrence_rule`)
 *   4. Description section (conditional on `description_text` /
 *      `description_html`; HTML rendered via sandboxed iframe to match
 *      §3.26.15.5 outbound sanitization discipline applied for inbound
 *      display)
 *   5. Attendees section — response-state status dot per attendee +
 *      "You" row inline Accept / Decline / Tentative buttons
 *   6. Linked entities section
 *   7. Action footer: [Edit event] [Reschedule] [Cancel event] [Add to
 *      my calendar]
 *
 * **Spec discipline (CLAUDE.md §12)**: this page MUST NOT introduce
 * the pre-existing `asChild` violation that lives on
 * `CalendarAccountsPage.tsx`. Action buttons that navigate use a
 * direct `<Button onClick={() => navigate(...)}>` shape instead of
 * Link composition.
 *
 * **Step 5 scope** is informative + light-action: response updates +
 * cancel commit ship today; full edit / reschedule wizards route
 * through the existing Step 3 outbound flow (drafted-not-auto-sent
 * discipline per §3.26.14.14.5).
 *
 * Data sources:
 *   - `GET /api/v1/calendar-events/{event_id}`
 *   - `GET /api/v1/calendar-events/{event_id}/attendees`
 *   - `GET /api/v1/calendar-events/{event_id}/linkages`
 *   - `PATCH /api/v1/calendar-events/{event_id}/attendees/{attendee_id}/response`
 *   - `POST /api/v1/calendar-events/{event_id}/send` (tentative → confirmed)
 *   - `POST /api/v1/calendar-events/{event_id}/cancel`
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeft,
  Calendar as CalendarIcon,
  CheckCircle2,
  Globe,
  Link as LinkIcon,
  Loader2,
  MapPin,
  Repeat,
  Users,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card"
import { StatusPill } from "@/components/ui/status-pill"
import { useAuth } from "@/contexts/auth-context"
import {
  cancelCalendarEvent,
  getCalendarEvent,
  listEventAttendees,
  listEventLinkages,
  sendCalendarEvent,
  updateAttendeeResponse,
} from "@/services/calendar-account-service"
import type {
  CalendarEvent,
  CalendarEventAttendee,
  CalendarEventLinkage,
} from "@/types/calendar-account"
import { cn } from "@/lib/utils"


// ── Display helpers ─────────────────────────────────────────────────


function formatEventTime(startIso: string, endIso: string, isAllDay: boolean): {
  primary: string
  secondary: string
} {
  const start = new Date(startIso)
  const end = new Date(endIso)
  const dateFmt: Intl.DateTimeFormatOptions = {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }
  const timeFmt: Intl.DateTimeFormatOptions = {
    hour: "numeric",
    minute: "2-digit",
  }
  if (isAllDay) {
    return {
      primary: start.toLocaleDateString(undefined, dateFmt),
      secondary: "All day",
    }
  }
  const sameDay =
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth() &&
    start.getDate() === end.getDate()
  if (sameDay) {
    return {
      primary: start.toLocaleDateString(undefined, dateFmt),
      secondary: `${start.toLocaleTimeString(
        undefined,
        timeFmt,
      )} – ${end.toLocaleTimeString(undefined, timeFmt)}`,
    }
  }
  return {
    primary: `${start.toLocaleDateString(undefined, dateFmt)} ${start.toLocaleTimeString(undefined, timeFmt)}`,
    secondary: `→ ${end.toLocaleDateString(undefined, dateFmt)} ${end.toLocaleTimeString(undefined, timeFmt)}`,
  }
}


function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = then - now
  const min = Math.round(diff / 60_000)
  if (min < 0) {
    const past = Math.abs(min)
    if (past < 60) return `${past} min ago`
    const hr = Math.round(past / 60)
    if (hr < 24) return `${hr}h ago`
    const day = Math.round(hr / 24)
    if (day < 30) return `${day}d ago`
    return new Date(iso).toLocaleDateString()
  }
  if (min < 60) return `in ${min} min`
  const hr = Math.round(min / 60)
  if (hr < 24) return `in ${hr}h`
  const day = Math.round(hr / 24)
  return `in ${day}d`
}


/** Map attendee response_status → StatusFamily-compatible status string. */
function attendeeStatusKey(rs: string): string {
  switch (rs) {
    case "accepted":
      return "approved"
    case "declined":
      return "declined"
    case "tentative":
      return "pending"
    case "needs_action":
    default:
      return "info"
  }
}


/** Linked-entity render label. */
function linkageLabel(l: CalendarEventLinkage): string {
  // Future: per-entity-type display joined with the actual record;
  // Step 5 surfaces type + truncated id for traceability.
  const id = l.linked_entity_id.length > 12
    ? l.linked_entity_id.slice(0, 8) + "…"
    : l.linked_entity_id
  return `${l.linked_entity_type} · ${id}`
}


// ── Page component ──────────────────────────────────────────────────


export default function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const callerEmail = user?.email?.toLowerCase() ?? null

  const [event, setEvent] = useState<CalendarEvent | null>(null)
  const [attendees, setAttendees] = useState<CalendarEventAttendee[]>([])
  const [linkages, setLinkages] = useState<CalendarEventLinkage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionInFlight, setActionInFlight] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const reload = useCallback(async () => {
    if (!eventId) return
    setIsLoading(true)
    setError(null)
    try {
      const [ev, atts, lks] = await Promise.all([
        getCalendarEvent(eventId),
        listEventAttendees(eventId),
        listEventLinkages(eventId),
      ])
      setEvent(ev)
      setAttendees(atts)
      setLinkages(lks)
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(message ?? "Couldn't load event")
    } finally {
      setIsLoading(false)
    }
  }, [eventId])

  useEffect(() => {
    void reload()
  }, [reload])

  const myAttendee = useMemo(() => {
    if (!callerEmail) return null
    return (
      attendees.find((a) => a.email_address.toLowerCase() === callerEmail) ??
      null
    )
  }, [attendees, callerEmail])

  const otherAttendees = useMemo(() => {
    if (!myAttendee) return attendees
    return attendees.filter((a) => a.id !== myAttendee.id)
  }, [attendees, myAttendee])

  const isCancelled = event?.status === "cancelled"
  const isTentative = event?.status === "tentative"
  const isConfirmed = event?.status === "confirmed"

  const handleResponse = useCallback(
    async (response_status: "accepted" | "declined" | "tentative") => {
      if (!eventId || !myAttendee) return
      setActionInFlight(`response:${response_status}`)
      setActionMessage(null)
      try {
        await updateAttendeeResponse(eventId, myAttendee.id, {
          response_status,
        })
        await reload()
      } catch (err) {
        const message = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail
        setActionMessage(message ?? "Couldn't update response")
      } finally {
        setActionInFlight(null)
      }
    },
    [eventId, myAttendee, reload],
  )

  const handleSend = useCallback(async () => {
    if (!eventId) return
    setActionInFlight("send")
    setActionMessage(null)
    try {
      const result = await sendCalendarEvent(eventId)
      setActionMessage(
        `Sent invites to ${result.recipient_count} attendee${
          result.recipient_count === 1 ? "" : "s"
        }`,
      )
      await reload()
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setActionMessage(message ?? "Couldn't send event")
    } finally {
      setActionInFlight(null)
    }
  }, [eventId, reload])

  const handleCancel = useCallback(async () => {
    if (!eventId || !event) return
    if (
      !window.confirm(
        `Cancel "${event.subject || "this event"}"? Attendees will be notified.`,
      )
    ) {
      return
    }
    setActionInFlight("cancel")
    setActionMessage(null)
    try {
      const result = await cancelCalendarEvent(eventId)
      setActionMessage(
        `Cancelled · notified ${result.recipient_count} attendee${
          result.recipient_count === 1 ? "" : "s"
        }`,
      )
      await reload()
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setActionMessage(message ?? "Couldn't cancel event")
    } finally {
      setActionInFlight(null)
    }
  }, [event, eventId, reload])

  // ── Loading + error states ────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] gap-2 text-content-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="font-plex-sans text-body-sm">Loading event…</span>
      </div>
    )
  }

  if (error || !event) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/calendar")}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to calendar
        </Button>
        <Card>
          <CardContent className="py-8 text-center">
            <p className="font-plex-sans text-body text-content-strong">
              {error ?? "Event not found"}
            </p>
            <p className="font-plex-sans text-caption text-content-muted mt-2">
              The event may have been deleted or you may not have access to
              its calendar account.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const time = formatEventTime(event.start_at, event.end_at, event.is_all_day)

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-4">
      {/* Back link */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/calendar")}
        className="-ml-2"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to calendar
      </Button>

      {/* Action message banner (success / failure of last action) */}
      {actionMessage && (
        <div
          className={cn(
            "rounded-md border px-4 py-2 text-body-sm",
            "border-status-info bg-status-info-muted text-status-info",
          )}
          role="status"
          data-testid="event-detail-action-message"
        >
          {actionMessage}
        </div>
      )}

      {/* Cancelled banner */}
      {isCancelled && (
        <div
          className={cn(
            "rounded-md border px-4 py-2 text-body-sm",
            "border-status-error bg-status-error-muted text-status-error",
          )}
          data-testid="event-detail-cancelled-banner"
        >
          This event was cancelled.
        </div>
      )}

      {/* Pattern 2 main card */}
      <Card data-testid="event-detail-card">
        {/* Subject + time strip */}
        <CardHeader className="border-b border-border-subtle pb-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1
                className="font-plex-serif text-h2 text-content-strong leading-tight break-words"
                data-testid="event-detail-subject"
              >
                {event.subject || "(No subject)"}
              </h1>
              <p className="font-plex-sans text-body text-content-base mt-2">
                {time.primary}
              </p>
              <p className="font-plex-mono text-body-sm text-content-muted tabular-nums">
                {time.secondary}
                <span className="mx-2 text-content-subtle">·</span>
                <span className="text-content-subtle">
                  {relativeTime(event.start_at)}
                </span>
              </p>
            </div>
            <StatusPill
              status={event.status}
              size="md"
              data-testid="event-detail-status"
            />
          </div>
        </CardHeader>

        <CardContent className="pt-4 space-y-4">
          {/* Metadata strip */}
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-2 text-body-sm text-content-muted"
            data-testid="event-detail-metadata"
          >
            {event.location && (
              <span className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-content-subtle" aria-hidden />
                <span className="text-content-base">{event.location}</span>
              </span>
            )}
            {event.is_cross_tenant && (
              <span
                className="flex items-center gap-1.5 text-accent"
                data-testid="event-detail-cross-tenant"
              >
                <Globe className="h-4 w-4" aria-hidden />
                <span>Cross-tenant event</span>
              </span>
            )}
            {event.transparency === "transparent" && (
              <span className="text-content-subtle italic">Free</span>
            )}
            {attendees.length > 0 && (
              <span className="flex items-center gap-1.5">
                <Users className="h-4 w-4 text-content-subtle" aria-hidden />
                <span>
                  {attendees.length} attendee
                  {attendees.length === 1 ? "" : "s"}
                </span>
              </span>
            )}
          </div>

          {/* Recurrence section — conditional */}
          {event.recurrence_rule && (
            <section
              className="border-t border-border-subtle pt-4"
              data-testid="event-detail-recurrence"
            >
              <h2 className="text-micro uppercase tracking-wider text-content-muted mb-2 flex items-center gap-1.5">
                <Repeat className="h-3.5 w-3.5" aria-hidden />
                Recurrence
              </h2>
              <p className="font-plex-mono text-body-sm text-content-base break-all">
                {event.recurrence_rule}
              </p>
            </section>
          )}

          {/* Description section — conditional */}
          {(event.description_text || event.description_html) && (
            <section
              className="border-t border-border-subtle pt-4"
              data-testid="event-detail-description"
            >
              <h2 className="text-micro uppercase tracking-wider text-content-muted mb-2">
                Description
              </h2>
              {event.description_html ? (
                <iframe
                  srcDoc={event.description_html}
                  sandbox=""
                  title="Event description"
                  className="w-full min-h-32 border border-border-subtle rounded-sm bg-surface-base"
                  data-testid="event-detail-description-html"
                />
              ) : (
                <p className="font-plex-sans text-body text-content-base whitespace-pre-wrap">
                  {event.description_text}
                </p>
              )}
            </section>
          )}

          {/* Attendees section */}
          <section
            className="border-t border-border-subtle pt-4"
            data-testid="event-detail-attendees"
          >
            <h2 className="text-micro uppercase tracking-wider text-content-muted mb-3 flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5" aria-hidden />
              Attendees
            </h2>
            {attendees.length === 0 ? (
              <p className="font-plex-sans text-caption text-content-muted italic">
                No attendees.
              </p>
            ) : (
              <ul className="space-y-2">
                {/* "You" row first with inline action buttons */}
                {myAttendee && (
                  <li
                    className={cn(
                      "rounded-sm border border-border-subtle bg-surface-elevated/50",
                      "px-3 py-2.5 flex flex-wrap items-center gap-3",
                    )}
                    data-testid="event-detail-you-row"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent text-content-on-accent font-plex-mono text-caption font-medium shrink-0">
                        Me
                      </span>
                      <div className="min-w-0">
                        <p className="font-plex-sans text-body-sm text-content-strong truncate">
                          You
                          <span className="text-content-muted font-normal ml-2">
                            ({myAttendee.email_address})
                          </span>
                        </p>
                        <p className="font-plex-sans text-caption text-content-muted">
                          {myAttendee.responded_at
                            ? `Last responded ${relativeTime(myAttendee.responded_at)}`
                            : "Awaiting your response"}
                        </p>
                      </div>
                    </div>
                    <div
                      className="flex items-center gap-1.5"
                      data-testid="event-detail-response-buttons"
                    >
                      <Button
                        type="button"
                        size="sm"
                        variant={
                          myAttendee.response_status === "accepted"
                            ? "default"
                            : "outline"
                        }
                        disabled={
                          isCancelled || actionInFlight === "response:accepted"
                        }
                        onClick={() => handleResponse("accepted")}
                        data-testid="event-detail-accept"
                      >
                        Accept
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant={
                          myAttendee.response_status === "tentative"
                            ? "default"
                            : "outline"
                        }
                        disabled={
                          isCancelled || actionInFlight === "response:tentative"
                        }
                        onClick={() => handleResponse("tentative")}
                        data-testid="event-detail-tentative"
                      >
                        Tentative
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant={
                          myAttendee.response_status === "declined"
                            ? "destructive"
                            : "outline"
                        }
                        disabled={
                          isCancelled || actionInFlight === "response:declined"
                        }
                        onClick={() => handleResponse("declined")}
                        data-testid="event-detail-decline"
                      >
                        Decline
                      </Button>
                    </div>
                  </li>
                )}
                {/* Other attendees */}
                {otherAttendees.map((a) => (
                  <li
                    key={a.id}
                    className={cn(
                      "rounded-sm px-3 py-2 flex items-center gap-3",
                      "hover:bg-surface-elevated/30 transition-colors duration-quick ease-settle",
                    )}
                    data-attendee-id={a.id}
                    data-response-status={a.response_status}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full shrink-0",
                        a.response_status === "accepted" && "bg-status-success",
                        a.response_status === "declined" && "bg-status-error",
                        a.response_status === "tentative" && "bg-status-warning",
                        a.response_status === "needs_action" &&
                          "bg-content-subtle",
                      )}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <p className="font-plex-sans text-body-sm text-content-base truncate">
                        {a.display_name || a.email_address}
                        {a.role === "organizer" && (
                          <span className="text-micro uppercase tracking-wider text-content-muted ml-2">
                            Organizer
                          </span>
                        )}
                      </p>
                      {a.display_name && (
                        <p className="font-plex-sans text-caption text-content-muted truncate">
                          {a.email_address}
                        </p>
                      )}
                    </div>
                    <StatusPill
                      status={attendeeStatusKey(a.response_status)}
                      size="sm"
                      label={a.response_status.replace("_", " ")}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Linked entities section */}
          {linkages.length > 0 && (
            <section
              className="border-t border-border-subtle pt-4"
              data-testid="event-detail-linkages"
            >
              <h2 className="text-micro uppercase tracking-wider text-content-muted mb-2 flex items-center gap-1.5">
                <LinkIcon className="h-3.5 w-3.5" aria-hidden />
                Linked entities
              </h2>
              <ul className="flex flex-wrap gap-1.5">
                {linkages.map((l) => (
                  <li
                    key={l.id}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-sm border",
                      "border-border-subtle bg-surface-elevated/40 px-2 py-1",
                      "font-plex-mono text-caption text-content-base",
                    )}
                    data-linkage-id={l.id}
                  >
                    {linkageLabel(l)}
                    {l.linkage_source === "intelligence_inferred" && (
                      <span className="text-content-subtle italic">
                        · auto
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </CardContent>

        {/* Action footer */}
        <CardFooter className="flex flex-wrap items-center gap-2 border-t border-border-subtle pt-4">
          {isTentative && (
            <Button
              type="button"
              size="sm"
              disabled={actionInFlight === "send"}
              onClick={handleSend}
              data-testid="event-detail-send"
            >
              <CheckCircle2 className="h-4 w-4 mr-2" aria-hidden />
              Send invites
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              // Edit + reschedule wizards live on the existing calendar
              // workspace surface; deep-link there with the event id.
              navigate(`/calendar?event=${event.id}&action=edit`)
            }}
            data-testid="event-detail-edit"
          >
            <CalendarIcon className="h-4 w-4 mr-2" aria-hidden />
            Edit event
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              navigate(`/calendar?event=${event.id}&action=reschedule`)
            }}
            data-testid="event-detail-reschedule"
          >
            <Repeat className="h-4 w-4 mr-2" aria-hidden />
            Reschedule
          </Button>
          {isConfirmed && (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={actionInFlight === "cancel"}
              onClick={handleCancel}
              data-testid="event-detail-cancel"
            >
              <X className="h-4 w-4 mr-2" aria-hidden />
              Cancel event
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}

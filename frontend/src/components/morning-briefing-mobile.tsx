// morning-briefing-mobile.tsx — Mobile swipeable card carousel briefing.
// One item per screen, swipe between. Mark done / snooze actions.

import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/auth-context"
import apiClient from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import {
  Check, ChevronRight, Clock, RefreshCw, List, X,
} from "lucide-react"
import { cn } from "@/lib/utils"

// ── Types (same as MorningBriefingCard) ─────────────────────────────────────

interface BriefingItem {
  number: number
  text: string
  priority: "critical" | "warning" | "info"
  related_entity_type?: string
  related_entity_hint?: string
}

interface BriefingResponse {
  content: string | null
  items: BriefingItem[]
  tier: "primary_area" | "executive" | "role_based"
  primary_area: string | null
  was_cached: boolean
  generated_at: string
  briefing_date: string
  reason?: string
}

interface AnnouncementItem {
  id: string
  title: string
  body: string | null
  priority: "info" | "warning" | "critical"
  content_type: string
  pin_to_top: boolean
  created_at: string | null
  is_read: boolean
  is_dismissed: boolean
  safety_category: string | null
  requires_acknowledgment: boolean
  acknowledgment_deadline: string | null
  is_acknowledged: boolean
  document_url: string | null
  document_filename: string | null
}

// Unified card item for the carousel
interface CarouselCard {
  id: string
  type: "briefing" | "announcement"
  // Briefing fields
  number?: number
  text: string
  priority: "critical" | "warning" | "info"
  primaryArea?: string | null
  relatedEntityType?: string
  relatedEntityHint?: string
  // Announcement fields
  announcementId?: string
  title?: string
  body?: string | null
  contentType?: string
  requiresAck?: boolean
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function isAfterNoon(): boolean {
  return new Date().getHours() >= 12
}

function formatDate(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}

// Sort by urgency for mobile: critical first, then warning, then info
function urgencySort(a: CarouselCard, b: CarouselCard): number {
  const order = { critical: 0, warning: 1, info: 2 }
  return order[a.priority] - order[b.priority]
}

function inferActionLink(
  text: string,
  primaryArea: string | null,
): { label: string; route: string } | null {
  const lower = text.toLowerCase()

  if (primaryArea === "funeral_scheduling") {
    if (lower.includes("unassigned") || lower.includes("no driver"))
      return { label: "Open scheduler", route: "/scheduling" }
    if (lower.includes("vault not") || lower.includes("inventory"))
      return { label: "Check inventory", route: "/inventory" }
    if (lower.includes("unscheduled order"))
      return { label: "View orders", route: "/orders?filter=unscheduled" }
    if (lower.includes("legacy") || lower.includes("proof"))
      return { label: "Review in Legacy Studio", route: "/legacy/library" }
  }

  if (primaryArea === "invoicing_ar") {
    if (lower.includes("overdue") || lower.includes("unpaid") || lower.includes("past due"))
      return { label: "View invoices", route: "/invoices?filter=overdue" }
    if (lower.includes("sync error") || lower.includes("not syncing"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" }
  }

  if (primaryArea === "safety_compliance") {
    if (lower.includes("inspection") || lower.includes("overdue"))
      return { label: "View safety", route: "/safety" }
    if (lower.includes("incident"))
      return { label: "View incidents", route: "/safety/incidents" }
  }

  if (primaryArea === "full_admin") {
    if (lower.includes("overdue") || lower.includes("unpaid"))
      return { label: "View AR", route: "/invoices?filter=overdue" }
    if (lower.includes("sync"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" }
  }

  return null
}

function priorityIcon(priority: string): string {
  if (priority === "critical") return "\u26a0\ufe0f"
  if (priority === "warning") return "\ud83d\udfe1"
  return "\u2139\ufe0f"
}

// ── Component ───────────────────────────────────────────────────────────────

export function MorningBriefingMobile() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState<BriefingResponse | null>(null)
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Card carousel state
  const [cards, setCards] = useState<CarouselCard[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set())
  const [snoozedIds, setSnoozedIds] = useState<Set<string>>(new Set())
  const [dismissAnim, setDismissAnim] = useState<string | null>(null)

  // Full list bottom sheet
  const [showList, setShowList] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)

  // Touch swipe state
  const touchStartRef = useRef<{ x: number; y: number } | null>(null)
  const swipeOffsetRef = useRef(0)
  const [swipeOffset, setSwipeOffset] = useState(0)

  // ── Data fetching ─────────────────────────────────────────────────────

  const fetchBriefing = useCallback(async () => {
    try {
      const res = await apiClient.get<BriefingResponse>("/briefings/briefing")
      setData(res.data)
    } catch {
      setData(null)
    }
  }, [])

  const fetchAnnouncements = useCallback(async () => {
    try {
      const res = await apiClient.get<AnnouncementItem[]>("/announcements/my")
      setAnnouncements(res.data)
    } catch {
      setAnnouncements([])
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      await Promise.all([fetchBriefing(), fetchAnnouncements()])
      if (!cancelled) setLoading(false)
    })()
    return () => { cancelled = true }
  }, [fetchBriefing, fetchAnnouncements])

  // Mark announcements as read
  useEffect(() => {
    announcements.forEach((a) => {
      if (!a.is_read) {
        apiClient.post(`/announcements/${a.id}/read`).catch(() => {})
      }
    })
  }, [announcements])

  // Build carousel cards from briefing items + announcements
  useEffect(() => {
    const result: CarouselCard[] = []

    // Add announcement cards (safety first)
    const safetyFirst = [...announcements].sort((a, b) => {
      const aReq = a.content_type === "safety_notice" && a.requires_acknowledgment && !a.is_acknowledged
      const bReq = b.content_type === "safety_notice" && b.requires_acknowledgment && !b.is_acknowledged
      if (aReq && !bReq) return -1
      if (!aReq && bReq) return 1
      return 0
    })

    for (const a of safetyFirst) {
      if (a.is_dismissed) continue
      result.push({
        id: `ann_${a.id}`,
        type: "announcement",
        text: a.body || a.title,
        priority: a.priority,
        title: a.title,
        body: a.body,
        announcementId: a.id,
        contentType: a.content_type,
        requiresAck: a.requires_acknowledgment && !a.is_acknowledged,
      })
    }

    // Add briefing item cards
    if (data && data.items.length > 0) {
      for (const item of data.items) {
        result.push({
          id: `item_${item.number}`,
          type: "briefing",
          number: item.number,
          text: item.text,
          priority: item.priority,
          primaryArea: data.primary_area,
          relatedEntityType: item.related_entity_type,
          relatedEntityHint: item.related_entity_hint,
        })
      }
    } else if (data && data.content && data.tier === "role_based") {
      // Role-based: single paragraph card
      result.push({
        id: "role_narrative",
        type: "briefing",
        text: data.content,
        priority: "info",
        primaryArea: data.primary_area,
      })
    }

    // Sort briefing items by urgency
    const annCards = result.filter((c) => c.type === "announcement")
    const briefCards = result.filter((c) => c.type === "briefing").sort(urgencySort)
    setCards([...annCards, ...briefCards])
    setCurrentIndex(0)
  }, [data, announcements])

  // ── Card actions ──────────────────────────────────────────────────────

  function markDone(cardId: string) {
    setDismissAnim(cardId)
    setTimeout(() => {
      setDoneIds((prev) => new Set(prev).add(cardId))
      setDismissAnim(null)
      // Move to next visible card
      const visibleCards = cards.filter(
        (c) => !doneIds.has(c.id) && !snoozedIds.has(c.id) && c.id !== cardId,
      )
      if (visibleCards.length > 0) {
        const nextIdx = Math.min(currentIndex, visibleCards.length - 1)
        setCurrentIndex(nextIdx)
      }
      // If it's an announcement, dismiss via API too
      const card = cards.find((c) => c.id === cardId)
      if (card?.announcementId) {
        apiClient.post(`/announcements/${card.announcementId}/dismiss`).catch(() => {})
      }
    }, 300)
  }

  function snoozeCard(cardId: string) {
    setSnoozedIds((prev) => new Set(prev).add(cardId))
    // Un-snooze after 2 hours
    setTimeout(
      () => {
        setSnoozedIds((prev) => {
          const next = new Set(prev)
          next.delete(cardId)
          return next
        })
      },
      2 * 60 * 60 * 1000,
    )
    // Move to next visible card
    const visibleCards = cards.filter(
      (c) => !doneIds.has(c.id) && !snoozedIds.has(c.id) && c.id !== cardId,
    )
    if (visibleCards.length > 0) {
      setCurrentIndex(Math.min(currentIndex, visibleCards.length - 1))
    }
  }

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const res = await apiClient.post<BriefingResponse>("/briefings/briefing/refresh")
      setData(res.data)
      setDoneIds(new Set())
      setSnoozedIds(new Set())
    } catch {
      // silent
    } finally {
      setRefreshing(false)
    }
  }

  // ── Touch swipe handlers ──────────────────────────────────────────────

  function handleTouchStart(e: React.TouchEvent) {
    touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
    swipeOffsetRef.current = 0
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (!touchStartRef.current) return
    const dx = e.touches[0].clientX - touchStartRef.current.x
    swipeOffsetRef.current = dx
    setSwipeOffset(dx)
  }

  function handleTouchEnd() {
    const threshold = 60
    if (swipeOffsetRef.current < -threshold && currentIndex < visibleCards.length - 1) {
      setCurrentIndex((i) => i + 1)
    } else if (swipeOffsetRef.current > threshold && currentIndex > 0) {
      setCurrentIndex((i) => i - 1)
    }
    touchStartRef.current = null
    swipeOffsetRef.current = 0
    setSwipeOffset(0)
  }

  // ── Derived data ──────────────────────────────────────────────────────

  const visibleCards = cards.filter(
    (c) => !doneIds.has(c.id) && !snoozedIds.has(c.id),
  )
  const processedCount = doneIds.size + snoozedIds.size
  const totalCount = cards.length
  const allDone = visibleCards.length === 0 && totalCount > 0
  const currentCard = visibleCards[currentIndex] || null

  const firstName = user?.first_name || "there"
  const greeting = isAfterNoon() ? "Good afternoon" : "Good morning"

  // ── Loading state ─────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="space-y-1">
          <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-32 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="bg-white rounded-2xl border p-6 space-y-4">
          <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-4/5 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-3/5 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>
    )
  }

  // No briefing data at all
  if (!data && announcements.length === 0) return null

  // ── All done state ────────────────────────────────────────────────────

  if (allDone) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">
            {greeting}, {firstName}
          </h2>
          <p className="text-sm text-gray-500">{formatDate()}</p>
        </div>

        <div className="bg-white rounded-2xl border p-8 text-center space-y-3">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 mb-2">
            <Check className="h-6 w-6 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">All caught up</h3>
          <p className="text-sm text-gray-500">
            {greeting}, {firstName}. You're all set for today.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => { setDoneIds(new Set()); setSnoozedIds(new Set()); setCurrentIndex(0) }}
          >
            View full briefing
          </Button>
        </div>
      </div>
    )
  }

  // ── Card carousel ─────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">
            {greeting}, {firstName}
          </h2>
          <p className="text-sm text-gray-500">{formatDate()}</p>
          {totalCount > 0 && (
            <p className="text-xs text-gray-400 mt-1">
              {totalCount - processedCount} of {totalCount} items to process
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="h-8 text-xs text-gray-500 gap-1"
        >
          <RefreshCw className={cn("h-3 w-3", refreshing && "animate-spin")} />
        </Button>
      </div>

      {/* Progress dots */}
      {totalCount > 1 && (
        <div className="flex items-center gap-1.5 justify-center">
          {cards.map((card) => {
            const isDone = doneIds.has(card.id)
            const isSnoozed = snoozedIds.has(card.id)
            const visibleIdx = visibleCards.indexOf(card)
            const isCurrent = visibleIdx === currentIndex
            return (
              <div
                key={card.id}
                className={cn(
                  "h-2 rounded-full transition-all duration-200",
                  isDone
                    ? "w-2 bg-green-400"
                    : isSnoozed
                      ? "w-2 bg-gray-300"
                      : isCurrent
                        ? "w-4 bg-blue-500"
                        : "w-2 bg-gray-300",
                )}
              />
            )
          })}
        </div>
      )}

      {/* Card */}
      {currentCard && (
        <div
          ref={containerRef}
          className="overflow-hidden"
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          <div
            className={cn(
              "bg-white rounded-2xl border shadow-sm p-5 space-y-4 transition-all duration-300",
              dismissAnim === currentCard.id && "opacity-0 -translate-x-full",
            )}
            style={{
              transform: dismissAnim ? undefined : `translateX(${swipeOffset * 0.4}px)`,
            }}
          >
            {/* Priority badge */}
            <div className="flex items-center gap-2">
              <span className="text-sm">{priorityIcon(currentCard.priority)}</span>
              {currentCard.type === "announcement" ? (
                <span
                  className={cn(
                    "text-xs font-semibold uppercase tracking-wider",
                    currentCard.priority === "critical" && "text-red-600",
                    currentCard.priority === "warning" && "text-amber-600",
                    currentCard.priority === "info" && "text-blue-600",
                  )}
                >
                  {currentCard.contentType === "safety_notice" ? "Safety Notice" : "Announcement"}
                </span>
              ) : (
                <span
                  className={cn(
                    "text-xs font-semibold uppercase tracking-wider",
                    currentCard.priority === "critical" && "text-red-600",
                    currentCard.priority === "warning" && "text-amber-600",
                    currentCard.priority === "info" && "text-blue-600",
                  )}
                >
                  {currentCard.priority === "critical"
                    ? "Action Required"
                    : currentCard.priority === "warning"
                      ? "Attention"
                      : "Info"}
                </span>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                {currentIndex + 1}/{visibleCards.length}
              </span>
            </div>

            {/* Title for announcements */}
            {currentCard.title && currentCard.type === "announcement" && (
              <h3 className="text-lg font-semibold text-gray-900">
                {currentCard.title}
              </h3>
            )}

            {/* Body text */}
            <p className="text-base text-gray-700 leading-relaxed">
              {currentCard.text}
            </p>

            {/* Primary action button */}
            {currentCard.type === "briefing" && (() => {
              const action = inferActionLink(currentCard.text, currentCard.primaryArea || null)
              if (!action) return null
              return (
                <Button
                  className="w-full"
                  onClick={() => navigate(action.route)}
                >
                  {action.label} <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              )
            })()}

            {currentCard.requiresAck && (
              <Button
                className="w-full bg-amber-600 hover:bg-amber-700 text-white"
                onClick={() => {
                  if (currentCard.announcementId) {
                    apiClient
                      .post(`/announcements/${currentCard.announcementId}/acknowledge`, { note: null })
                      .then(() => markDone(currentCard.id))
                      .catch(() => {})
                  }
                }}
              >
                <Check className="h-4 w-4 mr-1" /> I have read and understood this
              </Button>
            )}

            {/* Mark done / Snooze */}
            <div className="flex gap-2">
              {!currentCard.requiresAck && (
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => markDone(currentCard.id)}
                >
                  <Check className="h-4 w-4 mr-1" /> Done
                </Button>
              )}
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => snoozeCard(currentCard.id)}
              >
                <Clock className="h-4 w-4 mr-1" /> Snooze 2h
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Swipe hint */}
      {visibleCards.length > 1 && (
        <p className="text-[10px] text-gray-400 text-center">
          Swipe left/right between items
        </p>
      )}

      {/* View all as list */}
      <button
        onClick={() => setShowList(true)}
        className="flex items-center justify-center gap-1.5 text-xs text-gray-500 mx-auto"
      >
        <List className="h-3 w-3" /> View all as list
      </button>

      {/* ── Full list bottom sheet ───────────────────────────────────── */}
      {showList && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowList(false)} />
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl animate-in slide-in-from-bottom duration-200 max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b sticky top-0 bg-white z-10">
              <h3 className="font-semibold text-sm">All briefing items</h3>
              <button onClick={() => setShowList(false)}>
                <X className="h-5 w-5 text-gray-400" />
              </button>
            </div>
            <div className="px-4 py-3 space-y-2">
              {cards.map((card) => {
                const isDone = doneIds.has(card.id)
                const isSnoozed = snoozedIds.has(card.id)
                return (
                  <div
                    key={card.id}
                    className={cn(
                      "flex items-start gap-3 p-3 rounded-lg border",
                      isDone && "opacity-40 line-through",
                      isSnoozed && "opacity-50",
                      card.priority === "critical" && "border-l-2 border-l-red-500",
                      card.priority === "warning" && "border-l-2 border-l-amber-500",
                    )}
                  >
                    <span className="text-sm mt-0.5">{priorityIcon(card.priority)}</span>
                    <div className="flex-1 min-w-0">
                      {card.title && card.type === "announcement" && (
                        <p className="text-sm font-semibold text-gray-900">{card.title}</p>
                      )}
                      <p className="text-sm text-gray-700">{card.text}</p>
                      {isDone && (
                        <span className="text-[10px] text-green-600 font-medium">Done</span>
                      )}
                      {isSnoozed && (
                        <span className="text-[10px] text-amber-600 font-medium">Snoozed</span>
                      )}
                    </div>
                    {!isDone && !isSnoozed && (
                      <button
                        onClick={() => {
                          markDone(card.id)
                          // Jump to this card in carousel
                          const idx = visibleCards.indexOf(card)
                          if (idx >= 0) setCurrentIndex(idx)
                        }}
                        className="text-xs text-blue-600 shrink-0"
                      >
                        Done
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="h-8" />
          </div>
        </div>
      )}
    </div>
  )
}

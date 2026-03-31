// ops-context-card.tsx
// Fetches and displays the daily Operations Board context card.
// Caches in sessionStorage for 30 minutes; dismissable per-day via localStorage.

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import apiClient from '@/lib/api-client'

// ── Types ────────────────────────────────────────────────────────────────────

interface ContextItem {
  type: string
  message: string
  action_label: string
  action_url: string
}

interface DailyContext {
  greeting: string
  priority_message: string
  items: ContextItem[]
  generated_at: string
}

// ── Cache helpers ─────────────────────────────────────────────────────────────

const SESSION_KEY = 'ops-daily-context'
const CACHE_TTL_MS = 30 * 60 * 1000 // 30 minutes

interface CachedEntry {
  data: DailyContext
  fetchedAt: number
}

function readCache(): DailyContext | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const entry: CachedEntry = JSON.parse(raw)
    if (Date.now() - entry.fetchedAt > CACHE_TTL_MS) {
      sessionStorage.removeItem(SESSION_KEY)
      return null
    }
    return entry.data
  } catch {
    return null
  }
}

function writeCache(data: DailyContext): void {
  try {
    const entry: CachedEntry = { data, fetchedAt: Date.now() }
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(entry))
  } catch {
    // sessionStorage may be unavailable (private mode quota, etc.) — ignore
  }
}

// ── Dismiss helpers ───────────────────────────────────────────────────────────

function todayString(): string {
  return new Date().toISOString().slice(0, 10) // "YYYY-MM-DD"
}

function dismissKey(): string {
  return `ops-context-dismissed-${todayString()}`
}

function isDismissedToday(): boolean {
  try {
    return localStorage.getItem(dismissKey()) === 'true'
  } catch {
    return false
  }
}

function markDismissedToday(): void {
  try {
    localStorage.setItem(dismissKey(), 'true')
  } catch {
    // localStorage unavailable — ignore
  }
}

// ── Offline greeting ──────────────────────────────────────────────────────────

function timeBasedGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ContextSkeleton() {
  return (
    <div className="mobile-card bg-amber-50 border border-amber-200 animate-pulse">
      <div className="h-5 w-36 rounded bg-amber-200 mb-3" />
      <div className="h-4 w-full rounded bg-amber-100 mb-2" />
      <div className="h-4 w-3/4 rounded bg-amber-100 mb-4" />
      <div className="flex gap-2">
        <div className="h-7 w-24 rounded-full bg-amber-100" />
        <div className="h-7 w-28 rounded-full bg-amber-100" />
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function OpsContextCard({ className }: { className?: string }) {
  const navigate = useNavigate()
  const [context, setContext] = useState<DailyContext | null>(null)
  const [loading, setLoading] = useState(true)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    // Check dismiss state first
    if (isDismissedToday()) {
      setDismissed(true)
      setLoading(false)
      return
    }

    // Try sessionStorage cache
    const cached = readCache()
    if (cached) {
      setContext(cached)
      setLoading(false)
      return
    }

    // Fetch from API
    apiClient
      .get<DailyContext>('/operations-board/daily-context')
      .then((res) => {
        writeCache(res.data)
        setContext(res.data)
      })
      .catch(() => {
        // Offline or server error — fall back to time-based greeting
        setContext({
          greeting: timeBasedGreeting(),
          priority_message: '',
          items: [],
          generated_at: new Date().toISOString(),
        })
      })
      .finally(() => setLoading(false))
  }, [])

  function handleDismiss() {
    markDismissedToday()
    setDismissed(true)
  }

  // Don't render anything once dismissed
  if (dismissed) return null

  if (loading) return <ContextSkeleton />

  if (!context) return null

  return (
    <div
      className={cn(
        'mobile-card bg-amber-50 border border-amber-200 relative',
        className,
      )}
    >
      {/* Header row: greeting + dismiss button */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <h2 className="text-lg font-semibold text-gray-800 leading-tight">
          {context.greeting}
        </h2>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss context card"
          className="mt-0.5 flex-shrink-0 rounded-full p-1 text-gray-400 hover:bg-amber-200 hover:text-gray-600 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Priority message */}
      {context.priority_message && (
        <p className="text-base text-gray-700 mb-4 leading-snug">
          {context.priority_message}
        </p>
      )}

      {/* Action items as chips */}
      {context.items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {context.items.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                if (item.action_url) navigate(item.action_url)
              }}
              className="bg-white border border-amber-300 rounded-full px-3 py-1 text-sm text-gray-700 font-medium hover:bg-amber-100 active:scale-95 transition-all"
            >
              {item.action_label || item.message}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

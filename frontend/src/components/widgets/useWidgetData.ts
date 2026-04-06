// useWidgetData — data fetching hook for widgets with auto-refresh

import { useState, useEffect, useCallback, useRef } from "react"
import apiClient from "@/lib/api-client"

interface UseWidgetDataOptions {
  /** Auto-refresh interval in ms. 0 = no auto-refresh. */
  refreshInterval?: number
  /** Don't fetch automatically on mount */
  manual?: boolean
}

interface UseWidgetDataResult<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  refresh: () => void
  lastUpdated: Date | null
}

export function useWidgetData<T = unknown>(
  url: string,
  options: UseWidgetDataOptions = {}
): UseWidgetDataResult<T> {
  const { refreshInterval = 0, manual = false } = options
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(!manual)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await apiClient.get<T>(url)
      if (mountedRef.current) {
        setData(res.data)
        setLastUpdated(new Date())
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        const msg =
          err instanceof Error
            ? err.message
            : "Failed to load data"
        setError(msg)
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [url])

  // Initial fetch
  useEffect(() => {
    mountedRef.current = true
    if (!manual) fetchData()
    return () => {
      mountedRef.current = false
    }
  }, [fetchData, manual])

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval > 0) {
      intervalRef.current = setInterval(fetchData, refreshInterval)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [refreshInterval, fetchData])

  return { data, isLoading, error, refresh: fetchData, lastUpdated }
}

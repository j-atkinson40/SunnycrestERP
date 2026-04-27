// useDashboard — hook that manages dashboard state for any page context

import { useState, useEffect, useCallback, useRef } from "react"
import apiClient from "@/lib/api-client"
import type { WidgetDefinition, WidgetLayoutItem, WidgetLayout } from "./types"

export function useDashboard(pageContext: string) {
  const [layout, setLayout] = useState<WidgetLayoutItem[]>([])
  const [available, setAvailable] = useState<WidgetDefinition[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [editMode, setEditMode] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load layout and available widgets
  const loadData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [layoutRes, availableRes] = await Promise.all([
        apiClient.get<WidgetLayout>("/widgets/layout", {
          params: { page_context: pageContext },
        }),
        apiClient.get<WidgetDefinition[]>("/widgets/available", {
          params: { page_context: pageContext },
        }),
      ])
      setLayout(layoutRes.data.widgets || [])
      setAvailable(availableRes.data)
    } catch (err) {
      console.error("Failed to load dashboard layout:", err)
    } finally {
      setIsLoading(false)
    }
  }, [pageContext])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Debounced save to API
  const debouncedSave = useCallback(
    (widgets: WidgetLayoutItem[]) => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = setTimeout(async () => {
        setIsSaving(true)
        try {
          const stripped = widgets.map((w) => ({
            widget_id: w.widget_id,
            enabled: w.enabled,
            position: w.position,
            size: w.size,
            config: w.config || {},
          }))
          await apiClient.patch(
            "/widgets/layout",
            { widgets: stripped },
            { params: { page_context: pageContext } }
          )
          setLastSaved(new Date())
        } catch (err) {
          console.error("Failed to save layout:", err)
        } finally {
          setIsSaving(false)
        }
      }, 500)
    },
    [pageContext]
  )

  const addWidget = useCallback(
    (widgetId: string) => {
      const defn = available.find((w) => w.widget_id === widgetId)
      if (!defn) return

      const maxPos = Math.max(0, ...layout.map((w) => w.position))
      const newItem: WidgetLayoutItem = {
        widget_id: widgetId,
        enabled: true,
        position: maxPos + 1,
        size: defn.default_size,
        config: defn.default_config as Record<string, unknown> ?? {},
        // Widget Library Phase W-1 — Section 12.3: per-instance
        // variant selection. Defaults to the widget's declared
        // default_variant_id when adding to dashboard. User can
        // resize-to-variant-swap (Phase W-3+) or pick a different
        // variant via the catalog UI.
        variant_id: defn.default_variant_id,
        title: defn.title,
        description: defn.description,
        icon: defn.icon,
        category: defn.category,
        supported_sizes: defn.supported_sizes,
        required_extension: defn.required_extension,
      }
      const updated = [...layout, newItem]
      setLayout(updated)
      debouncedSave(updated)
    },
    [layout, available, debouncedSave]
  )

  const removeWidget = useCallback(
    (widgetId: string) => {
      const updated = layout.map((w) =>
        w.widget_id === widgetId ? { ...w, enabled: false } : w
      )
      setLayout(updated)
      debouncedSave(updated)
    },
    [layout, debouncedSave]
  )

  const reorderWidgets = useCallback(
    (orderedIds: string[]) => {
      const updated = layout.map((w) => {
        const idx = orderedIds.indexOf(w.widget_id)
        return idx >= 0 ? { ...w, position: idx + 1 } : w
      })
      // Sort by new position
      updated.sort((a, b) => a.position - b.position)
      setLayout(updated)
      debouncedSave(updated)
    },
    [layout, debouncedSave]
  )

  const resizeWidget = useCallback(
    (widgetId: string, size: string) => {
      const updated = layout.map((w) =>
        w.widget_id === widgetId ? { ...w, size } : w
      )
      setLayout(updated)
      debouncedSave(updated)
    },
    [layout, debouncedSave]
  )

  const resetLayout = useCallback(async () => {
    try {
      await apiClient.post("/widgets/layout/reset", null, {
        params: { page_context: pageContext },
      })
      await loadData()
    } catch (err) {
      console.error("Failed to reset layout:", err)
    }
  }, [pageContext, loadData])

  return {
    layout,
    available,
    isLoading,
    editMode,
    setEditMode,
    addWidget,
    removeWidget,
    reorderWidgets,
    resizeWidget,
    resetLayout,
    isSaving,
    lastSaved,
    reload: loadData,
  }
}

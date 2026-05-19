/**
 * Placeholder widgets for the Focus Builder palette — sub-arc F-3.
 *
 * These are deliberately INERT placeholder renders. They exist so that
 * F-3 can demonstrate the widget palette + drag-to-canvas + placement
 * editing infrastructure end-to-end without binding to real data
 * sources. Real implementations (with live data fetches, status logic,
 * vertical-specific behavior) ship in later vertical-specific arcs.
 *
 * Each renders a frosted/elevated card with name + lucide icon +
 * one-line description so it reads correctly when dropped on the
 * canvas during F-3 demos.
 */
import * as React from "react"
import { CalendarDays, Map, Pin } from "lucide-react"

export interface PlaceholderWidgetProps {
  /** Optional density / sizing prop demonstrating the registration's
   * configurableProps surface. Inert visually in F-3. */
  daysVisible?: number
  showCount?: boolean
  zoom?: number
}

const baseStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  justifyContent: "center",
  gap: 6,
  padding: "12px 16px",
  borderRadius: 12,
  background: "var(--surface-elevated, rgba(255,255,255,0.65))",
  border: "1px solid var(--border-subtle, rgba(0,0,0,0.06))",
  boxShadow: "var(--shadow-level-1, 0 1px 2px rgba(0,0,0,0.06))",
  width: "100%",
  height: "100%",
  minHeight: 56,
}

function PlaceholderShell({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div style={baseStyle} data-placeholder-widget="true">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          color: "var(--content-strong, #1a1a1a)",
          fontSize: 12,
          fontWeight: 600,
          fontFamily: "var(--font-plex-sans)",
        }}
      >
        {icon}
        <span>{title}</span>
      </div>
      <p
        style={{
          margin: 0,
          color: "var(--content-muted, #6a6a6a)",
          fontSize: 11,
          fontFamily: "var(--font-plex-sans)",
        }}
      >
        {description}
      </p>
    </div>
  )
}

export function DayStripWidget(_props: PlaceholderWidgetProps) {
  return (
    <PlaceholderShell
      icon={<CalendarDays size={14} aria-hidden />}
      title="Day Strip"
      description="Seven-day strip with today highlighted"
    />
  )
}

export function TodayPinWidget(_props: PlaceholderWidgetProps) {
  return (
    <PlaceholderShell
      icon={<Pin size={14} aria-hidden />}
      title="Today Pin"
      description="Pinned summary of today's items"
    />
  )
}

export function MapPlaceholderWidget(_props: PlaceholderWidgetProps) {
  return (
    <PlaceholderShell
      icon={<Map size={14} aria-hidden />}
      title="Map"
      description="Geographic context for placements"
    />
  )
}

export default {
  DayStripWidget,
  TodayPinWidget,
  MapPlaceholderWidget,
}

/**
 * Focus family icons (r122) — the curated set + name→component lookup.
 *
 * The icon is FAMILY IDENTITY: each Tier 1 core wears a distinct mark and
 * every variation renders its lineage ROOT core's CURRENT icon (resolved
 * server-side at read — inherited, never copied, not overridable
 * downstream). A glance at any focus pill answers "what kind of focus is
 * this." The map's keys ARE the picker's choices (single source); unknown
 * names fall back to the generic Focus glyph rather than breaking.
 */

import {
  BookOpen,
  Calendar,
  ClipboardCheck,
  FileText,
  Focus,
  Gavel,
  HeartHandshake,
  Kanban,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Package,
  Scale,
  Sparkles,
  Target,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react"

/** The curated set — keys are the persisted names (focus_cores.icon). */
export const FOCUS_ICON_MAP: Record<string, LucideIcon> = {
  kanban: Kanban,
  scale: Scale,
  sparkles: Sparkles,
  users: Users,
  calendar: Calendar,
  "list-checks": ListChecks,
  gavel: Gavel,
  "clipboard-check": ClipboardCheck,
  "file-text": FileText,
  "layout-dashboard": LayoutDashboard,
  "message-square": MessageSquare,
  package: Package,
  truck: Truck,
  "heart-handshake": HeartHandshake,
  "book-open": BookOpen,
  target: Target,
}

export const FOCUS_ICON_NAMES = Object.keys(FOCUS_ICON_MAP)

/** Resolve a persisted name → component; null/unknown → the generic glyph. */
export function focusIcon(name: string | null | undefined): LucideIcon {
  return (name && FOCUS_ICON_MAP[name]) || Focus
}

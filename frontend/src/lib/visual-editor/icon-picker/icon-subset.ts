/**
 * Arc 4a.1 — Curated lucide icon subset for IconPicker.
 *
 * Subset rationale: aggregate of icons-already-in-use across the platform
 * (RegisteredButton ICON_MAP, ButtonPicker ICON_MAP, DotNav space icons,
 * widget metadata, sidebar nav) PLUS commonly-needed extensions to round
 * out the authoring surface (Edit / Trash / Plus / X / Check / Save /
 * Calendar / Bell / FileText / DollarSign / etc).
 *
 * Target ~40 icons — narrow enough to scan visually in a grid, broad
 * enough to cover the canonical action vocabulary admins reach for when
 * authoring R-4 buttons or future class-level icon configs.
 *
 * Free-form text fallback in IconPicker preserves the existing R4 contract
 * — admins can still type any valid lucide-react export name not in the
 * subset; IconPicker renders it via the same resolution path.
 *
 * Extending the subset: append the named import + IconSubsetEntry below.
 * Lucide's tree-shaking keeps the bundle bounded to icons-actually-imported.
 */

import {
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowLeftRight,
  ArrowRight,
  Bell,
  Box,
  Calendar,
  CalendarPlus,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Copy,
  DollarSign,
  Download,
  Edit,
  ExternalLink,
  Eye,
  FileText,
  Filter,
  Flag,
  Home,
  Info,
  type LucideIcon,
  Mail,
  MapPin,
  MessageSquare,
  MoreHorizontal,
  Phone,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings,
  Share2,
  ShoppingCart,
  Star,
  Trash2,
  Truck,
  Upload,
  User,
  UserPlus,
  Workflow,
  X,
} from "lucide-react"


export interface IconSubsetEntry {
  /** lucide-react export name (case-sensitive). Stored as-is in
   *  `iconName` configurable props. */
  name: string
  /** Resolved component reference for grid rendering. */
  Icon: LucideIcon
  /** Optional group label for organizing the picker grid into
   *  scannable clusters. */
  group?: "actions" | "navigation" | "objects" | "status" | "misc"
}


/** The canonical curated subset. ~40 icons across 5 groups. */
export const ICON_SUBSET: IconSubsetEntry[] = [
  // ── Actions (10) — primary verbs admins reach for first ────────
  { name: "Plus", Icon: Plus, group: "actions" },
  { name: "Edit", Icon: Edit, group: "actions" },
  { name: "Trash2", Icon: Trash2, group: "actions" },
  { name: "Check", Icon: Check, group: "actions" },
  { name: "X", Icon: X, group: "actions" },
  { name: "Save", Icon: Save, group: "actions" },
  { name: "Send", Icon: Send, group: "actions" },
  { name: "Copy", Icon: Copy, group: "actions" },
  { name: "Download", Icon: Download, group: "actions" },
  { name: "Upload", Icon: Upload, group: "actions" },

  // ── Navigation (8) — wayfinding + flow ──────────────────────────
  { name: "Home", Icon: Home, group: "navigation" },
  { name: "ArrowRight", Icon: ArrowRight, group: "navigation" },
  { name: "ChevronRight", Icon: ChevronRight, group: "navigation" },
  { name: "ArrowLeftRight", Icon: ArrowLeftRight, group: "navigation" },
  { name: "ExternalLink", Icon: ExternalLink, group: "navigation" },
  { name: "Search", Icon: Search, group: "navigation" },
  { name: "Filter", Icon: Filter, group: "navigation" },
  { name: "MoreHorizontal", Icon: MoreHorizontal, group: "navigation" },

  // ── Objects (12) — domain entities + content types ─────────────
  { name: "FileText", Icon: FileText, group: "objects" },
  { name: "Calendar", Icon: Calendar, group: "objects" },
  { name: "CalendarPlus", Icon: CalendarPlus, group: "objects" },
  { name: "Mail", Icon: Mail, group: "objects" },
  { name: "Phone", Icon: Phone, group: "objects" },
  { name: "MessageSquare", Icon: MessageSquare, group: "objects" },
  { name: "User", Icon: User, group: "objects" },
  { name: "UserPlus", Icon: UserPlus, group: "objects" },
  { name: "ShoppingCart", Icon: ShoppingCart, group: "objects" },
  { name: "Truck", Icon: Truck, group: "objects" },
  { name: "Box", Icon: Box, group: "objects" },
  { name: "DollarSign", Icon: DollarSign, group: "objects" },

  // ── Status (8) — signals + flags ────────────────────────────────
  { name: "AlertTriangle", Icon: AlertTriangle, group: "status" },
  { name: "AlertCircle", Icon: AlertCircle, group: "status" },
  { name: "Info", Icon: Info, group: "status" },
  { name: "CheckCircle2", Icon: CheckCircle2, group: "status" },
  { name: "Bell", Icon: Bell, group: "status" },
  { name: "Flag", Icon: Flag, group: "status" },
  { name: "Star", Icon: Star, group: "status" },
  { name: "Clock", Icon: Clock, group: "status" },

  // ── Misc (6) — common platform glue ─────────────────────────────
  { name: "Workflow", Icon: Workflow, group: "misc" },
  { name: "Settings", Icon: Settings, group: "misc" },
  { name: "Eye", Icon: Eye, group: "misc" },
  { name: "RefreshCw", Icon: RefreshCw, group: "misc" },
  { name: "Share2", Icon: Share2, group: "misc" },
  { name: "MapPin", Icon: MapPin, group: "misc" },
  { name: "Archive", Icon: Archive, group: "misc" },
]


/** O(1) lookup by lucide name. */
export const ICON_SUBSET_MAP: Record<string, LucideIcon> =
  Object.fromEntries(ICON_SUBSET.map((e) => [e.name, e.Icon]))


/** Canonical group order for grid rendering. */
export const ICON_GROUPS: ReadonlyArray<NonNullable<IconSubsetEntry["group"]>> =
  ["actions", "navigation", "objects", "status", "misc"] as const


export const ICON_GROUP_LABELS: Record<
  NonNullable<IconSubsetEntry["group"]>,
  string
> = {
  actions: "Actions",
  navigation: "Navigation",
  objects: "Objects",
  status: "Status",
  misc: "Misc",
}


/** Resolve an icon name to a lucide component. Returns null when the
 *  name isn't in the curated subset — callers can decide whether to
 *  render a fallback (e.g., "icon name not recognized" or a generic
 *  placeholder). */
export function resolveSubsetIcon(name: string | undefined): LucideIcon | null {
  if (!name) return null
  return ICON_SUBSET_MAP[name] ?? null
}

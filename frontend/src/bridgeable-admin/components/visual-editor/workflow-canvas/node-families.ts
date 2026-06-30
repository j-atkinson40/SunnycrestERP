/**
 * node-families — A3 shape-treatment (replaces the B-3b silhouette system).
 *
 * Uniform node cards distinguished by a per-TYPE Lucide icon + a per-FAMILY
 * warm-tonal step (lightness, NOT hue) + a family left-stripe. This module
 * owns the three render-time constants:
 *
 *   - TYPE_ICON     : 32 VALID_NODE_TYPES → Lucide icon (defensive Circle
 *                     fallback for any unmapped type)
 *   - NODE_FAMILY   : node type → one of 6 operator-locked families
 *   - FAMILY_TONE   : family → { bg, stripe } OKLCH per light/dark mode
 *
 * DESIGN-LANGUAGE NOTE: these are RENDER-TIME CONSTANTS, not canon tokens.
 * The family tones stay strictly inside DESIGN_LANGUAGE's single-accent /
 * warm-restraint lock — terracotta (`--accent`) remains the only accent;
 * family distinction is a LIGHTNESS step within the warm-neutral hue (82
 * light / 81 dark), with a faint chroma lift for depth. NO new hues, NO
 * categorical rainbow, NO new design-language tokens. The taxonomy lives
 * here (NOT in the registry — registry stays flat category:"workflow-nodes"
 * per the B-2 Path A lock; NOT in canon).
 *
 * Tones are deliberately SUBTLE — the icon is the primary type signal; the
 * family tone + stripe are quiet reinforcement (P4). Calibrated on the live
 * canvas (render-time constant = cheap to adjust); no canon round-trip.
 */
import {
  Archive,
  BadgeCheck,
  Bell,
  BellRing,
  Bot,
  Calendar,
  CheckCheck,
  Circle,
  ClipboardCheck,
  Clock,
  Cog,
  FilePen,
  FilePlus,
  FileText,
  FileUp,
  Filter,
  Flag,
  GitBranch,
  GitFork,
  GitMerge,
  LogIn,
  LogOut,
  Mail,
  MessageSquare,
  PackageCheck,
  PanelRightOpen,
  Play,
  Send,
  Sparkles,
  Split,
  Wand2,
  Zap,
  type LucideIcon,
} from "lucide-react"

// ─── Per-type icon (32 + defensive fallback) ────────────────────────

export const TYPE_ICON: Record<string, LucideIcon> = {
  // Lifecycle
  start: Play,
  end: Flag,
  input: LogIn,
  output: LogOut,
  wait: Clock,
  schedule: Calendar,
  // Flow-control
  decision: GitBranch,
  condition: Filter,
  branch: Split,
  parallel_split: GitFork,
  parallel_join: GitMerge,
  // Action-data
  action: Zap,
  call_service_method: Cog,
  create_record: FilePlus,
  update_record: FilePen,
  log_vault_item: Archive,
  playwright_action: Bot,
  // AI-generation
  ai_prompt: Sparkles,
  generate_document: FileText,
  // Generation/review focus (the redundant generation-focus-invocation twin
  // was retired in focus-invocation reconciliation P2 — keeper below).
  invoke_generation_focus: Wand2,
  invoke_review_focus: ClipboardCheck,
  // Communication
  notification: Bell,
  send_notification: BellRing,
  send_email: Mail,
  notify_via_contact_preference: Send,
  send_document: FileUp,
  "send-communication": MessageSquare,
  show_confirmation: BadgeCheck,
  open_slide_over: PanelRightOpen,
  // Cross-tenant
  cross_tenant_order: PackageCheck,
  cross_tenant_request: Send,
  cross_tenant_acknowledgment: CheckCheck,
}

/** Resolve a type's icon; defensive Circle for any unmapped type. */
export function resolveTypeIcon(nodeType: string): LucideIcon {
  return TYPE_ICON[nodeType] ?? Circle
}


// ─── Families (operator-locked taxonomy; 6 families, all 32 assigned) ──

export type NodeFamily =
  | "lifecycle"
  | "flow-control"
  | "action-data"
  | "ai-generation"
  | "communication"
  | "cross-tenant"

export const NODE_FAMILY: Record<string, NodeFamily> = {
  // Lifecycle
  start: "lifecycle",
  end: "lifecycle",
  input: "lifecycle",
  output: "lifecycle",
  wait: "lifecycle",
  schedule: "lifecycle",
  // Flow-control
  decision: "flow-control",
  condition: "flow-control",
  branch: "flow-control",
  parallel_split: "flow-control",
  parallel_join: "flow-control",
  // Action-data
  action: "action-data",
  call_service_method: "action-data",
  create_record: "action-data",
  update_record: "action-data",
  log_vault_item: "action-data",
  playwright_action: "action-data",
  // AI-generation
  ai_prompt: "ai-generation",
  generate_document: "ai-generation",
  invoke_generation_focus: "ai-generation",
  invoke_review_focus: "ai-generation",
  // Communication
  notification: "communication",
  send_notification: "communication",
  send_email: "communication",
  notify_via_contact_preference: "communication",
  send_document: "communication",
  "send-communication": "communication",
  show_confirmation: "communication",
  open_slide_over: "communication",
  // Cross-tenant
  cross_tenant_order: "cross-tenant",
  cross_tenant_request: "cross-tenant",
  cross_tenant_acknowledgment: "cross-tenant",
}

/** Resolve a type's family; null for any unmapped type (→ neutral base tone). */
export function resolveNodeFamily(nodeType: string): NodeFamily | null {
  return NODE_FAMILY[nodeType] ?? null
}


// ─── Family tones (OKLCH, both modes; warm-restraint lightness step) ──

import type { ThemeMode } from "@/lib/theme-mode"

interface FamilyTone {
  /** Card background. */
  bg: string
  /** Left-stripe — a stronger step of the same warm tone. */
  stripe: string
}

interface FamilyToneByMode {
  light: FamilyTone
  dark: FamilyTone
}

/** Neutral base (unmapped type) — surface-elevated bg + subtle border stripe. */
const NEUTRAL_TONE: FamilyToneByMode = {
  light: { bg: "oklch(0.965 0.014 82)", stripe: "oklch(0.78 0.020 82)" },
  dark: { bg: "oklch(0.280 0.014 81)", stripe: "oklch(0.42 0.020 81)" },
}

/**
 * Per-family tone. Light steps DOWN in lightness from surface-elevated
 * (0.965) so families recede subtly against the warm page; dark steps UP
 * (lamplit grouping that lifts off the dark canvas). Stripe = a deeper /
 * slightly more chromatic step of the same warm hue. Hue locked 82/81.
 */
export const FAMILY_TONE: Record<NodeFamily, FamilyToneByMode> = {
  lifecycle: {
    light: { bg: "oklch(0.965 0.014 82)", stripe: "oklch(0.86 0.030 82)" },
    dark: { bg: "oklch(0.280 0.014 81)", stripe: "oklch(0.42 0.030 81)" },
  },
  communication: {
    light: { bg: "oklch(0.957 0.016 82)", stripe: "oklch(0.85 0.035 82)" },
    dark: { bg: "oklch(0.295 0.016 81)", stripe: "oklch(0.44 0.035 81)" },
  },
  "flow-control": {
    light: { bg: "oklch(0.949 0.018 82)", stripe: "oklch(0.84 0.040 82)" },
    dark: { bg: "oklch(0.310 0.018 81)", stripe: "oklch(0.46 0.040 81)" },
  },
  "ai-generation": {
    light: { bg: "oklch(0.945 0.019 82)", stripe: "oklch(0.83 0.045 82)" },
    dark: { bg: "oklch(0.320 0.019 81)", stripe: "oklch(0.48 0.045 81)" },
  },
  "action-data": {
    light: { bg: "oklch(0.940 0.020 82)", stripe: "oklch(0.82 0.050 82)" },
    dark: { bg: "oklch(0.330 0.020 81)", stripe: "oklch(0.50 0.050 81)" },
  },
  "cross-tenant": {
    light: { bg: "oklch(0.935 0.022 82)", stripe: "oklch(0.80 0.055 82)" },
    dark: { bg: "oklch(0.340 0.022 81)", stripe: "oklch(0.52 0.055 81)" },
  },
}

/** Resolve the card bg + stripe for a node type in the current mode. */
export function resolveFamilyTone(
  nodeType: string,
  mode: ThemeMode,
): FamilyTone {
  const family = resolveNodeFamily(nodeType)
  const byMode = family ? FAMILY_TONE[family] : NEUTRAL_TONE
  return byMode[mode]
}

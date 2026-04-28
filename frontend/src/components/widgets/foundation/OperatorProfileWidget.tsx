/**
 * OperatorProfileWidget — Phase W-3a cross-vertical foundation widget.
 *
 * Shows the current user's identity + role + active space. Cross-
 * vertical, cross-line — every tenant + every user sees this widget.
 * Per [DESIGN_LANGUAGE.md §12.10](../../../../DESIGN_LANGUAGE.md):
 * Glance + Brief variants only (no Detail — operator profile is a
 * reference widget, not a workspace; deeper profile editing routes
 * to /settings/profile).
 *
 * Three-component shape per AncillaryPoolPin precedent + same
 * Pattern 1 chrome on Glance / Pattern 2 content shape on Brief
 * as the TodayWidget (Phase W-3a Commit 2).
 *
 * Data source: **auth context only** — no backend call. The
 * `useAuth()` hook surfaces every field rendered by both variants:
 *   - first_name / last_name (avatar initials + full name)
 *   - role_name (display label)
 *   - permissions / enabled_modules / enabled_extensions counts
 * Plus `useSpaces()` for the active space's name + accent.
 * Adding a backend call (department, last_login, etc.) is a future
 * scope expansion when the data lands; W-3a Phase 1 is auth-only.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through navigation to /settings/profile.
 * No state-flip interactions; profile edits happen on the dedicated
 * page, not in the widget.
 */

import { useNavigate } from "react-router-dom"

import { useAuth } from "@/contexts/auth-context"
import { useSpacesOptional } from "@/contexts/space-context"
import { cn } from "@/lib/utils"
import type { User } from "@/types/auth"
import type { VariantId } from "@/components/widgets/types"


// ── Helpers ─────────────────────────────────────────────────────────


function getInitials(user: Pick<User, "first_name" | "last_name">): string {
  const f = (user.first_name || "").trim()
  const l = (user.last_name || "").trim()
  if (!f && !l) return "??"
  return ((f[0] ?? "") + (l[0] ?? "")).toUpperCase() || "??"
}


function fullName(user: Pick<User, "first_name" | "last_name">): string {
  return `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Unknown"
}


function roleLabel(user: Pick<User, "role_name" | "role_slug">): string {
  return user.role_name || user.role_slug || "Member"
}


// ── Avatar (shared between variants) ────────────────────────────────


interface AvatarProps {
  user: Pick<User, "first_name" | "last_name">
  size?: "sm" | "md"
}


/**
 * Avatar — initials inside a colored circle. Same Pattern 2 visual
 * vocabulary as the rest of the platform (terracotta accent muted
 * background per DESIGN_LANGUAGE §3 cross-mode pairing).
 *
 * Size sm = 24×24 (Glance variant). md = 32×32 (Brief variant).
 */
function OperatorAvatar({ user, size = "md" }: AvatarProps) {
  const initials = getInitials(user)
  return (
    <span
      data-slot="operator-profile-avatar"
      data-initials={initials}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full",
        "bg-accent-muted text-content-on-accent",
        "font-medium tabular-nums",
        size === "sm"
          ? "h-6 w-6 text-micro"
          : "h-8 w-8 text-caption",
      )}
      aria-hidden
    >
      {initials}
    </span>
  )
}


// ── Glance variant (Pattern 1 frosted-glass tablet) ─────────────────


interface GlanceProps {
  user: User
  onSummon: () => void
}


function OperatorProfileGlanceTablet({ user, onSummon }: GlanceProps) {
  const role = roleLabel(user)
  const name = fullName(user)
  return (
    <div
      data-slot="operator-profile-widget"
      data-variant="glance"
      data-surface="spaces_pin"
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Pattern 1 frosted-glass surface — same chrome as
        // TodayWidget Glance + AncillaryPoolPin Glance for cross-
        // surface continuity.
        "relative flex items-center overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        "h-15 w-full",
        "cursor-pointer",
        "hover:bg-surface-elevated/95",
        "transition-colors duration-quick ease-settle",
        "focus-ring-accent outline-none",
      )}
      onClick={onSummon}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onSummon()
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`${name}, ${role}. Open profile.`}
    >
      {/* Bezel column — same 28px structural left edge as other
          Pattern 1 widgets. */}
      <div
        aria-hidden
        data-slot="operator-profile-widget-bezel-grip"
        className={cn(
          "flex h-full w-7 shrink-0 items-center justify-center",
          "border-r border-border-subtle/30",
          "gap-0.5",
        )}
      >
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
      </div>
      {/* Content — avatar + name + role */}
      <div className="flex min-w-0 flex-1 items-center gap-2 px-3">
        <OperatorAvatar user={user} size="sm" />
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-caption font-medium leading-tight",
              "text-content-strong font-sans truncate",
            )}
            data-slot="operator-profile-widget-name"
          >
            {name}
          </p>
          <p
            className={cn(
              "text-micro leading-tight",
              "text-content-muted font-sans truncate",
            )}
            data-slot="operator-profile-widget-role"
          >
            {role}
          </p>
        </div>
      </div>
    </div>
  )
}


// ── Brief variant (Pattern 2 solid-fill card) ───────────────────────


interface BriefProps {
  user: User
  activeSpaceName: string | null
  onNavigate: () => void
}


function OperatorProfileBriefCard({
  user,
  activeSpaceName,
  onNavigate,
}: BriefProps) {
  const role = roleLabel(user)
  const name = fullName(user)
  const permissionsCount = user.permissions?.length ?? 0
  const modulesCount = user.enabled_modules?.length ?? 0
  const extensionsCount = user.enabled_extensions?.length ?? 0

  return (
    <div
      data-slot="operator-profile-widget"
      data-variant="brief"
      className="flex flex-col h-full"
    >
      {/* Header — eyebrow + avatar + full name */}
      <div
        data-slot="operator-profile-widget-header"
        className={cn(
          "flex items-center gap-3",
          "border-b border-border-subtle/40 px-4 py-3",
        )}
      >
        <OperatorAvatar user={user} size="md" />
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
            )}
          >
            Signed in as
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-sans truncate",
            )}
            data-slot="operator-profile-widget-name"
          >
            {name}
          </h3>
          <p
            className={cn(
              "text-caption text-content-muted font-sans truncate",
            )}
            data-slot="operator-profile-widget-email"
          >
            {user.email || ""}
          </p>
        </div>
      </div>

      {/* Body — role + active space + access summary */}
      <div
        data-slot="operator-profile-widget-body"
        className="flex-1 px-4 py-3 space-y-2"
      >
        <ProfileRow
          label="Role"
          value={role}
          slot="operator-profile-widget-role"
        />
        <ProfileRow
          label="Active space"
          value={activeSpaceName || "—"}
          slot="operator-profile-widget-space"
        />
        <ProfileRow
          label="Access"
          value={
            permissionsCount === 0 && modulesCount === 0
              ? "—"
              : [
                  `${permissionsCount} permission${
                    permissionsCount === 1 ? "" : "s"
                  }`,
                  `${modulesCount} module${
                    modulesCount === 1 ? "" : "s"
                  }`,
                  ...(extensionsCount > 0
                    ? [
                        `${extensionsCount} extension${
                          extensionsCount === 1 ? "" : "s"
                        }`,
                      ]
                    : []),
                ].join(" · ")
          }
          slot="operator-profile-widget-access"
        />
      </div>

      {/* Footer — manage profile CTA */}
      <div
        data-slot="operator-profile-widget-footer"
        className={cn(
          "border-t border-border-subtle/40 px-4 py-2",
        )}
      >
        <button
          onClick={onNavigate}
          className={cn(
            "text-caption text-accent font-sans",
            "hover:text-accent-hover",
            "transition-colors duration-quick ease-settle",
            "focus-ring-accent outline-none rounded-sm",
          )}
          data-slot="operator-profile-widget-cta"
        >
          Manage profile →
        </button>
      </div>
    </div>
  )
}


function ProfileRow({
  label,
  value,
  slot,
}: {
  label: string
  value: string
  slot: string
}) {
  return (
    <div
      className="flex items-baseline justify-between gap-3"
      data-slot={slot}
    >
      <span
        className={cn(
          "text-caption text-content-muted font-sans shrink-0",
          "uppercase tracking-wider text-micro",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "text-caption text-content-base font-sans truncate",
          "text-right",
        )}
      >
        {value}
      </span>
    </div>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


export interface OperatorProfileWidgetProps {
  widgetId?: string
  variant_id?: VariantId
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
}


export function OperatorProfileWidget(props: OperatorProfileWidgetProps) {
  const isGlance =
    props.surface === "spaces_pin" || props.variant_id === "glance"
  if (isGlance) {
    return <OperatorProfileGlanceVariant />
  }
  return <OperatorProfileBriefVariant />
}


/** Glance dispatcher — pulls user from auth context. Returns null
 * when unauthenticated (defensive: every consumer surface is gated by
 * ProtectedRoute, but the dispatcher must not crash if mounted in a
 * non-auth context like Storybook or test scaffolding). */
function OperatorProfileGlanceVariant() {
  const navigate = useNavigate()
  const { user } = useAuth()
  if (!user) return null
  return (
    <OperatorProfileGlanceTablet
      user={user}
      onSummon={() => navigate("/settings/profile")}
    />
  )
}


/** Brief dispatcher — pulls user from auth context + active space
 * from spaces context (optional, may not be present outside the
 * tenant app shell). */
function OperatorProfileBriefVariant() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const spacesCtx = useSpacesOptional()
  if (!user) return null
  const activeSpaceName = spacesCtx?.activeSpace?.name ?? null
  return (
    <OperatorProfileBriefCard
      user={user}
      activeSpaceName={activeSpaceName}
      onNavigate={() => navigate("/settings/profile")}
    />
  )
}


export default OperatorProfileWidget

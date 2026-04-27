/**
 * DotNav — Workflow Arc Phase 8a.
 *
 * Horizontal row of dots at the bottom of the left sidebar.
 * Replaces the top-of-screen SpaceSwitcher (Phase 3) with a more
 * compact + discoverable space switcher that lives alongside the
 * rest of the nav rail.
 *
 * Dot rendering:
 *   - Per-space icon when `space.icon` maps to a lucide name
 *   - Colored dot (fallback) with space accent
 *   - Active dot: filled with space accent + ring
 *   - Inactive: faded outline
 *   - System spaces (is_system=true) render leftmost + always
 *     visible; user spaces follow in display_order
 *   - Plus button at the end triggers NewSpaceDialog
 *
 * Keyboard shortcuts preserved from Phase 3 SpaceSwitcher:
 *   - Cmd/Ctrl + ]   → next space
 *   - Cmd/Ctrl + [   → previous space
 *   - Cmd/Ctrl + Shift + 1..5 → jump to space N (1-indexed)
 *
 * Registered via useEffect (not capture-phase) — different modifier
 * combos from the command bar's Option/Alt+1..5, so no collision.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,

} from "react";
import {
  BarChart3,
  Calculator,
  CalendarHeart,
  Factory,
  GraduationCap,
  Home,
  Kanban,
  Layers,
  type LucideIcon,
  MapPin,
  Plus,
  Receipt,
  Settings as SettingsIcon,
  ShieldCheck,
  Store,
  TrendingUp,
  Truck,
  Users,
} from "lucide-react";

import { useSpaces } from "@/contexts/space-context";
import { cn } from "@/lib/utils";
import { NewSpaceDialog } from "@/components/spaces/NewSpaceDialog";
import { SpaceEditorDialog } from "@/components/spaces/SpaceEditorDialog";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import type { Space } from "@/types/spaces";


// Lucide icon map for space.icon strings used in SEED_TEMPLATES +
// SYSTEM_SPACE_TEMPLATES. Unknown icons fall back to the colored-dot
// rendering. Keep this map narrow — per-space-icon is a low-churn
// field; we don't need every lucide icon.
const ICON_MAP: Record<string, LucideIcon> = {
  "calendar-heart": CalendarHeart,
  receipt: Receipt,
  "trending-up": TrendingUp,
  factory: Factory,
  kanban: Kanban,
  store: Store,
  home: Home,
  settings: SettingsIcon,
  truck: Truck,
  calculator: Calculator,
  "map-pin": MapPin,
  users: Users,
  layers: Layers,
  // Phase 8e additions — bar-chart-3 (Reports), shield-check
  // (Compliance), graduation-cap (Training).
  "bar-chart-3": BarChart3,
  "shield-check": ShieldCheck,
  "graduation-cap": GraduationCap,
};


function DotIcon({
  space,
  active,
}: {
  space: Space;
  active: boolean;
}) {
  const IconComponent = ICON_MAP[space.icon];
  if (IconComponent) {
    return (
      <IconComponent
        className="h-3.5 w-3.5"
        style={
          active
            ? { color: "var(--space-accent, var(--preset-accent))" }
            : undefined
        }
      />
    );
  }
  // Fallback — filled dot, colored with space accent.
  return (
    <span
      className="block h-2 w-2 rounded-full"
      style={{
        backgroundColor: active
          ? "var(--space-accent, var(--preset-accent))"
          : "currentColor",
      }}
    />
  );
}


export function DotNav() {
  const { spaces, activeSpace, switchSpace, isLoading } = useSpaces();
  const [creatorOpen, setCreatorOpen] = useState(false);
  const [editorTarget, setEditorTarget] = useState<string | null>(null);

  // Sort: system spaces first (always), then user spaces by
  // display_order. Matches backend's -1000 default for system spaces
  // but is also a belt-and-suspenders safeguard against user
  // reorders that might put a system space below a user space.
  const sortedSpaces = useMemo(() => {
    return [...spaces].sort((a, b) => {
      const aSys = a.is_system ? 0 : 1;
      const bSys = b.is_system ? 0 : 1;
      if (aSys !== bSys) return aSys - bSys;
      return a.display_order - b.display_order;
    });
  }, [spaces]);

  // ── Keyboard shortcuts ────────────────────────────────────────

  useEffect(() => {
    if (sortedSpaces.length === 0) return;

    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;

      // Skip if user is typing into an input / textarea.
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (target.isContentEditable) return;
      }

      // Phase 8e — keyboard shortcuts pass source="keyboard" so
      // rapid-switching doesn't fling the user between routes.
      if (e.key === "]") {
        e.preventDefault();
        const idx = sortedSpaces.findIndex(
          (s) => s.space_id === activeSpace?.space_id,
        );
        const next = sortedSpaces[(idx + 1) % sortedSpaces.length];
        if (next) void switchSpace(next.space_id, { source: "keyboard" });
        return;
      }
      if (e.key === "[") {
        e.preventDefault();
        const idx = sortedSpaces.findIndex(
          (s) => s.space_id === activeSpace?.space_id,
        );
        const prev =
          sortedSpaces[
            (idx - 1 + sortedSpaces.length) % sortedSpaces.length
          ];
        if (prev) void switchSpace(prev.space_id, { source: "keyboard" });
        return;
      }
      // Phase 8e — Cmd+Shift+1..7 (bumped from 1..5 alongside
      // MAX_SPACES_PER_USER = 7).
      if (e.shiftKey && e.key >= "1" && e.key <= "7") {
        e.preventDefault();
        const n = parseInt(e.key, 10) - 1;
        const target = sortedSpaces[n];
        if (target) void switchSpace(target.space_id, { source: "keyboard" });
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [sortedSpaces, activeSpace, switchSpace]);

  const handleDotClick = useCallback(
    (spaceId: string, event: React.MouseEvent) => {
      // Shift-click opens the editor (inline renaming, recoloring).
      if (event.shiftKey) {
        setEditorTarget(spaceId);
        return;
      }
      // Phase 8e — click = deliberate activation, triggers the
      // target space's default_home_route navigation.
      void switchSpace(spaceId, { source: "deliberate" });
    },
    [switchSpace],
  );

  // Nav Bar Completion (Apr 2026) — the rail ALWAYS renders, so the
  // + button is reachable at all times. Phase 8a shipped a
  // `spaces.length === 0 → return null` early-return whose inline
  // comment described "render just the plus button" but whose code
  // returned null. Comment-code mismatch that survived 14 months
  // because the Playwright test seeds spaces before assertion and
  // never exercised the empty branch. Fix renders per-state:
  //   isLoading + spaces=[] → skeleton dot next to + button
  //   !isLoading + spaces=[] → + button alone (recovery path)
  //   spaces.length > 0     → real dots + + button
  //
  // Welcome touch gate (≥2 spaces) unchanged — single-space tenants
  // don't benefit from a "switch spaces" primer.
  const showWelcomeTouch = sortedSpaces.length >= 2;
  const showSkeleton = isLoading && sortedSpaces.length === 0;

  return (
    <>
      {/* Phase 8e — MAX_SPACES_PER_USER bumped 5 → 7. Dot layout
          tightened from gap-1.5 to gap-1 and given overflow-x-auto
          so a collapsed 240px sidebar still fits 7 dots + plus
          gracefully. Horizontal scroll bar is hidden via scrollbar-
          none utility; users still navigate via shortcuts.
          `relative` anchors the OnboardingTouch welcome card. */}
      <div
        className="scrollbar-none relative flex items-center gap-1 overflow-x-auto border-t border-border-subtle px-3 py-2"
        role="toolbar"
        aria-label="Space switcher"
        data-testid="dot-nav"
      >
        {showWelcomeTouch ? (
          <OnboardingTouch
            touchKey="welcome_to_spaces"
            title="Spaces organize your day."
            body={
              "Click a dot to switch — each space pins the views " +
              "and pages you need for that kind of work. ⌘[ and " +
              "⌘] cycle without changing pages."
            }
            position="top"
            className="left-3 right-3 w-auto"
          />
        ) : null}
        {showSkeleton ? (
          // Loading skeleton — avoids the "plus button appears alone
          // for a flash" during initial fetchSpaces(). Matches the
          // 7×7 dot footprint so layout doesn't shift on fetch-complete.
          <span
            className="inline-block h-7 w-7 rounded-full bg-surface-sunken animate-pulse motion-reduce:animate-none"
            aria-hidden="true"
            data-testid="dot-nav-skeleton"
          />
        ) : null}
        {sortedSpaces.map((space) => {
          const active = space.space_id === activeSpace?.space_id;
          // Phase 8e.2.3 — state-aware tooltip. See
          // DESIGN_LANGUAGE.md § Tooltip patterns for the
          // "describe state when state matters" convention. An
          // active dot labeled "Switch to Operations" when the user
          // IS in Operations is misleading. "Active: Operations"
          // describes what the user sees; "Switch to Operations"
          // describes an action.
          const systemSuffix = space.is_system ? " (system)" : "";
          const label = active
            ? `Active: ${space.name}${systemSuffix}`
            : `Switch to ${space.name}${systemSuffix}`;
          return (
            <button
              key={space.space_id}
              type="button"
              onClick={(e) => handleDotClick(space.space_id, e)}
              title={label}
              aria-label={label}
              aria-pressed={active}
              className={cn(
                // Phase 8e.2.3 — active-state visual feedback
                // strengthened: ring bumped 1px → 2px with offset-1
                // for a clear "raised chip" effect; inactive opacity
                // tightened from text-content-muted-default to an
                // explicit 0.6 so the active/inactive delta is
                // readable even when both dots share the fallback
                // colored-dot rendering (user-created spaces).
                "inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors duration-quick ease-settle focus-ring-accent",
                active
                  ? "border-[color:var(--space-accent,var(--preset-accent))] bg-[color:var(--space-accent-light,transparent)] ring-2 ring-offset-1 ring-offset-surface-sunken ring-[color:var(--space-accent,var(--preset-accent))]"
                  : "border-transparent text-content-muted opacity-60 hover:opacity-100 hover:bg-accent-subtle hover:text-content-strong",
              )}
              data-testid="dot-nav-dot"
              data-space-id={space.space_id}
              data-active={active ? "true" : "false"}
              data-is-system={space.is_system ? "true" : "false"}
            >
              <DotIcon space={space} active={active} />
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setCreatorOpen(true)}
          title="Add a new space"
          aria-label="Add a new space"
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-dashed border-border-base text-content-muted transition-colors duration-quick ease-settle hover:border-solid hover:border-accent hover:text-content-strong focus-ring-accent"
          data-testid="dot-nav-add"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <NewSpaceDialog
        open={creatorOpen}
        onOpenChange={(open) => setCreatorOpen(open)}
      />
      <SpaceEditorDialog
        spaceId={editorTarget}
        open={editorTarget !== null}
        onOpenChange={(open) => { if (!open) setEditorTarget(null); }}
      />
    </>
  );
}


export default DotNav;


// Render<ReactNode> helper so callers importing named export can
// also grab a default-export for lazy loading if ever needed.
export const _DOT_NAV_ICON_MAP = ICON_MAP;

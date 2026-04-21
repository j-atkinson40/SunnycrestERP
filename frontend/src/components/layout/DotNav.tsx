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
  Calculator,
  CalendarHeart,
  Factory,
  Home,
  Kanban,
  Layers,
  type LucideIcon,
  MapPin,
  Plus,
  Receipt,
  Settings as SettingsIcon,
  Store,
  TrendingUp,
  Truck,
  Users,
} from "lucide-react";

import { useSpaces } from "@/contexts/space-context";
import { cn } from "@/lib/utils";
import { NewSpaceDialog } from "@/components/spaces/NewSpaceDialog";
import { SpaceEditorDialog } from "@/components/spaces/SpaceEditorDialog";
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
  const { spaces, activeSpace, switchSpace } = useSpaces();
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

      if (e.key === "]") {
        e.preventDefault();
        const idx = sortedSpaces.findIndex(
          (s) => s.space_id === activeSpace?.space_id,
        );
        const next = sortedSpaces[(idx + 1) % sortedSpaces.length];
        if (next) void switchSpace(next.space_id);
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
        if (prev) void switchSpace(prev.space_id);
        return;
      }
      if (e.shiftKey && e.key >= "1" && e.key <= "5") {
        e.preventDefault();
        const n = parseInt(e.key, 10) - 1;
        const target = sortedSpaces[n];
        if (target) void switchSpace(target.space_id);
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
      void switchSpace(spaceId);
    },
    [switchSpace],
  );

  if (spaces.length === 0) {
    // No spaces yet (unauthenticated or pre-seed): render just the
    // plus button so new tenants can still create one.
    return null;
  }

  return (
    <>
      <div
        className="flex items-center gap-1.5 border-t px-3 py-2"
        role="toolbar"
        aria-label="Space switcher"
        data-testid="dot-nav"
      >
        {sortedSpaces.map((space) => {
          const active = space.space_id === activeSpace?.space_id;
          const label = `Switch to ${space.name}${space.is_system ? " (system)" : ""}`;
          return (
            <button
              key={space.space_id}
              type="button"
              onClick={(e) => handleDotClick(space.space_id, e)}
              title={label}
              aria-label={label}
              aria-pressed={active}
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors",
                active
                  ? "border-[color:var(--space-accent,var(--preset-accent))] bg-[color:var(--space-accent-light,transparent)] ring-1 ring-[color:var(--space-accent,var(--preset-accent))]"
                  : "border-transparent text-muted-foreground/70 hover:bg-muted hover:text-foreground",
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
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-dashed text-muted-foreground/60 transition-colors hover:border-solid hover:text-foreground"
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

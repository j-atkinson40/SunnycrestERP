/**
 * SpaceSwitcher — top-nav space selector.
 *
 * Renders the active space's name + icon as a trigger; opening the
 * dropdown shows every space + "New space…" + "Edit spaces…"
 * actions. Click a space → switch. Accent color lights up the
 * active row via --space-accent.
 *
 * Also registers the keyboard shortcuts:
 *   - Cmd/Ctrl + ]  → next space
 *   - Cmd/Ctrl + [  → previous space
 *   - Cmd/Ctrl + Shift + 1..5 → jump to space N
 *
 * Shortcuts are installed via useEffect (no capture-phase needed;
 * these modifier combos don't collide with the command bar's
 * Option/Alt+1..5 or Cmd+K).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Layers, Pencil, Plus } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useSpaces } from "@/contexts/space-context";
import { cn } from "@/lib/utils";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import { NewSpaceDialog } from "./NewSpaceDialog";
import { SpaceEditorDialog } from "./SpaceEditorDialog";

function iconNode(_name: string): React.ReactNode {
  // Spaces icons come from the template registry as lucide names.
  // The sidebar has an extensive ICON_MAP — the switcher just needs
  // a minimal visual; use Layers as a universal placeholder so we
  // don't have to maintain a second icon map here. Per-space
  // personality comes through accent color, not icon variety.
  return <Layers className="size-4 shrink-0" />;
}

export function SpaceSwitcher() {
  const {
    spaces,
    activeSpace,
    switchSpace,
    isLoading,
  } = useSpaces();

  const [creatorOpen, setCreatorOpen] = useState(false);
  const [editorTarget, setEditorTarget] = useState<string | null>(null);

  // ── Keyboard shortcuts ────────────────────────────────────────
  // Standard useEffect listener (not capture-phase). Cmd+[, Cmd+],
  // Cmd+Shift+1..5. Checks order: bracket keys first (both use
  // `e.key`), then Shift+digit.
  const sortedSpaces = useMemo(
    () => [...spaces].sort((a, b) => a.display_order - b.display_order),
    [spaces],
  );

  const doSwitchByIndex = useCallback(
    (idx: number) => {
      const target = sortedSpaces[idx];
      if (target && target.space_id !== activeSpace?.space_id) {
        void switchSpace(target.space_id);
      }
    },
    [sortedSpaces, activeSpace, switchSpace],
  );

  useEffect(() => {
    if (sortedSpaces.length === 0) return;

    function onKey(e: KeyboardEvent) {
      const usesCmd = e.metaKey || e.ctrlKey;
      if (!usesCmd) return;

      // Skip if the user is typing in an input (command bar, etc).
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) {
        // Still allow bracket navigation (won't collide with
        // browser defaults in most inputs), but NOT the digit
        // jumps — those would interfere with typing.
        if (e.shiftKey) return;
      }

      // Cmd + [ / ]
      if (!e.shiftKey && !e.altKey) {
        if (e.key === "]") {
          e.preventDefault();
          const idx = Math.max(
            0,
            sortedSpaces.findIndex(
              (s) => s.space_id === activeSpace?.space_id,
            ),
          );
          const next = (idx + 1) % sortedSpaces.length;
          doSwitchByIndex(next);
          return;
        }
        if (e.key === "[") {
          e.preventDefault();
          const idx = Math.max(
            0,
            sortedSpaces.findIndex(
              (s) => s.space_id === activeSpace?.space_id,
            ),
          );
          const prev = (idx - 1 + sortedSpaces.length) % sortedSpaces.length;
          doSwitchByIndex(prev);
          return;
        }
      }

      // Cmd + Shift + 1..5 — jump by index.
      if (e.shiftKey && !e.altKey) {
        const n = parseInt(e.key, 10);
        if (!Number.isNaN(n) && n >= 1 && n <= 5) {
          const idx = n - 1;
          if (idx < sortedSpaces.length) {
            e.preventDefault();
            doSwitchByIndex(idx);
          }
        }
      }
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sortedSpaces, activeSpace?.space_id, doSwitchByIndex]);

  if (isLoading && spaces.length === 0) {
    return null;
  }
  if (spaces.length === 0) {
    // No spaces seeded yet (edge case — new user before seed runs).
    // Render a subtle "New space" button so the user isn't stuck.
    return (
      <>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCreatorOpen(true)}
          className="gap-2 text-xs"
          data-testid="space-switcher-empty"
        >
          <Plus className="size-3.5" /> New space
        </Button>
        <NewSpaceDialog open={creatorOpen} onOpenChange={setCreatorOpen} />
      </>
    );
  }

  // Phase 7 — show first-run tooltip only if the user has more than
  // one space (a single-space user doesn't benefit from explaining
  // space switching).
  const showSwitcherIntro = sortedSpaces.length > 1;

  return (
    <>
      <div className="relative">
        {showSwitcherIntro ? (
          <OnboardingTouch
            touchKey="space_switcher_intro"
            title="Spaces organize different work."
            body={"Use \u2318[ and \u2318] to move between them, or \u2318\u21E71\u20135 to jump directly."}
            position="bottom"
            className="right-0 top-full w-72 mt-2"
          />
        ) : null}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  "gap-2 text-xs h-8",
                  "border-[color:var(--space-accent,var(--preset-accent))]/30",
                )}
                style={{
                  color: "var(--space-accent, var(--preset-accent))",
                }}
                data-testid="space-switcher-trigger"
                data-space-id={activeSpace?.space_id ?? ""}
              >
                {iconNode(activeSpace?.icon ?? "layers")}
                <span className="font-medium">
                  {activeSpace?.name ?? "Select space"}
                </span>
                <ChevronDown className="size-3 opacity-60" />
              </Button>
            }
          />
        <DropdownMenuContent align="end" className="w-56">
          {sortedSpaces.map((s, idx) => {
            const isActive = s.space_id === activeSpace?.space_id;
            return (
              <DropdownMenuItem
                key={s.space_id}
                onSelect={() => void switchSpace(s.space_id)}
                className={cn(
                  "flex items-center justify-between gap-2",
                  isActive && "font-medium bg-accent/40",
                )}
                data-testid={`space-switcher-item-${s.space_id}`}
              >
                <div className="flex items-center gap-2">
                  {iconNode(s.icon)}
                  <span className="truncate">{s.name}</span>
                </div>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  ⌘⇧{idx + 1}
                </span>
              </DropdownMenuItem>
            );
          })}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => setCreatorOpen(true)}
            className="gap-2"
          >
            <Plus className="size-4" />
            New space…
          </DropdownMenuItem>
          {activeSpace && (
            <DropdownMenuItem
              onSelect={() => setEditorTarget(activeSpace.space_id)}
              className="gap-2"
            >
              <Pencil className="size-4" />
              Edit current space…
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      </div>

      <NewSpaceDialog open={creatorOpen} onOpenChange={setCreatorOpen} />
      <SpaceEditorDialog
        spaceId={editorTarget}
        open={editorTarget !== null}
        onOpenChange={(o) => {
          if (!o) setEditorTarget(null);
        }}
      />
    </>
  );
}

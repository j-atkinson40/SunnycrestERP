/**
 * ModeToggle — Nav Bar Completion (April 2026).
 *
 * Sun/Moon button in the AppLayout top header. Wires the visible
 * UI control to the already-complete mode-switching infrastructure:
 *
 *   - Aesthetic Arc Session 1: flash-mitigation inline script in
 *     `index.html` reads localStorage + falls back to
 *     `prefers-color-scheme`, sets `data-mode="dark"` on `<html>`
 *     BEFORE React mounts (no flash of wrong mode).
 *   - Runtime API `frontend/src/lib/theme-mode.ts` — `useMode()`
 *     hook with `{mode, toggle}` shape. Delegates to `useThemeMode`.
 *   - tokens.css `[data-mode="dark"]` block flips all DL tokens.
 *   - index.css shadcn-default aliases (Phase II Batch 0) flip
 *     automatically via the DL cascade.
 *
 * Design decisions (audit-approved):
 *   - Icon rendered is the DESTINATION, not current state:
 *     light mode shows <Moon /> (click to go dark),
 *     dark mode shows <Sun /> (click to go light).
 *     Matches GitHub / Linear / most SaaS apps + user intuition.
 *   - `aria-label` describes the ACTION ("Switch to dark mode"),
 *     not the state — per WCAG toggle-button recommendation.
 *   - `aria-pressed` reflects current toggle state (true when dark).
 *     Screen readers announce both the available action + current state.
 *   - `focus-ring-brass` utility inherits the current light-mode
 *     WCAG 2.4.7 gap (~1.26:1 on cream — Session 4/Batch 1a finding)
 *     until Session 6 fixes the utility itself. Not a per-component
 *     fix in scope here.
 *   - Size: `h-9 w-9` matches the adjacent <NotificationDropdown>
 *     visual weight + satisfies WCAG 2.2 target size (36 >= 24).
 */

import { Moon, Sun } from "lucide-react";

import { useMode } from "@/lib/theme-mode";
import { cn } from "@/lib/utils";

interface ModeToggleProps {
  className?: string;
}

export function ModeToggle({ className }: ModeToggleProps) {
  const { mode, toggle } = useMode();
  const isDark = mode === "dark";
  const Icon = isDark ? Sun : Moon;
  const nextMode = isDark ? "light" : "dark";
  const label = `Switch to ${nextMode} mode`;

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      aria-pressed={isDark}
      title={label}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-md text-content-muted transition-colors duration-quick ease-settle hover:bg-brass-subtle hover:text-content-strong focus-ring-brass",
        className,
      )}
      data-testid="mode-toggle"
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

export default ModeToggle;

/**
 * Phase 7 — Keyboard help overlay.
 *
 * Press `?` anywhere (outside input/textarea/contenteditable) to
 * open a modal listing every available shortcut. The list is
 * context-aware via location pathname — triage page shows triage
 * shortcuts, etc.
 *
 * This is app-level infrastructure: mounted once in App.tsx so the
 * `?` key is wired globally. Dismisses on Escape, on backdrop click,
 * or on the Close button.
 */

import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Shortcut {
  keys: string;
  label: string;
}

interface ShortcutSection {
  title: string;
  shortcuts: Shortcut[];
}

const GLOBAL_SHORTCUTS: ShortcutSection = {
  title: "Global",
  shortcuts: [
    { keys: "\u2318 K", label: "Open command bar" },
    { keys: "\u2318 \u2318 K", label: "Voice input (hold)" },
    { keys: "?", label: "Open this keyboard help" },
  ],
};

const COMMAND_BAR_SHORTCUTS: ShortcutSection = {
  title: "Command bar",
  shortcuts: [
    { keys: "\u2191 \u2193", label: "Navigate results" },
    { keys: "Enter", label: "Select" },
    { keys: "Esc", label: "Close" },
    { keys: "\u2325 1\u20135", label: "Jump to result 1-5" },
    { keys: "Tab", label: "Open traditional form (in NL mode)" },
  ],
};

const SPACES_SHORTCUTS: ShortcutSection = {
  title: "Spaces",
  shortcuts: [
    { keys: "\u2318 [", label: "Previous space" },
    { keys: "\u2318 ]", label: "Next space" },
    { keys: "\u2318 \u21E7 1\u20135", label: "Jump to space 1-5" },
  ],
};

const TRIAGE_SHORTCUTS: ShortcutSection = {
  title: "Triage workspace",
  shortcuts: [
    { keys: "Enter", label: "Accept / primary action" },
    { keys: "r", label: "Reassign" },
    { keys: "s", label: "Defer (snooze)" },
    { keys: "\u21E7 D", label: "Cancel / reject" },
    { keys: "n", label: "Skip" },
  ],
};

const TASK_SHORTCUTS: ShortcutSection = {
  title: "Tasks",
  shortcuts: [
    { keys: "\u2318 K \u00B7 new task \u2026", label: "Create task via NL" },
  ],
};

function sectionsForPath(pathname: string): ShortcutSection[] {
  const sections: ShortcutSection[] = [GLOBAL_SHORTCUTS, COMMAND_BAR_SHORTCUTS, SPACES_SHORTCUTS];
  if (pathname.startsWith("/triage")) sections.push(TRIAGE_SHORTCUTS);
  if (pathname.startsWith("/tasks")) sections.push(TASK_SHORTCUTS);
  return sections;
}

export function KeyboardHelpOverlay() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        if (target.isContentEditable) return;
        if (target.getAttribute("role") === "textbox") return;
      }
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setOpen((v) => !v);
        return;
      }
      if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  const close = useCallback(() => setOpen(false), []);

  if (!open) return null;

  const sections = sectionsForPath(location.pathname);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      data-testid="keyboard-help-overlay"
      onClick={close}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" aria-hidden="true" />
      <div
        className={cn(
          "relative w-full max-w-[560px] mx-4 rounded-xl bg-card shadow-2xl ring-1 ring-foreground/10",
          "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95",
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-5 py-3">
          <h2 className="text-sm font-semibold">Keyboard shortcuts</h2>
          <button
            type="button"
            onClick={close}
            aria-label="Close keyboard help"
            className="rounded text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          {sections.map((section) => (
            <div key={section.title} className="space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                {section.title}
              </div>
              <ul className="space-y-1">
                {section.shortcuts.map((s) => (
                  <li
                    key={`${section.title}-${s.keys}`}
                    className="flex items-center justify-between gap-3 text-xs"
                  >
                    <span className="text-foreground/80">{s.label}</span>
                    <kbd className="rounded border bg-muted px-1.5 py-0.5 text-[10px] tabular-nums">
                      {s.keys}
                    </kbd>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <footer className="border-t px-5 py-2 text-[10px] text-muted-foreground">
          Press <kbd className="rounded border bg-muted px-1">?</kbd> again or{" "}
          <kbd className="rounded border bg-muted px-1">Esc</kbd> to close
        </footer>
      </div>
    </div>
  );
}

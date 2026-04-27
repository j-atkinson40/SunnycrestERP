import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * Extended tailwind-merge config (Aesthetic Arc Session 2, April 2026).
 *
 * Default tailwind-merge classifies any `text-*` utility into the
 * font-size group, which causes a class like `text-body-sm` (font-size)
 * to dedupe-out `text-content-on-accent` (color). Pre-rename this same
 * conflict silently dropped `text-content-on-brass` from primary
 * button rendering — the bug surfaced visibly when the migration to
 * deepened terracotta moved cream-text-on-accent into a register where
 * the missing color reads obviously wrong.
 *
 * The fix: register our custom `--text-*` (font-size) and `--color-*`
 * (color) namespaces so tailwind-merge knows the difference. This
 * applies to every `cn()` call platform-wide. No component code
 * changes; the conflict resolves at the merge layer.
 */
const customTwMerge = extendTailwindMerge({
  override: {
    classGroups: {
      // Font-size utilities — DESIGN_LANGUAGE §4 size scale tokens
      // (the `--text-*` namespace in `index.css @theme inline`).
      "font-size": [
        {
          text: [
            "display-lg",
            "display",
            "h1",
            "h2",
            "h3",
            "h4",
            "body",
            "body-sm",
            "caption",
            "micro",
          ],
        },
      ],
      // Text color utilities — DESIGN_LANGUAGE §3 content + accent +
      // status tokens (the `--color-*` namespace, text- subset).
      "text-color": [
        {
          text: [
            // Content tokens
            "content-strong",
            "content-base",
            "content-muted",
            "content-subtle",
            "content-on-accent",
            // Accent
            "accent",
            "accent-hover",
            // Status (full set)
            "status-error",
            "status-warning",
            "status-success",
            "status-info",
            "status-error-muted",
            "status-warning-muted",
            "status-success-muted",
            "status-info-muted",
            // Surface text (rarely used but keep coherent)
            "surface-base",
            "surface-elevated",
            "surface-raised",
            "surface-sunken",
          ],
        },
      ],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return customTwMerge(clsx(inputs))
}

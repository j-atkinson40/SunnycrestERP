# Canonical Mockups

Authoritative visual references for Bridgeable's design system. When arcs
reference "match the canonical mockup," they reference files here.

## Files

- `funeral_scheduling_apple_pre_liquid_glass.html` — canonical FH Scheduling
  Focus aesthetic. Apple-pre-liquid-glass: warm sunrise gradient substrate,
  frosted glass cards, restrained typography. Authoritative reference for
  morning-warm substrate composition, frosted chrome preset values, and
  frosted-text typography preset values. Referenced by E-1 and E-1.1 arcs.

## Conventions

- Mockups are static, self-contained HTML files. No build step, no
  external dependencies — open directly in a browser.
- Canonical CSS values inline in each mockup are the source of truth.
  When code and mockup diverge, the mockup wins; arcs land code changes
  to align.
- New mockups land alongside the arc that introduces them. Update this
  README's Files list when adding.

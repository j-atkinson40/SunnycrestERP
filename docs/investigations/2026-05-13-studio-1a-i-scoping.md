# Studio 1a-i scoping re-estimate + sub-arc decomposition findings

Read-only investigation. Builds on `/tmp/studio_1a_internal_investigation_findings.md` and `/tmp/studio_shell_investigation_findings.md`, applies the R-7-α overrun pattern (verticals-lite precursor: 500-720 LOC estimate → 1,671 actual = 2.32x), and validates the DECISIONS.md 2026-05-13 "Studio shell arc decomposition" commitment that Live mode ships with the first Studio sub-arc.

---

## Section 1: Re-estimate each piece with R-7-α floor

R-7-α factor: take the upper bound from the prior estimate, multiply by 1.5 (midpoint case, ~50% above upper) for the realistic midpoint, and by 2.3 (matching the verticals-lite precursor's actual overrun) for worst case. Sub-agent execution ceiling treated as 2,000-2,500 LOC.

| # | Piece | Prior estimate (LOC) | Midpoint after R-7-α (×1.5 of upper) | Worst case (×2.3 of upper) | Ceiling flag |
|---|---|---|---|---|---|
| 1 | Studio routing + URL state model + redirect layer | 250-400 | ~600 | ~920 | OK |
| 2 | Studio rail component (icon-strip + expanded modes + scope picker) | 250-400 | ~600 | ~920 | OK |
| 3 | Editor adaptation pass (9 editors accept `studioRailExpanded`) | 300-500 | ~750 | ~1,150 | OK |
| 4 | Live mode wrap (`StudioLiveModeWrap` + `studioContext` prop + chrome conflict resolution + impersonation handshake + mode-toggle URL helper) | 300-500 | ~750 | ~1,150 | OK alone, contributes to ceiling pressure in aggregate |
| 5 | Placeholder overview surface (static section list at `/studio` and `/studio/{vertical}`) | (subset of 1a-i originally; not separately scoped in prior doc) ~100-200 | ~300 | ~460 | OK |
| 6 | Tests (vitest + pytest + Playwright smoke) | 600-900 | ~1,350 | ~2,070 | **Approaches ceiling alone**; in aggregate dominant |
| | **Sum** | **1,800-2,900** | **~4,350** | **~6,670** | **Well above ceiling** |

The prior doc's Studio 1a-i estimate ("~1,100-1,600 LOC" for the smaller cut from §6 of the internal investigation) understated by leaving out the larger pieces from the §6 table (overview + Live mode wrap were grouped into 1a-ii). The current build-prompt scope of 1a-i AS RESTATED IN THIS PROMPT bundles all six pieces — that's a 1,500-2,000 LOC estimate per the prompt's bracketing language. Applying R-7-α floor gives a realistic midpoint of ~4,000-4,500 LOC and a worst case approaching ~6,500 LOC.

**Key finding: Tests alone (piece 6) at worst case (~2,070 LOC) approach the ceiling.** This means tests cannot be combined with substantial implementation work in a single sub-agent run without exceeding the execution budget. Tests have to be split across sub-arcs whose implementations they cover.

**No single non-test piece breaches the 2,000-2,500 ceiling on its own at worst case.** Pieces 3 and 4 (editor adaptation + Live mode wrap) sit at ~1,150 LOC worst case, leaving headroom for piece-scoped tests. Pieces 1+2 (routing + rail) together sit at ~1,840 LOC worst case, fitting into a single sub-arc with their tests.

---

## Section 2: Natural split point analysis

### Is Live mode wrap mechanically independent?

Yes. Live mode wrap consumes Studio routing (knows about `/studio/live/*` paths), the Studio top bar (suppresses admin ribbon when `studioContext` is true), and the Studio rail (Live mode toggle button lives there). It does NOT depend on:

- Editor adaptation pass (editors are not mounted in Live mode — `RuntimeEditorShell` mounts `TenantRouteTree` instead)
- Inventory service / overview surface (Live mode never reads inventory)
- Placeholder overview content (Live mode bypasses `/studio` entirely once impersonation begins)

The minimum surface area Live mode wrap needs from 1a-i:
- The `/studio/live/*` route registration (routing piece, ~30 LOC subset of piece 1)
- A Studio top bar that accepts a `suppressAdminRibbon` indicator (rail piece subset, ~10 LOC)
- A "Live mode" button somewhere in the rail that navigates to `/studio/live` (rail piece subset, ~5 LOC)

Roughly 45 LOC of cross-piece surface. Otherwise self-contained.

### If Live mode wrap defers to 1a-i.5, what does the "Live mode" button do in 1a-i?

Three options:

| Option | Behavior | Trade-off |
|---|---|---|
| (a) "Coming soon" disabled affordance | Tooltip on hover, button is greyed | Operator never reaches runtime editor through Studio chrome in 1a-i; existing `/runtime-editor/*` still works standalone |
| (b) Link to old `/runtime-editor/*` | Button navigates out of Studio shell to the legacy URL | Operator gets runtime editor immediately; visual continuity broken (leaves Studio chrome); a brief intermediate UX |
| (c) Hidden | Rail simply omits the Live mode entry | Operator has no visible path to runtime editor from Studio; counter-intuitive given the prompt says Live mode is canon |

Option (b) is the cleanest temporary state — the legacy `/runtime-editor/*` remains a working URL until Studio 1a-i ships, and a brief detour out of Studio chrome is acceptable for a single transitional sub-arc. Option (a) is the "we're shipping Studio but Live mode isn't wired yet" affordance, more honest but more frustrating.

### DECISIONS.md 2026-05-13 commitment

> "Live mode ships in 1a-i, not deferred."

This commitment forces option (a) and (c) off the table for any decomposition that calls itself "Studio shell arc": Live mode must be wired in the first sub-arc that meets "Studio launched to operators." If 1a-i splits, the sub-arc containing Live mode wrap is by definition the first ship.

### Alternative split points

1. **Editor adaptation pass as own sub-arc**: 9 editors × ~30-60 LOC each + tests. Worst case ~1,150 LOC. Mechanically independent of routing AND Live mode (editors just learn to read a context value). Could ship as a precursor to or follow-on of the core shell. Trade-off: shipping it first means editors expose `studioRailExpanded` plumbing before there's a rail; shipping it second means rail renders without the icon-strip-vs-expanded coexistence working until the second arc lands. The first ordering is more graceful.

2. **Placeholder overview surface as separate sub-arc**: Static section list at `/studio` and `/studio/{vertical}`. ~100-200 LOC. Doesn't justify its own arc — fold into whichever sub-arc owns the rail.

3. **Redirect layer as precursor**: 10 standalone routes redirecting to Studio. ~80-120 LOC. Strictly speaking shippable as its own arc, but pointless to ship redirects to a non-existent `/studio` shell. The redirects MUST land in the same arc that introduces `/studio`.

### Smallest viable Studio that ships first

Defined as: operator navigates to `/studio`, sees chrome, clicks into editors, edits something. Not required: Live mode wired, overview populated, all redirects bulletproof, all 10 redirect routes covered.

Concrete contents:
- `/studio` route + minimal `<StudioShell />` with top bar + rail substrate
- Rail in expanded mode showing section list (no icon-strip mode required for SVS — that's polish)
- One scope: Platform only (no scope picker required for SVS — that's polish)
- Editor adaptation pass: 9 editors accept context but rendering can be no-op pass-through (just plumb the context value)
- At least one redirect: `/visual-editor` → `/studio` (proves the pattern; ship the rest as a polish pass)
- Placeholder overview at `/studio` (static section list)
- No Live mode

Estimated SVS LOC: ~600-900. **But: DECISIONS.md commitment forbids deferring Live mode beyond the first ship.** SVS is therefore not a valid sub-arc — must be expanded to include Live mode wrap.

---

## Section 3: Recommended decomposition

**Recommendation: split Studio 1a-i into TWO sub-arcs.**

### Studio 1a-i.A — Studio shell + rail + redirect + Live mode wrap

Sequenced first. Honors DECISIONS.md "Live mode from launch."

Contents:
1. Studio routing + URL state model + redirect layer (piece 1; ~250-400 → midpoint ~600, worst ~920)
2. Studio rail component (piece 2; ~250-400 → midpoint ~600, worst ~920) — scope picker reads `verticals` table from precursor
3. Live mode wrap (piece 4; ~300-500 → midpoint ~750, worst ~1,150)
4. Placeholder overview surface (piece 5 subset; ~100-200 → midpoint ~300, worst ~460)
5. Tests for routing, rail, Live mode wrap (piece 6 subset; ~400-600 → midpoint ~900, worst ~1,380)

**Estimated total**: midpoint ~3,150 LOC, worst case ~4,830 LOC.

This still exceeds the ceiling at worst case. The pressure comes from tests + Live mode wrap combined. Two mitigations:

- **(a) Trim test scope to "smoke + critical path" only.** Defer comprehensive coverage of rail icon-strip transitions, redirect query-param translation edge cases, and impersonation handshake corner cases to follow-on polish. This shaves ~400-600 LOC off worst case.
- **(b) Editor adaptation pass moves to sub-arc 1a-i.B.** Editors initially render outside Studio (link out to standalone `/visual-editor/{editor}`) for 1a-i.A; rail's section clicks resolve via the same redirect layer that takes a standalone request back into Studio in the next sub-arc.

Under mitigation (a) + scoping pressure (b): midpoint ~2,750 LOC, worst case ~4,200 LOC. **Still over ceiling at worst case.**

### Studio 1a-i.B — Editor adaptation pass

Contents:
1. 9 editors accept `studioRailExpanded` context (piece 3; ~300-500 → midpoint ~750, worst ~1,150)
2. Tests for adaptation pass (piece 6 subset; ~200-300 → midpoint ~450, worst ~690)

**Estimated total**: midpoint ~1,200 LOC, worst case ~1,840 LOC. **Fits ceiling cleanly.**

### Validation against the ceiling

| Sub-arc | Midpoint | Worst case | Ceiling fit |
|---|---|---|---|
| 1a-i.A | ~2,750 | ~4,200 | **At risk** — depends on test scope trimming holding |
| 1a-i.B | ~1,200 | ~1,840 | OK |

**1a-i.A worst case is still uncomfortable.** Consider a further cut:

### Option: three sub-arcs (1a-i.A1 / 1a-i.A2 / 1a-i.B)

| Sub-arc | Contents | Midpoint | Worst case |
|---|---|---|---|
| 1a-i.A1 | Routing + redirect layer + Studio rail + placeholder overview + smoke tests | ~1,500 | ~2,300 |
| 1a-i.A2 | Live mode wrap + chrome conflict resolution + impersonation handshake + mode-toggle URL helper + Live mode tests | ~1,250 | ~1,900 |
| 1a-i.B | Editor adaptation pass + tests | ~1,200 | ~1,840 |

All three fit the 2,000-2,500 ceiling at worst case.

**But: the DECISIONS.md commitment "Live mode ships in 1a-i, not deferred" prohibits shipping 1a-i.A1 alone as "Studio launched."** If the platform commits to operator-visible Studio in A1, Live mode must come with it. Two interpretations:

- **Strict reading**: 1a-i is defined as the first operator-visible Studio ship. A1 + A2 ship together as "1a-i" (paired commits, paired arc dispatch). Editor adaptation (B) is "1a-i.B" or renamed "1a-ii" but ships strictly after the operator-visible launch.
- **Pragmatic reading**: Live mode IS the operator's most visible reason to enter Studio (per DECISIONS.md 2026-05-13 "Live mode is vertical-or-tenant-tier authoring"). A1 without Live mode is not really "Studio launched" — it's a placeholder. A2 is the real launch.

Both readings preserve the DECISIONS.md spirit: Live mode is not deferred indefinitely to a follow-on arc; it ships with the first operator-visible Studio.

### Final recommendation

**Two sub-arcs:**

1. **Studio 1a-i.A — Studio shell + rail + redirect + Live mode wrap** (paired dispatch if needed; A1 + A2 as internal sequencing, but operator-visible ship as one unit). Estimated midpoint ~2,750 LOC, worst case ~4,200 LOC. **Must trim test scope to smoke + critical paths; comprehensive coverage deferred to polish.** May internally serialize as A1 (~2,300 worst) then A2 (~1,900 worst) if execution-budget pressure surfaces during build.
2. **Studio 1a-i.B — Editor adaptation pass + comprehensive tests** (~1,200 midpoint, ~1,840 worst case). Ships after 1a-i.A.

This decomposition:
- Honors DECISIONS.md "Live mode ships in first sub-arc"
- Keeps each ship within or near the ceiling (1a-i.A.worst is ~4,200 with internal A1+A2 split available as a fallback)
- Preserves the rail-collapses-not-replaces model (editor adaptation is real but lightweight; deferrable to a second sub-arc since rail can render its icon-strip even before editors learn to coexist)
- Treats 1a-i.B as a polish + completeness pass, not a feature regression

### Alternative if A1+A2 paired dispatch is unacceptable

If the build-time discipline requires "every sub-arc is one self-contained dispatch," go to the three-sub-arc decomposition (A1 / A2 / B). Operator-visible ship is then A1 (Studio without Live mode), which technically violates the DECISIONS.md commitment unless A1 + A2 are sequenced rapidly enough that operators don't see the in-between state. Document the deviation in DECISIONS.md as a build-time pragmatic exception rather than a canonical revision.

---

## Section 4: STATE.md staleness audit

### Migration head claim

STATE.md line 9: `Migration head: r95_verticals_table`.

`ls backend/alembic/versions/ | grep '^r' | sort -V | tail` confirms `r95_verticals_table.py` is the latest r-prefixed migration. Z-prefixed files exist but are alphabetically-later branch ancestors, not migration chain heads. **STATE.md migration head is accurate.**

### Active arc

STATE.md lines 37-39 say the active arc is the Studio shell precursors → Bridgeable Studio shell, with verticals-lite + Arc 4d + Arc 4a.2a all "just committed" and Studio 1a-i next.

`git log --oneline -10` confirms:
- `c70050f feat(verticals): verticals-lite precursor`
- `8affc8f feat(visual-editor): Arc 4a.2a`
- `9fbcab5 feat(visual-authoring): Arc 4d`

All three present at HEAD or near-HEAD. **STATE.md "Last shipped: Verticals-lite precursor (8affc8f)" is INACCURATE** — the verticals-lite commit is `c70050f`, not `8affc8f`. `8affc8f` is Arc 4a.2a. **Correction needed**: line 39's commit hash should read `c70050f`.

### Recently shipped rolling list

Cross-reference STATE.md lines 57-68 with `git log --oneline -15`:

| STATE.md entry | Commit per git | Match? |
|---|---|---|
| 1. Verticals-lite (this commit) | c70050f | ✅ but STATE.md says "this commit" which is now "last commit" |
| 2. Arc 4a.2a (8affc8f) | 8affc8f | ✅ |
| 3. Arc 4d (9fbcab5) | 9fbcab5 | ✅ |
| 4. Canon/state separation (c655771) | c655771 | ✅ |
| 5. Arc 4c (efeed99) | efeed99 | ✅ |
| 6. Arc 4b.2b (7ff864a) | 7ff864a | ✅ |
| 7. Arc 4b.2a (66ec8c5) | 66ec8c5 | ✅ |
| 8. Arc 4b.1b (a534adb) | a534adb | ✅ |
| 9. Arc 4b.1a (3008ca2) | 3008ca2 | ✅ |
| 10. Arc 4a.1 (63fc1c2) | 63fc1c2 | ✅ |

All ten entries present. Order matches.

**Single defect: line 38's "Last shipped" assertion is mis-attributed.** Line 38 says "Last shipped: Verticals-lite precursor (`8affc8f` chain, 2026-05-13)." The commit `8affc8f` is Arc 4a.2a, not verticals-lite. Verticals-lite is `c70050f`. The "chain" qualifier doesn't resolve this — `c70050f` is the verticals-lite commit, full stop.

### Active deferred items

Line 44 references "Studio shell arc — three sub-arcs sequenced post-verticals-lite." Per this investigation, the actual decomposition is now TWO sub-arcs (1a-i.A + 1a-i.B) with the prior "1a-ii" rolled into 1a-i.A. STATE.md should reflect this once a decomposition is locked.

Line 45 references Arc 4a.2b as "sibling of Arc 4a.2a (committed `8affc8f`)" — accurate.

No items appear to be shipped-but-still-deferred. Cross-check of recent commits against deferred items shows no overlap.

**Audit corrections needed (do NOT modify STATE.md per task constraint):**
1. Line 39: change `8affc8f` to `c70050f` for verticals-lite Last shipped attribution.
2. Line 44 (and decomposition framing in lines 37-38): update Studio shell sub-arc count from three to two once the decomposition lock is committed via DECISIONS.md.

---

## Section 5: Working-tree contamination check

### git status

`On branch main` / `Your branch is up to date with 'origin/main'` / `nothing to commit, working tree clean`. **Clean.**

### Local commits ahead of origin

`git log origin/main..HEAD --oneline` returns empty output. **No local commits ahead of origin.**

### /tmp/ artifacts referenced as live state

`grep -rn "/tmp/" CLAUDE.md STATE.md DECISIONS.md` returns:

- **STATE.md line 38**: references `/tmp/studio_1a_internal_investigation_findings.md` in the "Current phase" description.
- **STATE.md line 44**: same `/tmp/` doc reference in the Studio shell active-deferred entry.
- **DECISIONS.md line 46**: references `/tmp/studio_shell_investigation_findings.md` § 2 in the Spaces substrate decision.

These references are **load-bearing in non-canonical state documents** — STATE.md and DECISIONS.md cite /tmp/ investigation docs as authoritative inputs. Per the prompt's framing, /tmp/ artifacts are scratch / intermediate; relying on them in STATE.md or DECISIONS.md risks future readers hitting stale or absent files (the /tmp/ docs are session-scoped and not committed).

**Recommendation (do NOT fix per task constraint)**: when the Studio shell arc closes, fold the canonical conclusions from `/tmp/studio_1a_internal_investigation_findings.md` and `/tmp/studio_shell_investigation_findings.md` into DECISIONS.md (or a permanent design doc), then strip the /tmp/ references from STATE.md / DECISIONS.md. Until then the references are tolerable as transient pointers during the active arc.

CLAUDE.md has no /tmp/ references. Clean on the canon side.

---

## Required signoff

Findings document absolute path: **`/tmp/studio_1a_i_scoping_findings.md`**

Most consequential finding: **The combined Studio 1a-i bundle (six pieces — routing, rail, editor adaptation, Live mode wrap, placeholder overview, tests) lands at ~4,000-4,500 LOC midpoint and ~6,500 LOC worst case under R-7-α floor — well above the 2,000-2,500 sub-agent execution ceiling.** The clean split is two sub-arcs: **1a-i.A** (shell + rail + redirect + Live mode wrap + placeholder overview + smoke tests, ~2,750 midpoint / ~4,200 worst with test scope trimming, internally splittable into A1 + A2 if needed) and **1a-i.B** (editor adaptation pass + comprehensive tests, ~1,200 midpoint / ~1,840 worst). This honors the DECISIONS.md 2026-05-13 commitment that Live mode ships with the first operator-visible Studio launch (1a-i.A), defers only the lightweight editor adaptation work to a follow-on (1a-i.B), and preserves the rail-collapses-not-replaces canon by treating editor adaptation as plumbing-without-feature-regression. If A1+A2 paired dispatch is unacceptable to the build-time discipline, fall back to a three-sub-arc decomposition (A1 / A2 / B) and document the brief in-between state where Studio ships without Live mode as a pragmatic exception in DECISIONS.md.

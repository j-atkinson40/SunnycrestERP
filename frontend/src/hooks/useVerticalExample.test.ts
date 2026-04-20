/**
 * Vertical-aware example hook — unit tests.
 *
 * Parametrized across all 4 verticals × 8 categories = 32 assertions,
 * plus 1 null-vertical fallback + 2 unknown-vertical-fallback cases
 * + normalization of case/underscore variants.
 *
 * Tests the pure lookup function (`getVerticalExample`). The React
 * hook form is covered implicitly by the 5 Playwright tooltip specs
 * that run the real auth context + render the tooltip content.
 */

import { describe, expect, it } from "vitest";
import {
  _TEST_CATEGORIES,
  _TEST_EXAMPLES_TABLE,
  _TEST_VERTICALS,
  getVerticalExample,
  type ExampleCategory,
  type VerticalName,
} from "./useVerticalExample";


describe("getVerticalExample — full coverage matrix", () => {
  for (const vertical of _TEST_VERTICALS) {
    for (const category of _TEST_CATEGORIES) {
      it(`${vertical} / ${category} returns expected value`, () => {
        const expected = _TEST_EXAMPLES_TABLE[vertical][category];
        expect(getVerticalExample(vertical, category)).toBe(expected);
        // Also sanity-check that expected is a non-empty string.
        expect(expected.length).toBeGreaterThan(0);
      });
    }
  }
});


describe("getVerticalExample — specific word choices (regression guard)", () => {
  // If a future refactor changes these, it's a deliberate product
  // decision + needs a test update. Better to fail loudly than
  // silently drift.
  it("manufacturing new_primary is 'new order' (not 'new work order')", () => {
    expect(getVerticalExample("manufacturing", "new_primary")).toBe("new order");
  });

  it("funeral_home new_primary is 'new case' (not 'new arrangement')", () => {
    expect(getVerticalExample("funeral_home", "new_primary")).toBe("new case");
  });

  it("cemetery primary_entity is 'burial' (refined from 'interment')", () => {
    // Approved refinement — operational default, more natural in tooltips.
    expect(getVerticalExample("cemetery", "primary_entity")).toBe("burial");
  });

  it("cemetery secondary_entity is 'plot' (not 'grave')", () => {
    expect(getVerticalExample("cemetery", "secondary_entity")).toBe("plot");
  });

  it("crematory secondary_entity is 'service' (intentional per spec)", () => {
    // No FH collision for a crematory-only tenant.
    expect(getVerticalExample("crematory", "secondary_entity")).toBe("service");
  });

  it("queue_primary maps per-vertical for command-bar hints", () => {
    expect(getVerticalExample("manufacturing", "queue_primary")).toBe("invoice");
    expect(getVerticalExample("funeral_home", "queue_primary")).toBe("approval");
    expect(getVerticalExample("cemetery", "queue_primary")).toBe("approval");
    expect(getVerticalExample("crematory", "queue_primary")).toBe("certificate");
  });
});


describe("getVerticalExample — null / unknown / normalization", () => {
  it("null vertical falls back to manufacturing", () => {
    expect(getVerticalExample(null, "new_primary")).toBe("new order");
  });

  it("undefined vertical falls back to manufacturing", () => {
    expect(getVerticalExample(undefined, "new_primary")).toBe("new order");
  });

  it("empty string falls back to manufacturing", () => {
    expect(getVerticalExample("", "new_primary")).toBe("new order");
  });

  it("unknown vertical string falls back to manufacturing", () => {
    expect(getVerticalExample("retail", "new_primary")).toBe("new order");
    expect(getVerticalExample("warehouse", "primary_entity")).toBe("order");
  });

  it("uppercase input normalizes", () => {
    expect(getVerticalExample("MANUFACTURING", "new_primary")).toBe("new order");
    expect(getVerticalExample("Funeral_Home", "new_primary")).toBe("new case");
  });

  it("'funeralhome' (no underscore) normalizes to funeral_home", () => {
    // Defensive: some legacy data has `tenant_type="funeralhome"`.
    expect(getVerticalExample("funeralhome", "new_primary")).toBe("new case");
  });
});


describe("getVerticalExample — no cross-vertical language leak", () => {
  // Critical invariant: a manufacturing query should never return
  // FH-specific terminology, and vice versa. This is the bug the
  // whole feature targets; assert it explicitly.
  const FH_TERMS = ["case", "arrangement", "deceased", "family"];
  const MFG_TERMS = ["order", "work order", "production"];
  const CEMETERY_TERMS = ["burial", "interment", "plot"];
  const CREMATORY_TERMS = ["cremation", "certificate"];

  const hasAny = (s: string, needles: string[]) =>
    needles.some((n) => s.toLowerCase().includes(n));

  it("manufacturing returns no FH terminology", () => {
    for (const cat of _TEST_CATEGORIES) {
      const val = getVerticalExample("manufacturing", cat);
      // Manufacturing shouldn't contain "case", "arrangement",
      // "deceased", or "family" in any category. "family" in
      // "primary family" would be a bug.
      expect(
        hasAny(val, FH_TERMS),
        `manufacturing.${cat} = "${val}" leaks FH term`,
      ).toBe(false);
    }
  });

  it("funeral_home returns no MFG terminology", () => {
    for (const cat of _TEST_CATEGORIES) {
      const val = getVerticalExample("funeral_home", cat);
      expect(
        hasAny(val, MFG_TERMS),
        `funeral_home.${cat} = "${val}" leaks MFG term`,
      ).toBe(false);
    }
  });

  it("cemetery uses cemetery-specific terminology", () => {
    // At least one category should reference a cemetery term —
    // otherwise we've regressed to generic language.
    const anyHit = _TEST_CATEGORIES.some((cat) =>
      hasAny(getVerticalExample("cemetery", cat), CEMETERY_TERMS),
    );
    expect(anyHit).toBe(true);
  });

  it("crematory uses crematory-specific terminology", () => {
    const anyHit = _TEST_CATEGORIES.some((cat) =>
      hasAny(getVerticalExample("crematory", cat), CREMATORY_TERMS),
    );
    expect(anyHit).toBe(true);
  });
});


describe("getVerticalExample — table shape", () => {
  it("every vertical has every category", () => {
    for (const v of _TEST_VERTICALS as VerticalName[]) {
      for (const c of _TEST_CATEGORIES as ExampleCategory[]) {
        const val = _TEST_EXAMPLES_TABLE[v][c];
        expect(val, `${v}.${c} is missing`).toBeTruthy();
        expect(typeof val).toBe("string");
      }
    }
  });
});

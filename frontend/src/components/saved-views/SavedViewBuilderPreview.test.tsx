/**
 * SavedViewBuilderPreview — vitest unit tests.
 *
 * Focuses on the two pieces of logic the component OWNS that are
 * cheap to unit-test without a DOM harness: the mode-switch cache
 * fingerprint + the pre-render mode hint.
 *
 * DOM-level integration (loading/empty/error/populated rendering,
 * debounce cancellation, refresh button) is covered by the Playwright
 * spec — it runs the real builder with the real network so behaviour
 * drift surfaces end-to-end.
 */

import { describe, expect, it } from "vitest";

import {
  aggregationModeOf,
  computeFingerprint,
  requiredSubConfigHint,
} from "./SavedViewBuilderPreview";
import type {
  Filter,
  Presentation,
  SavedViewConfig,
} from "@/types/saved-views";


function baseConfig(
  overrides: {
    filters?: Filter[];
    presentation?: Partial<Presentation>;
  } = {},
): SavedViewConfig {
  return {
    query: {
      entity_type: "sales_order",
      filters: overrides.filters ?? [],
      sort: [],
      grouping: null,
      limit: null,
    },
    presentation: {
      mode: "list",
      ...(overrides.presentation ?? {}),
    },
    permissions: {
      owner_user_id: "u1",
      visibility: "private",
    },
    extras: {},
  };
}


// ── aggregationModeOf ───────────────────────────────────────────────


describe("aggregationModeOf", () => {
  it("maps chart → chart", () => {
    expect(aggregationModeOf("chart")).toBe("chart");
  });
  it("maps stat → stat", () => {
    expect(aggregationModeOf("stat")).toBe("stat");
  });
  it("maps every non-aggregation mode → none", () => {
    for (const m of ["list", "table", "kanban", "calendar", "cards"] as const) {
      expect(aggregationModeOf(m)).toBe("none");
    }
  });
});


// ── computeFingerprint ──────────────────────────────────────────────


describe("computeFingerprint — mode-swap cache semantics", () => {
  it("same query + different non-aggregation modes collapse to same fingerprint", () => {
    const list = baseConfig({ presentation: { mode: "list" } });
    const table = baseConfig({ presentation: { mode: "table" } });
    const kanban = baseConfig({ presentation: { mode: "kanban" } });
    const calendar = baseConfig({ presentation: { mode: "calendar" } });
    const cards = baseConfig({ presentation: { mode: "cards" } });
    const fp = computeFingerprint(list);
    expect(computeFingerprint(table)).toBe(fp);
    expect(computeFingerprint(kanban)).toBe(fp);
    expect(computeFingerprint(calendar)).toBe(fp);
    expect(computeFingerprint(cards)).toBe(fp);
  });

  it("swapping INTO chart differs from non-aggregation fingerprint", () => {
    const list = baseConfig({ presentation: { mode: "list" } });
    const chart = baseConfig({
      presentation: {
        mode: "chart",
        chart_config: {
          chart_type: "bar",
          x_field: "status",
          y_field: "total",
          y_aggregation: "sum",
        },
      },
    });
    expect(computeFingerprint(chart)).not.toBe(computeFingerprint(list));
  });

  it("swapping INTO stat differs from non-aggregation fingerprint", () => {
    const list = baseConfig({ presentation: { mode: "list" } });
    const stat = baseConfig({
      presentation: {
        mode: "stat",
        stat_config: { metric_field: "total", aggregation: "sum" },
      },
    });
    expect(computeFingerprint(stat)).not.toBe(computeFingerprint(list));
  });

  it("chart config changes (x_field) produce a fresh fingerprint", () => {
    const c1 = baseConfig({
      presentation: {
        mode: "chart",
        chart_config: {
          chart_type: "bar",
          x_field: "status",
          y_field: "total",
          y_aggregation: "sum",
        },
      },
    });
    const c2 = baseConfig({
      presentation: {
        mode: "chart",
        chart_config: {
          chart_type: "bar",
          x_field: "customer_id",
          y_field: "total",
          y_aggregation: "sum",
        },
      },
    });
    expect(computeFingerprint(c1)).not.toBe(computeFingerprint(c2));
  });

  it("changing a filter value invalidates the fingerprint", () => {
    const a = baseConfig({
      filters: [{ field: "status", operator: "eq", value: "draft" }],
    });
    const b = baseConfig({
      filters: [{ field: "status", operator: "eq", value: "sent" }],
    });
    expect(computeFingerprint(a)).not.toBe(computeFingerprint(b));
  });

  it("changing a filter field invalidates the fingerprint", () => {
    const a = baseConfig({
      filters: [{ field: "status", operator: "eq", value: "draft" }],
    });
    const b = baseConfig({
      filters: [{ field: "customer_id", operator: "eq", value: "draft" }],
    });
    expect(computeFingerprint(a)).not.toBe(computeFingerprint(b));
  });

  it("identical configs produce identical fingerprints (stable, not object-identity)", () => {
    const a = baseConfig({
      filters: [{ field: "status", operator: "eq", value: "draft" }],
    });
    const b = baseConfig({
      filters: [{ field: "status", operator: "eq", value: "draft" }],
    });
    expect(a).not.toBe(b); // different object refs
    expect(computeFingerprint(a)).toBe(computeFingerprint(b));
  });
});


// ── requiredSubConfigHint ───────────────────────────────────────────


describe("requiredSubConfigHint", () => {
  it("returns null for list", () => {
    expect(requiredSubConfigHint(baseConfig())).toBeNull();
  });

  it("returns null for table (columns are optional)", () => {
    expect(
      requiredSubConfigHint(baseConfig({ presentation: { mode: "table" } })),
    ).toBeNull();
  });

  it("returns kanban hint when group_by_field missing", () => {
    const hint = requiredSubConfigHint(
      baseConfig({ presentation: { mode: "kanban" } }),
    );
    expect(hint?.title).toMatch(/group-by/i);
    expect(hint?.description).toMatch(/presentation/i);
  });

  it("returns kanban hint for missing card_title_field", () => {
    const hint = requiredSubConfigHint(
      baseConfig({
        presentation: {
          mode: "kanban",
          kanban_config: {
            group_by_field: "status",
            card_title_field: "",
            card_meta_fields: [],
          },
        },
      }),
    );
    expect(hint?.title).toMatch(/card title/i);
  });

  it("returns null when kanban is fully configured", () => {
    expect(
      requiredSubConfigHint(
        baseConfig({
          presentation: {
            mode: "kanban",
            kanban_config: {
              group_by_field: "status",
              card_title_field: "number",
              card_meta_fields: [],
            },
          },
        }),
      ),
    ).toBeNull();
  });

  it("returns calendar hint when date_field missing", () => {
    const hint = requiredSubConfigHint(
      baseConfig({ presentation: { mode: "calendar" } }),
    );
    expect(hint?.title).toMatch(/date field/i);
  });

  it("returns calendar hint when label_field missing but date_field set", () => {
    const hint = requiredSubConfigHint(
      baseConfig({
        presentation: {
          mode: "calendar",
          calendar_config: { date_field: "order_date", label_field: "" },
        },
      }),
    );
    expect(hint?.title).toMatch(/label field/i);
  });

  it("returns cards hint when title_field missing", () => {
    const hint = requiredSubConfigHint(
      baseConfig({ presentation: { mode: "cards" } }),
    );
    expect(hint?.title).toMatch(/title field/i);
  });

  it("returns chart hint when chart_type / x_field / aggregation missing", () => {
    const hint = requiredSubConfigHint(
      baseConfig({ presentation: { mode: "chart" } }),
    );
    expect(hint?.title).toMatch(/chart/i);
  });

  it("returns stat hint when metric_field missing", () => {
    const hint = requiredSubConfigHint(
      baseConfig({ presentation: { mode: "stat" } }),
    );
    expect(hint?.title).toMatch(/stat/i);
  });

  it("returns null when stat is fully configured", () => {
    expect(
      requiredSubConfigHint(
        baseConfig({
          presentation: {
            mode: "stat",
            stat_config: { metric_field: "total", aggregation: "sum" },
          },
        }),
      ),
    ).toBeNull();
  });
});

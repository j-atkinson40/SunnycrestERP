/**
 * Tests for the composition blob codec (WB-1).
 *
 * Covers canonical-example round-trip safety, deterministic
 * serialization (key ordering), and structural error cases.
 */

import { describe, expect, it } from "vitest";

import {
  CompositionBlobParseError,
  parseCompositionBlob,
  serializeCompositionBlob,
} from "./composition-blob-codec";
import type { CompositionBlob } from "./types/composition-blob";

function canonicalExample(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column", gap_token: "sm" },
        children: ["title", "value"],
        binding_refs: { condition: "b-cond" },
      },
      title: {
        atom_id: "title",
        atom_type: "text_label",
        config: { typography_token: "h3" },
        visible_in_variants: ["brief", "detail"],
        binding_refs: { text: "b-name" },
      },
      value: {
        atom_id: "value",
        atom_type: "value_display",
        config: { format: "currency", format_config: { currency: "USD" } },
        binding_refs: { value: "b-amount" },
      },
    },
    variants: [
      {
        variant_id: "brief",
        variant_name: "Brief",
        target_surface: "focus_canvas",
        canonical_dimensions: { width: 320, height: 200 },
      },
      {
        variant_id: "detail",
        variant_name: "Detail",
        target_surface: "page_canvas",
      },
    ],
    bindings_catalog: {
      "b-cond": {
        binding_id: "b-cond",
        binding_type: "literal",
        literal_value: true,
      },
      "b-name": {
        binding_id: "b-name",
        binding_type: "field_path",
        saved_view_id: "view-deliveries",
        field_path: "delivery.driver_name",
        iteration_mode: "per_row",
      },
      "b-amount": {
        binding_id: "b-amount",
        binding_type: "field_path",
        saved_view_id: "view-deliveries",
        field_path: "delivery.amount",
        iteration_mode: "per_row",
      },
    },
  };
}

describe("parseCompositionBlob", () => {
  it("parses the canonical Phase 1 example cleanly", () => {
    const blob = parseCompositionBlob(canonicalExample());
    expect(blob.root_atom_id).toBe("root");
    expect(Object.keys(blob.atom_tree)).toHaveLength(3);
    expect(blob.variants).toHaveLength(2);
    expect(Object.keys(blob.bindings_catalog)).toHaveLength(3);
  });

  it("throws on non-object input", () => {
    expect(() => parseCompositionBlob(null)).toThrow(
      CompositionBlobParseError,
    );
    expect(() => parseCompositionBlob(42)).toThrow(CompositionBlobParseError);
    expect(() => parseCompositionBlob("string")).toThrow(
      CompositionBlobParseError,
    );
  });

  it("rejects schema_version != 1", () => {
    const raw = { ...canonicalExample(), schema_version: 2 as unknown as 1 };
    expect(() => parseCompositionBlob(raw)).toThrow(
      CompositionBlobParseError,
    );
  });

  it("rejects unknown atom_type", () => {
    const raw = canonicalExample();
    (raw.atom_tree.title as unknown as { atom_type: string }).atom_type =
      "spark_line";
    expect(() => parseCompositionBlob(raw)).toThrow(
      CompositionBlobParseError,
    );
  });

  it("rejects unknown binding_type", () => {
    const raw = canonicalExample();
    (
      raw.bindings_catalog["b-cond"] as unknown as { binding_type: string }
    ).binding_type = "expression";
    expect(() => parseCompositionBlob(raw)).toThrow(
      CompositionBlobParseError,
    );
  });

  it("rejects unknown target_surface", () => {
    const raw = canonicalExample();
    (
      raw.variants[0] as unknown as { target_surface: string }
    ).target_surface = "moon_canvas";
    expect(() => parseCompositionBlob(raw)).toThrow(
      CompositionBlobParseError,
    );
  });

  it("rejects non-string atom_id", () => {
    const raw = canonicalExample();
    (raw.atom_tree.title as unknown as { atom_id: unknown }).atom_id = 42;
    expect(() => parseCompositionBlob(raw)).toThrow(
      CompositionBlobParseError,
    );
  });

  it("collects errors into the thrown error's errors array", () => {
    const raw = canonicalExample();
    (raw.atom_tree.title as unknown as { atom_type: string }).atom_type =
      "BAD";
    (
      raw.bindings_catalog["b-cond"] as unknown as { binding_type: string }
    ).binding_type = "WORSE";
    try {
      parseCompositionBlob(raw);
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(CompositionBlobParseError);
      expect((e as CompositionBlobParseError).errors.length).toBeGreaterThan(
        1,
      );
    }
  });
});

describe("serializeCompositionBlob", () => {
  it("produces deterministic key ordering", () => {
    const blob = canonicalExample();
    const s1 = serializeCompositionBlob(blob);
    // Construct an equivalent blob with intentionally-shuffled top-
    // level key order; both should serialize identically.
    const reshuffled: CompositionBlob = {
      bindings_catalog: blob.bindings_catalog,
      atom_tree: blob.atom_tree,
      variants: blob.variants,
      schema_version: blob.schema_version,
      root_atom_id: blob.root_atom_id,
    } as CompositionBlob;
    const s2 = serializeCompositionBlob(reshuffled);
    expect(s1).toBe(s2);
  });

  it("sorts keys at every nested level", () => {
    const blob = canonicalExample();
    const serialized = serializeCompositionBlob(blob);
    const parsed = JSON.parse(serialized);
    // Top-level keys sorted.
    expect(Object.keys(parsed)).toEqual(
      Object.keys(parsed).slice().sort(),
    );
    // Atom-tree-entry keys sorted.
    for (const key of Object.keys(parsed.atom_tree)) {
      const atomKeys = Object.keys(parsed.atom_tree[key]);
      expect(atomKeys).toEqual(atomKeys.slice().sort());
    }
  });

  it("round-trips canonical example", () => {
    const blob = canonicalExample();
    const serialized = serializeCompositionBlob(blob);
    const re = parseCompositionBlob(JSON.parse(serialized));
    // Re-serialize: equal bytes.
    expect(serializeCompositionBlob(re)).toBe(serialized);
  });

  // ── WB-3 — repeater_atom round-trip + nesting-cap rejection ──────

  it("accepts repeater_atom in atom_tree (WB-3)", () => {
    const blob = parseCompositionBlob({
      schema_version: 1,
      root_atom_id: "root",
      atom_tree: {
        root: {
          atom_id: "root",
          atom_type: "repeater_atom",
          config: {
            binding_id: "rows",
            children: ["row_label"],
            direction: "column",
            spacing: "normal",
          },
          children: ["row_label"],
          binding_refs: { rows: "rows" },
        },
        row_label: {
          atom_id: "row_label",
          atom_type: "text_label",
          config: {},
        },
      },
      variants: [
        {
          variant_id: "brief",
          variant_name: "Brief",
          target_surface: "focus_canvas",
        },
      ],
      bindings_catalog: {
        rows: {
          binding_id: "rows",
          binding_type: "field_path",
          saved_view_id: "sv1",
          field_path: "rows",
          iteration_mode: "per_row",
        },
      },
    });
    expect(blob.atom_tree.root.atom_type).toBe("repeater_atom");
    const reSerialized = serializeCompositionBlob(blob);
    const re = parseCompositionBlob(JSON.parse(reSerialized));
    expect(serializeCompositionBlob(re)).toBe(reSerialized);
  });

  it("rejects repeater_atom containing another repeater_atom (WB-3 cap)", () => {
    expect(() =>
      parseCompositionBlob({
        schema_version: 1,
        root_atom_id: "root",
        atom_tree: {
          root: {
            atom_id: "root",
            atom_type: "repeater_atom",
            config: {
              binding_id: "rows",
              children: ["nested"],
              direction: "column",
              spacing: "normal",
            },
            children: ["nested"],
            binding_refs: { rows: "rows" },
          },
          nested: {
            atom_id: "nested",
            atom_type: "repeater_atom",
            config: {
              binding_id: "rows",
              children: [],
              direction: "column",
              spacing: "normal",
            },
            children: [],
            binding_refs: { rows: "rows" },
          },
        },
        variants: [],
        bindings_catalog: {
          rows: {
            binding_id: "rows",
            binding_type: "field_path",
            saved_view_id: "sv1",
            field_path: "rows",
            iteration_mode: "per_row",
          },
        },
      }),
    ).toThrow(/may not contain another repeater_atom/);
  });
});

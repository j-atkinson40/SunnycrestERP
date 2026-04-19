/**
 * Tests for renderTemplatePreview — the client-side {{ var }} substitution
 * used by the Preview modal so admins can sanity-check a prompt without
 * burning API credits.
 *
 * This is pure string substitution (not a real Jinja runtime) — the
 * contract is: defined vars substitute, undefined vars pass through so
 * the admin can see they're unresolved.
 */

import { describe, expect, it } from "vitest";
import { renderTemplatePreview } from "./VariablesEditor";

describe("renderTemplatePreview", () => {
  it("substitutes a simple {{ var }} with its string value", () => {
    expect(
      renderTemplatePreview("Hello {{ name }}!", { name: "World" }),
    ).toBe("Hello World!");
  });

  it("allows whitespace variations around the variable name", () => {
    expect(
      renderTemplatePreview("A {{name}} B {{ name }} C {{  name  }} D", {
        name: "X",
      }),
    ).toBe("A X B X C X D");
  });

  it("leaves undefined variables visible so the admin knows they're unresolved", () => {
    expect(
      renderTemplatePreview("Hi {{ name }} from {{ city }}", { name: "Jim" }),
    ).toBe("Hi Jim from {{ city }}");
  });

  it("treats null / undefined / empty-string values as unresolved", () => {
    expect(
      renderTemplatePreview("a={{ a }} b={{ b }} c={{ c }}", {
        a: null,
        b: undefined,
        c: "",
      }),
    ).toBe("a={{ a }} b={{ b }} c={{ c }}");
  });

  it("JSON-stringifies non-string values (numbers, objects, arrays)", () => {
    expect(
      renderTemplatePreview("n={{ n }} o={{ o }} l={{ l }}", {
        n: 42,
        o: { x: 1 },
        l: [1, 2, 3],
      }),
    ).toBe('n=42 o={"x":1} l=[1,2,3]');
  });

  it("preserves the false value (as JSON 'false', not unresolved)", () => {
    expect(renderTemplatePreview("ok={{ ok }}", { ok: false })).toBe("ok=false");
  });

  it("preserves the number 0 (as '0', not unresolved)", () => {
    expect(renderTemplatePreview("n={{ n }}", { n: 0 })).toBe("n=0");
  });

  it("only matches bare identifiers — does not interpret dotted paths", () => {
    // The preview deliberately doesn't walk paths — that would require a
    // real Jinja runtime. Dotted references stay unresolved.
    expect(
      renderTemplatePreview("{{ user.name }}", { "user.name": "ignored" }),
    ).toBe("{{ user.name }}");
  });

  it("leaves non-identifier interpolations alone", () => {
    // `{{ 1 }}` has no identifier character at position 0 — regex ignores it
    expect(renderTemplatePreview("x={{ 1 }}", { "1": "one" })).toBe("x={{ 1 }}");
  });

  it("handles empty templates", () => {
    expect(renderTemplatePreview("", { x: "y" })).toBe("");
  });

  it("handles templates with no variables", () => {
    expect(renderTemplatePreview("just plain text", {})).toBe("just plain text");
  });

  it("allows the same variable multiple times", () => {
    expect(
      renderTemplatePreview("{{ x }} and {{ x }} and {{ x }}", { x: "hi" }),
    ).toBe("hi and hi and hi");
  });
});

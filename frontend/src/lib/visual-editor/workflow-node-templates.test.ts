/**
 * workflow-node-templates tests — inline-params P1 engine + 32-template
 * guard. Pure-function coverage (parse/interpolate/resolveSlot) +
 * the drift-catching guard that every template {slot} references a real
 * SEMANTIC param of its type. Registry populated via auto-register.
 */
import { describe, expect, it } from "vitest"

import "@/lib/visual-editor/registry/auto-register"
import {
  NODE_LABEL_TEMPLATES,
  VESTIGIAL_VISUAL_PARAMS,
  semanticParams,
  isEditableToken,
  isTokenInlineEditable,
  EDITABLE_TOKEN_TYPES,
  BESPOKE_NAMESPACE_TYPES,
  INSPECTOR_HIDDEN_PARAMS,
  unslottedParams,
  NOT_YET_IMPLEMENTED_PARAMS,
  parseTemplate,
  resolveSlot,
  summarizeValue,
  humanizeParam,
  renderModelFor,
  templateFor,
} from "./workflow-node-templates"
import { getByType } from "@/lib/visual-editor/registry"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry/types"

describe("workflow-node-templates — parseTemplate", () => {
  it("a no-slot template is a single literal", () => {
    expect(parseTemplate("Start")).toEqual([{ kind: "literal", text: "Start" }])
  })
  it("splits one slot into literal + slot", () => {
    expect(parseTemplate("Wait {durationSeconds}")).toEqual([
      { kind: "literal", text: "Wait " },
      { kind: "slot", param: "durationSeconds" },
    ])
  })
  it("splits multiple slots with literals between", () => {
    expect(
      parseTemplate("Send {templateKey} to {recipientBinding} via {deliveryChannel}"),
    ).toEqual([
      { kind: "literal", text: "Send " },
      { kind: "slot", param: "templateKey" },
      { kind: "literal", text: " to " },
      { kind: "slot", param: "recipientBinding" },
      { kind: "literal", text: " via " },
      { kind: "slot", param: "deliveryChannel" },
    ])
  })
  it("handles a leading slot + trailing literal", () => {
    expect(parseTemplate("{a} done")).toEqual([
      { kind: "slot", param: "a" },
      { kind: "literal", text: " done" },
    ])
  })
})

describe("workflow-node-templates — humanizeParam", () => {
  it("camelCase → spaced lower", () => {
    expect(humanizeParam("recipientBinding")).toBe("recipient binding")
  })
  it("snake/kebab → spaced lower", () => {
    expect(humanizeParam("entity_type")).toBe("entity type")
    expect(humanizeParam("target-tenant")).toBe("target tenant")
  })
})

describe("workflow-node-templates — summarizeValue", () => {
  it("object → N fields", () => {
    expect(summarizeValue("fieldBindings", { a: 1, b: 2, c: 3 })).toBe("3 fields")
    expect(summarizeValue("x", { only: 1 })).toBe("1 field")
  })
  it("array branches → N branches", () => {
    expect(summarizeValue("branches", [1, 2])).toBe("2 branches")
    expect(summarizeValue("branches", [1])).toBe("1 branch")
  })
  it("array (non-branches) → N items", () => {
    expect(summarizeValue("things", [1, 2, 3])).toBe("3 items")
    expect(summarizeValue("things", [1])).toBe("1 item")
  })
})

describe("workflow-node-templates — resolveSlot", () => {
  const str: ConfigPropSchema = { type: "string", default: "" }
  const enm: ConfigPropSchema = { type: "enum", default: "a", bounds: ["a", "b"] }
  const obj: ConfigPropSchema = { type: "object", default: {} }
  const arr: ConfigPropSchema = { type: "array", default: [] }

  it("unset (no value, empty default) → dimmed placeholder", () => {
    const t = resolveSlot("recipientBinding", {}, str)
    expect(t.placeholder).toBe(true)
    expect(t.text).toBe("[recipient binding]")
  })
  it("set string → the value", () => {
    const t = resolveSlot("recipientBinding", { recipientBinding: "ops@x" }, str)
    expect(t.placeholder).toBe(false)
    expect(t.text).toBe("ops@x")
  })
  it("set enum → the chosen option", () => {
    expect(resolveSlot("model", { model: "haiku" }, enm).text).toBe("haiku")
  })
  it("object value → N fields summary", () => {
    expect(resolveSlot("fieldBindings", { fieldBindings: { a: 1, b: 2 } }, obj).text).toBe(
      "2 fields",
    )
  })
  it("array value → N branches summary", () => {
    expect(resolveSlot("branches", { branches: [1, 2, 3] }, arr).text).toBe("3 branches")
  })
  it("componentReference → resolved display name (raw ref if unresolvable)", () => {
    const cr: ConfigPropSchema = { type: "componentReference", default: "" }
    // unknown focus-template ref → raw ref kept.
    expect(
      resolveSlot("focusTemplateName", { focusTemplateName: "no-such-tpl" }, cr).text,
    ).toBe("no-such-tpl")
  })
})

describe("workflow-node-templates — interpolate / renderModelFor", () => {
  it("interpolates a real type's template — set vs default vs placeholder", () => {
    // config empty: templateKey + entityBinding default "" → placeholders;
    // outputFormat has a non-empty default ("pdf") → value token.
    const model = renderModelFor("generate_document", { templateKey: "death-cert" })
    expect(model).not.toBeNull()
    const tokens = model!.filter((s) => s.kind === "token")
    expect(tokens.length).toBe(3) // templateKey, entityBinding, outputFormat
    const byParam = Object.fromEntries(
      tokens.map((t) => [(t as { param: string }).param, t]),
    )
    expect((byParam.templateKey as { text: string }).text).toBe("death-cert")
    // entityBinding unset + empty default → placeholder.
    expect((byParam.entityBinding as { placeholder: boolean }).placeholder).toBe(true)
    // outputFormat unset BUT has default "pdf" → value token, not placeholder.
    expect((byParam.outputFormat as { placeholder: boolean }).placeholder).toBe(false)
    expect((byParam.outputFormat as { text: string }).text).toBe("pdf")
  })
  it("a no-slot type (start) yields only literal segments", () => {
    const model = renderModelFor("start", {})
    expect(model).toEqual([{ kind: "literal", text: "Start" }])
  })
  it("an unknown type has no template (null → caller falls back)", () => {
    expect(renderModelFor("__nope__", {})).toBeNull()
    expect(templateFor("__nope__")).toBeUndefined()
  })
})

describe("workflow-node-templates — propType + isEditableToken (P2a/P2b gate)", () => {
  const mk = (type: string) =>
    resolveSlot("p", { p: "x" }, { type, default: "" } as never)

  it("resolveSlot carries the param's propType", () => {
    expect(mk("string").propType).toBe("string")
    expect(mk("enum").propType).toBe("enum")
    expect(mk("number").propType).toBe("number")
    expect(mk("componentReference").propType).toBe("componentReference")
  })

  it("isEditableToken: simple types (string/enum/number/boolean) → editable", () => {
    for (const t of ["string", "enum", "number", "boolean"]) {
      expect(isEditableToken(mk(t))).toBe(true)
    }
  })

  it("isEditableToken: complex types (object/array/componentReference) → editable (P2b)", () => {
    for (const t of ["object", "array", "componentReference"]) {
      expect(isEditableToken(mk(t))).toBe(true)
    }
  })

  it("isEditableToken: tokenReference (vestigial accentToken) → NOT editable", () => {
    expect(isEditableToken(mk("tokenReference"))).toBe(false)
  })

  it("isEditableToken: a token with no propType → NOT editable", () => {
    expect(isEditableToken({ kind: "token", param: "p", text: "x", placeholder: false })).toBe(
      false,
    )
  })

  it("EDITABLE_TOKEN_TYPES = the 4 simple + 3 complex; BESPOKE = the 2 invoke_ types", () => {
    expect([...EDITABLE_TOKEN_TYPES].sort()).toEqual([
      "array",
      "boolean",
      "componentReference",
      "enum",
      "number",
      "object",
      "string",
    ])
    expect([...BESPOKE_NAMESPACE_TYPES].sort()).toEqual([
      "invoke_generation_focus",
      "invoke_review_focus",
    ])
  })
})

describe("workflow-node-templates — isTokenInlineEditable (P2b namespace gate)", () => {
  const mk = (type: string) =>
    resolveSlot("p", { p: "x" }, { type, default: "" } as never)

  it("non-bespoke type + editable propType → inline-editable (simple AND complex)", () => {
    expect(isTokenInlineEditable("action", mk("string"))).toBe(true)
    expect(isTokenInlineEditable("decision", mk("array"))).toBe(true)
    // generation-focus-invocation (RegistryDrivenConfig) IS in scope —
    // its focusTemplateName round-trips cleanly.
    expect(
      isTokenInlineEditable("generation-focus-invocation", mk("componentReference")),
    ).toBe(true)
  })

  it("bespoke-namespace types → NOT editable for ANY propType (phantom-key guard)", () => {
    for (const nodeType of BESPOKE_NAMESPACE_TYPES) {
      expect(isTokenInlineEditable(nodeType, mk("componentReference"))).toBe(false)
      expect(isTokenInlineEditable(nodeType, mk("string"))).toBe(false)
      expect(isTokenInlineEditable(nodeType, mk("object"))).toBe(false)
    }
  })

  it("non-editable propType stays non-editable even on a non-bespoke type", () => {
    expect(isTokenInlineEditable("action", mk("tokenReference"))).toBe(false)
  })
})

describe("workflow-node-templates — semanticParams", () => {
  it("excludes ONLY the retired-visual props; not-yet-built indicators STAY semantic", () => {
    // generation-focus-invocation carries all 5 inspector-hidden params +
    // real config. The sentence engine excludes only the 3 RETIRED props;
    // the 2 not-yet-built indicators remain semantic (inspector-hidden ≠
    // engine-retired — locks the distinction so the drift can't recur).
    const sem = semanticParams("generation-focus-invocation")
    expect(sem).toContain("focusTemplateName")
    for (const v of VESTIGIAL_VISUAL_PARAMS) expect(sem).not.toContain(v)
    // The indicator enums are NOT engine-excluded — present in semanticParams.
    for (const v of NOT_YET_IMPLEMENTED_PARAMS) expect(sem).toContain(v)
  })

  it("VESTIGIAL_VISUAL_PARAMS = the 3 A3-retired props; NOT_YET_IMPLEMENTED = the 2 indicators", () => {
    expect([...VESTIGIAL_VISUAL_PARAMS].sort()).toEqual(
      ["accentToken", "labelPosition", "nodeShape"],
    )
    expect([...NOT_YET_IMPLEMENTED_PARAMS].sort()).toEqual(
      ["failureIndicatorStyle", "successIndicatorStyle"],
    )
  })
})

describe("workflow-node-templates — unslottedParams (P3a expand-panel source)", () => {
  it("returns [] for the 6 fully-slotted types (nothing to surface in the panel)", () => {
    for (const t of [
      "start",
      "end",
      "send_document",
      "generate_document",
      "cross_tenant_acknowledgment",
      "branch",
    ]) {
      expect(unslottedParams(t)).toEqual([])
    }
  })

  it("returns the un-slotted semantic params (excludes the template-slotted ones)", () => {
    // ai_prompt slots promptKey + model; temperature + maxTokens are un-slotted.
    expect(unslottedParams("ai_prompt").sort()).toEqual(["maxTokens", "temperature"])
    // schedule slots scheduleMode; cronExpression + delaySeconds un-slotted.
    expect(unslottedParams("schedule").sort()).toEqual(["cronExpression", "delaySeconds"])
  })

  it("excludes INSPECTOR_HIDDEN_PARAMS (retired-visual + not-yet-built indicators)", () => {
    const un = unslottedParams("generation-focus-invocation")
    // The un-slotted semantic params ARE surfaced…
    expect(un.sort()).toEqual(["inputBinding", "reviewMode", "timeoutSeconds"])
    // …and NONE of the inspector-hidden params leak into the panel.
    for (const h of INSPECTOR_HIDDEN_PARAMS) expect(un).not.toContain(h)
  })

  it("TWO-TIER: the panel set is DISJOINT from the sentence-slotted set (no duplication)", () => {
    for (const type of Object.keys(NODE_LABEL_TEMPLATES)) {
      const slots = new Set(
        [...NODE_LABEL_TEMPLATES[type].matchAll(/\{(\w+)\}/g)].map((m) => m[1]),
      )
      for (const p of unslottedParams(type)) {
        expect(slots.has(p)).toBe(false)
      }
    }
  })
})

// ── THE GUARD: every template {slot} references a real semantic param ──
// Catches template typos + registry drift loudly.
describe("workflow-node-templates — 32-template guard", () => {
  it("there is a template for every registered workflow-node type (and vice versa)", () => {
    const registered = getByType("workflow-node").map((e) => e.metadata.name).sort()
    const templated = Object.keys(NODE_LABEL_TEMPLATES).sort()
    expect(templated).toEqual(registered)
  })

  it("every template slot references a SEMANTIC param of its type", () => {
    const bad: string[] = []
    for (const [type, tmpl] of Object.entries(NODE_LABEL_TEMPLATES)) {
      const slots = [...tmpl.matchAll(/\{(\w+)\}/g)].map((m) => m[1])
      const sem = new Set(semanticParams(type))
      for (const s of slots) {
        if (!sem.has(s)) bad.push(`${type}: {${s}}`)
      }
    }
    expect(bad).toEqual([])
  })
})

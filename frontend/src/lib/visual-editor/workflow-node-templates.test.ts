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

describe("workflow-node-templates — propType + isEditableToken (P2a gate)", () => {
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

  it("isEditableToken: complex types (object/array/componentReference) → NOT editable", () => {
    for (const t of ["object", "array", "componentReference"]) {
      expect(isEditableToken(mk(t))).toBe(false)
    }
  })

  it("isEditableToken: a token with no propType → NOT editable", () => {
    expect(isEditableToken({ kind: "token", param: "p", text: "x", placeholder: false })).toBe(
      false,
    )
  })
})

describe("workflow-node-templates — semanticParams", () => {
  it("excludes the vestigial visual params", () => {
    const sem = semanticParams("generate_document")
    expect(sem).toContain("templateKey")
    for (const v of VESTIGIAL_VISUAL_PARAMS) expect(sem).not.toContain(v)
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

/**
 * "set my shortcut to control" — the bar phrase, James's ruling of 2026-10-28.
 *
 * ⚠️ THE REFUSALS ARE THE POINT OF THIS FILE. The bar's whole job is orders, so a
 * matcher that fired on anything containing "control" would eat a product name and a
 * note. Half the tests below are things that must NOT match, and they are the half
 * that would be missing if this were written to the happy path.
 */
import { describe, expect, it } from "vitest"

import { shortcutRequest } from "./shortcut-request"

describe("what it recognises", () => {
  it("the sentence the ruling names", () => {
    expect(shortcutRequest("set my shortcut to control")).toBe("control")
  })

  it("every modifier, and its common short names", () => {
    expect(shortcutRequest("set my shortcut to option")).toBe("option")
    expect(shortcutRequest("set my shortcut to opt")).toBe("option")
    expect(shortcutRequest("set my shortcut to alt")).toBe("option")
    expect(shortcutRequest("set my shortcut to ctrl")).toBe("control")
    expect(shortcutRequest("set my shortcut to command")).toBe("command")
    expect(shortcutRequest("set my shortcut to cmd")).toBe("command")
    expect(shortcutRequest("set my shortcut to meta")).toBe("command")
  })

  it("case, trailing punctuation and extra spaces", () => {
    expect(shortcutRequest("  Set My Shortcut To Control.  ")).toBe("control")
    expect(shortcutRequest("set  my   shortcut  to   control")).toBe("control")
  })

  it("the ways people actually say it", () => {
    expect(shortcutRequest("set my shortcut to the control key")).toBe("control")
    expect(shortcutRequest("set shortcut to command")).toBe("command")
    expect(shortcutRequest("my shortcut is control")).toBe("control")
    expect(shortcutRequest("set my pick shortcut to option")).toBe("option")
    expect(shortcutRequest("use control for pills")).toBe("control")
    expect(shortcutRequest("use command to pick")).toBe("command")
  })
})

describe("what it REFUSES, which is the half that protects the bar", () => {
  it("a bare 'use <name>' — because 'use monticello' is a thing people type", () => {
    // ⚠️ `use` IS THE ONE LOOSE PREFIX AND IT IS FENCED to the pill-naming forms.
    expect(shortcutRequest("use control")).toBeNull()
    expect(shortcutRequest("use option")).toBeNull()
    expect(shortcutRequest("use monticello")).toBeNull()
  })

  it("a question about the shortcut, rather than an instruction", () => {
    // ⚠️ A LOOSE MATCH ON "shortcut" WOULD ANSWER A QUESTION BY CHANGING THE SETTING.
    expect(shortcutRequest("what is my shortcut")).toBeNull()
    expect(shortcutRequest("what shortcut picks pills")).toBeNull()
    expect(shortcutRequest("which shortcut is control")).toBeNull()
  })

  it("a modifier name that is not one of the three", () => {
    expect(shortcutRequest("set my shortcut to hyper")).toBeNull()
    expect(shortcutRequest("set my shortcut to f13")).toBeNull()
    expect(shortcutRequest("set my shortcut to")).toBeNull()
  })

  it("an order, a product and a note that merely contain the words", () => {
    // ⚠️ THE REAL RISK. These all have to reach the extractor untouched.
    expect(shortcutRequest("order for hopkins control series vault")).toBeNull()
    expect(shortcutRequest("continental 34 for riverside")).toBeNull()
    expect(shortcutRequest("set the service to graveside")).toBeNull()
    expect(shortcutRequest("command the tent for thursday")).toBeNull()
  })

  it("empty and whitespace", () => {
    expect(shortcutRequest("")).toBeNull()
    expect(shortcutRequest("   ")).toBeNull()
  })

  it("a phrase that only nearly matches", () => {
    // ⚠️ REFUSED RATHER THAN GUESSED, BY CHOICE. The office retypes a refused phrase;
    // a guess silently changes a keyboard under them.
    expect(shortcutRequest("set my shortcuts to control")).toBeNull()
    expect(shortcutRequest("set my shortcut control")).toBeNull()
    expect(shortcutRequest("shortcut to control")).toBeNull()
  })
})

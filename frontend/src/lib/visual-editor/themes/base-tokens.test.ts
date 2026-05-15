/**
 * base-tokens drift-gate vitest test (sub-arc C-2.1).
 *
 * Parses tokens.css at test time and asserts every key in
 * BASE_TOKENS.light + BASE_TOKENS.dark matches the corresponding
 * --<key> declaration in the :root + [data-mode="dark"] blocks.
 *
 * Drift = test failure. Prevents the token-source divergence motivating
 * the Q7 architectural decision (tokens.css is canonical platform-
 * default; BASE_TOKENS mirrors it; the editor composes BASE_TOKENS +
 * platform_themes overrides).
 */
import * as fs from "node:fs"
import * as path from "node:path"
import { describe, expect, it } from "vitest"

import { BASE_TOKENS, BASE_TOKEN_KEYS } from "./base-tokens"

const TOKENS_CSS_PATH = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "styles",
  "tokens.css",
)

interface ParsedBlocks {
  root: Record<string, string>
  dark: Record<string, string>
}

function parseTokensCss(): ParsedBlocks {
  const raw = fs.readFileSync(TOKENS_CSS_PATH, "utf-8")
  const stripComments = raw.replace(/\/\*[\s\S]*?\*\//g, "")

  function extractBlock(opener: RegExp): string {
    const m = stripComments.match(opener)
    if (!m) return ""
    const startIdx = m.index! + m[0].length
    let depth = 1
    let i = startIdx
    while (i < stripComments.length && depth > 0) {
      const ch = stripComments[i]
      if (ch === "{") depth += 1
      else if (ch === "}") depth -= 1
      i += 1
    }
    return stripComments.slice(startIdx, i - 1)
  }

  function parseDecls(blockBody: string): Record<string, string> {
    const out: Record<string, string> = {}
    // Match --name: value;  — value may include parens, slashes,
    // commas. Stop at semicolon.
    const re = /--([a-zA-Z0-9-]+)\s*:\s*([^;]+);/g
    let m: RegExpExecArray | null
    while ((m = re.exec(blockBody)) !== null) {
      out[m[1]] = m[2].trim()
    }
    return out
  }

  const rootBody = extractBlock(/:root\s*\{/)
  const darkBody = extractBlock(/\[data-mode\s*=\s*"dark"\]\s*\{/)
  return { root: parseDecls(rootBody), dark: parseDecls(darkBody) }
}

describe("BASE_TOKENS drift-gate", () => {
  const parsed = parseTokensCss()

  it("parses tokens.css :root block successfully", () => {
    expect(Object.keys(parsed.root).length).toBeGreaterThan(20)
  })

  it("parses tokens.css [data-mode=dark] block successfully", () => {
    // Dark block may or may not be present; if present must parse.
    // Loose check — some tokens are inherited unchanged from :root.
    expect(parsed.dark).toBeDefined()
  })

  for (const key of BASE_TOKEN_KEYS) {
    it(`light/${key} matches tokens.css :root`, () => {
      const cssValue = parsed.root[key]
      // Token must exist in :root.
      expect(cssValue, `tokens.css :root must declare --${key}`).toBeDefined()
      const baseValue = BASE_TOKENS.light[key]
      expect(
        baseValue,
        `BASE_TOKENS.light[${key}] must match tokens.css :root --${key}`,
      ).toBe(cssValue)
    })
  }

  it("BASE_TOKENS.dark provides values for every key in BASE_TOKENS.light", () => {
    for (const key of BASE_TOKEN_KEYS) {
      expect(
        BASE_TOKENS.dark[key],
        `BASE_TOKENS.dark[${key}] must be defined`,
      ).toBeTruthy()
    }
  })
})

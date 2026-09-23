/**
 * GUARD — no e2e route handler for the production host may fail OPEN.
 *
 * ⚠️ WHAT THIS PREVENTS. Every browser-based e2e spec rewrites
 * `https://api.getbridgeable.com/**` to the staging backend, because the staging
 * frontend is built against the PRODUCTION api (see tests/e2e/PROD_INTERCEPT.md).
 * If the rewrite throws — which is what happens when staging is unreachable —
 * `route.continue()` forwards the ORIGINAL request, original host, method and
 * body, to production. `route.abort()` kills it instead.
 *
 * Measured 2026-09-23: all 42 sites routing the production host ended in
 * `catch { route.continue() }`; zero used abort. Observed against a local sink
 * standing in for production, a POST with a body arrived.
 *
 * ⚠️ AST, NOT A TEXT SEARCH, FOR TWO REASONS.
 *   1. A literal search for "route.continue()" inside a catch would match THIS
 *      file, which has to name the thing it forbids.
 *   2. The defect has several spellings — `await route.continue()`,
 *      `return route.continue()`, `catch (e) { ... }`, a renamed binding — and a
 *      regex tuned to one spelling silently passes the others. That is the
 *      constructed-name failure in CLAUDE.md §11.
 *
 * It reads source only: no browser, no network, no staging. It runs inside the
 * existing `npm test` gate.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import ts from "typescript";
import { describe, expect, it } from "vitest";

const E2E_ROOT = join(__dirname, "..", "..", "tests", "e2e");
const PROD_HOSTS = ["api.getbridgeable.com", "app.getbridgeable.com"];

function tsFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...tsFiles(p));
    else if (name.endsWith(".ts")) out.push(p);
  }
  return out;
}

/** `true` when the expression is a `.route(...)` call whose first argument
 *  mentions a production host — as a literal or through a template that
 *  interpolates a PROD_API-shaped identifier. */
function routesProduction(node: ts.CallExpression, src: ts.SourceFile): boolean {
  const callee = node.expression;
  if (!ts.isPropertyAccessExpression(callee) || callee.name.text !== "route") {
    return false;
  }
  const arg = node.arguments[0];
  if (!arg) return false;
  const text = arg.getText(src);
  return (
    PROD_HOSTS.some((h) => text.includes(h)) || /\bPROD_API\b/.test(text)
  );
}

/** Every `route.continue()` reachable inside a catch clause under `node`. */
function continuesInsideCatch(node: ts.Node): number {
  let found = 0;
  const visitCatch = (n: ts.Node) => {
    if (ts.isCallExpression(n)) {
      const c = n.expression;
      // Any `<something>.continue()` — the binding may be renamed, so match the
      // method rather than the receiver's spelling.
      if (ts.isPropertyAccessExpression(c) && c.name.text === "continue") found++;
    }
    ts.forEachChild(n, visitCatch);
  };
  const walk = (n: ts.Node) => {
    if (ts.isCatchClause(n)) visitCatch(n.block);
    ts.forEachChild(n, walk);
  };
  walk(node);
  return found;
}

describe("e2e production intercepts fail closed", () => {
  const files = tsFiles(E2E_ROOT);

  it("finds e2e sources to scan — the instrument can see", () => {
    // ⚠️ Positive control. A scan that matches nothing satisfies "zero
    // violations" trivially; this proves the directory was read and that at
    // least one file actually routes the production host.
    expect(files.length).toBeGreaterThan(20);
    const routing = files.filter((f) => {
      const src = ts.createSourceFile(f, readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true);
      let hit = false;
      const walk = (n: ts.Node) => {
        if (ts.isCallExpression(n) && routesProduction(n, src)) hit = true;
        ts.forEachChild(n, walk);
      };
      walk(src);
      return hit;
    });
    expect(routing.length).toBeGreaterThan(20);
  });

  it("no production-host route handler continues on error", () => {
    const offenders: string[] = [];
    for (const f of files) {
      const text = readFileSync(f, "utf8");
      const src = ts.createSourceFile(f, text, ts.ScriptTarget.Latest, true);
      const walk = (n: ts.Node) => {
        if (ts.isCallExpression(n) && routesProduction(n, src)) {
          const handler = n.arguments[1];
          if (handler && continuesInsideCatch(handler) > 0) {
            const { line } = src.getLineAndCharacterOfPosition(n.getStart(src));
            offenders.push(`${relative(E2E_ROOT, f)}:${line + 1}`);
          }
        }
        ts.forEachChild(n, walk);
      };
      walk(src);
    }
    expect(
      offenders,
      "These route the production host and fall through to it when the rewrite " +
        "fails — which is exactly when staging is down. Use route.abort() in the " +
        "catch. See tests/e2e/PROD_INTERCEPT.md.\n  " + offenders.join("\n  "),
    ).toEqual([]);
  });
});

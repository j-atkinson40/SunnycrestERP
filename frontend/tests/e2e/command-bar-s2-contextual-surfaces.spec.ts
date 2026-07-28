/**
 * Command Bar S-2 (§4.3) — floating contextual surfaces E2E.
 *
 * THE DEFERRED LIVE-OVERLAY WITNESS. The local (dev) witness could
 * prove every layer in isolation — the /quote-preview endpoint against
 * real data, both-mode chrome, the host dispatch, the map suppression —
 * but NOT the real chain end-to-end, because dev has no ANTHROPIC_API_KEY
 * (so extraction yields empty fields and the surfaces stay suppressed).
 *
 * Staging HAS the key, a real viewport, and a real browser. This spec
 * drives the actual chain a user experiences, no injection tricks:
 *
 *   Cmd+K → Compose workflow → real overlay → type a real quote
 *     → extraction settles (Haiku) → onExtraction fires
 *     → CONTEXTUAL_SURFACES keys on entry_intent="quote"
 *     → CommandBarSurfaceHost dispatches via getWidgetRenderer
 *     → the widgets self-fetch and render BESIDE the palette.
 *
 * Surfaces are `lg`-gated (hidden below 1024px), so the witness runs
 * on the desktop project only (skipped on mobile).
 *
 * Pattern mirrors command-bar-phase-1.spec.ts: staging backend via the
 * prod→staging fetch redirect, testco tenant, admin credentials.
 */
import { test, expect, Page } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL || "https://sunnycresterp-staging.up.railway.app";

const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

// A phrase the extractor should resolve to a testco-seeded vault
// product + quantity. Monticello is a seeded manufacturing product.
const QUOTE_TEXT = "quote 3 Monticello for Hopkins";
const PRODUCT_REF = "Monticello";
const QTY = 3;

async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_BACKEND);
    try {
      const response = await route.fetch({ url });
      await route.fulfill({ response });
    } catch {
      await route.continue();
    }
  });
  await page.goto("/", { waitUntil: "commit" });
  await page.evaluate((slug) => {
    localStorage.setItem("company_slug", slug);
  }, TENANT_SLUG);
}

async function login(page: Page) {
  await setupPage(page);
  await page.goto("/login");
  // "load", NOT "networkidle" — the app holds a persistent RingCentral
  // SSE open, so networkidle never settles (the tree-wide fix from the
  // runtime-editor arc, 2026-07-23). Deterministic element waits below.
  await page.waitForLoadState("load");
  const identifier = page.locator("#identifier");
  await identifier.waitFor({ state: "visible", timeout: 10_000 });
  await identifier.fill(CREDS.email);
  await page.waitForTimeout(300);
  const password = page.locator("#password");
  await password.waitFor({ state: "visible", timeout: 5_000 });
  await password.fill(CREDS.password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
}

async function authHeaders(page: Page) {
  const token = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  );
  const slug = await page.evaluate(() =>
    localStorage.getItem("company_slug"),
  );
  return {
    Authorization: `Bearer ${token}`,
    "X-Company-Slug": slug ?? TENANT_SLUG,
    "Content-Type": "application/json",
  };
}

async function openCommandBar(page: Page) {
  const input = page
    .locator(
      'input[placeholder*="search" i], input[placeholder*="ask" i], input[aria-label*="command" i]',
    )
    .first();
  // Deterministic open (hardened after the 5s flake): press the shortcut,
  // wait on the input MOUNTING. Meta is Cmd on mac, Super on the Linux CI
  // runner (where Control+k is the binding) — try both, re-pressing only
  // when the bar did not open (so we never toggle an already-open bar).
  for (const combo of ["Meta+k", "Control+k", "Meta+k"]) {
    await page.keyboard.press(combo);
    try {
      await input.waitFor({ state: "visible", timeout: 6_000 });
      return input;
    } catch {
      // bar didn't open on this combo — try the next
    }
  }
  // Final wait so a real failure reads as "bar never opened".
  await input.waitFor({ state: "visible", timeout: 6_000 });
  return input;
}

test.describe("@tenant:sunnycrest Command Bar S-2 contextual surfaces", () => {
  // Surfaces float beside the palette and are hidden below the `lg`
  // breakpoint — the witness is a desktop-viewport concern.
  test.skip(
    ({ viewport }) => (viewport?.width ?? 0) < 1024,
    "contextual surfaces render at lg+ only",
  );

  test("live overlay → quote preview + price-list reference materialize beside the palette", async ({
    page,
  }) => {
    await login(page);
    // "load" not "networkidle" — the dashboard holds the SSE open.
    await page.goto("/dashboard", { waitUntil: "load" });

    // Cmd+K → surface + activate the Compose workflow (real click).
    const input = await openCommandBar(page);
    await input.fill("quote");
    const composeRow = page.getByText("Bridgeable Compose").first();
    await composeRow.waitFor({ state: "visible", timeout: 8_000 });
    await composeRow.click();

    // The NL overlay opens with its own textarea (wf_compose example
    // placeholder). Type a real quote — this fires the debounced Haiku
    // extraction, whose settle lifts onExtraction into the surfaces.
    const overlay = page.getByPlaceholder(
      /Continental for Hopkins|describe in your own words/i,
    );
    await overlay.waitFor({ state: "visible", timeout: 8_000 });
    await overlay.fill(QUOTE_TEXT);

    // JOB 1 — the integration proof. onExtraction → map (entry_intent
    // "quote") → host dispatch → widget self-fetch. Generous timeout:
    // the surface data rides the ~600ms debounce + the Haiku round-trip.
    const quotePreview = page.getByTestId("quote-preview-surface");
    const t0 = Date.now();
    await quotePreview.waitFor({ state: "visible", timeout: 20_000 });
    const msToSurface = Date.now() - t0;
    // Timing telemetry (Job 2) — surfaced in the run report.
    // eslint-disable-next-line no-console
    console.log(`[s2-timing] fill→quote-preview-visible: ${msToSurface}ms`);

    // The preview lives inside the Act host (beside the palette), not
    // the modal — confirm it's under the surface host.
    await expect(page.getByTestId("command-bar-surface-host")).toBeVisible();

    // Price-list reference appears once a product resolves (suppressed
    // until then by CONTEXTUAL_SURFACES.configFrom).
    const priceList = page.getByTestId("price-list-reference-surface");
    await priceList.waitFor({ state: "visible", timeout: 20_000 });

    // JOB 4 (money, tied to the ORDER resolver) — the caption shows a
    // real currency total, and it equals what /quote-preview computes
    // for the same lines (which uses get_effective_price, NOT the tiered
    // display). NOTE: on testco seed the order price and the published
    // standard price coincide, so the e2e can't distinguish them by
    // value — the order-vs-tiered DIVERGENCE is proven in the backend
    // unit test (test_quote_preview.py). Here we prove the rendered
    // surface reflects the order-resolver endpoint value.
    const endpoint = await page.request.post(
      `${STAGING_BACKEND}/api/v1/command-bar/quote-preview`,
      {
        headers: await authHeaders(page),
        data: {
          customer_name: "Hopkins Funeral Home",
          lines: [{ product_ref: PRODUCT_REF, quantity: QTY }],
        },
      },
    );
    expect(endpoint.status()).toBe(200);
    const body = await endpoint.json();
    expect(body.subtotal_formatted).toMatch(/^\$[\d,]+\.\d{2}$/);
    // The surface's visible chrome shows that same subtotal figure.
    await expect(quotePreview).toContainText(body.subtotal_formatted);

    // Witness screenshot (Job 1 deliverable).
    await page.screenshot({
      path: "tests/e2e/screenshots/s2-live-overlay-witness.png",
      fullPage: false,
    });
  });

  test("preview endpoint returns the order-resolver price with correct quantity math", async ({
    page,
  }) => {
    // Deterministic (no AI): proves the money-math on real staging data.
    // subtotal(qty=N) must equal N × subtotal(qty=1) — the line-total
    // multiply through money.line_total — and be a real currency figure.
    await login(page);
    const headers = await authHeaders(page);
    const url = `${STAGING_BACKEND}/api/v1/command-bar/quote-preview`;

    const one = await page.request.post(url, {
      headers,
      data: { lines: [{ product_ref: PRODUCT_REF, quantity: 1 }] },
    });
    expect(one.status()).toBe(200);
    const oneBody = await one.json();
    expect(oneBody.subtotal_formatted).toMatch(/^\$[\d,]+\.\d{2}$/);
    expect(oneBody.has_call_office).toBe(false);

    const three = await page.request.post(url, {
      headers,
      data: { lines: [{ product_ref: PRODUCT_REF, quantity: 3 }] },
    });
    const threeBody = await three.json();

    const toNum = (s: string) => Number(s.replace(/[$,]/g, ""));
    expect(toNum(threeBody.subtotal_formatted)).toBeCloseTo(
      toNum(oneBody.subtotal_formatted) * 3,
      2,
    );
  });
});

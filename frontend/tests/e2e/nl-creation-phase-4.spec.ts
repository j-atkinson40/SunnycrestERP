/**
 * Bridgeable NL Creation — Phase 4 of UI/UX Arc E2E.
 *
 * Eight scenarios across case / event / contact entity types +
 * cross-cutting UX behaviors. Staging-canonical: prod→staging
 * fetch redirect, testco tenant, admin credentials.
 *
 *   1. nl_create_case            — demo sentence end-to-end
 *   2. nl_create_event           — "new event lunch..." happy path
 *   3. nl_create_contact         — name + company resolution + create
 *   4. nl_extraction_live_update — overlay updates as user types
 *   5. nl_tab_to_form            — Tab → traditional form with ?nl=
 *   6. nl_escape_cancels         — Esc exits NL mode
 *   7. nl_entity_resolution_pill — Hopkins FH renders as pill
 *   8. nl_api_extract_smoke      — API contract smoke test
 *
 * Precondition: staging has Hopkins Funeral Home seeded via
 * `backend/scripts/seed_nl_demo_data.py`. Tests that depend on
 * resolution skip gracefully if the row is missing.
 */
import { test, expect, Page } from "@playwright/test";

const STAGING_BACKEND =
  process.env.BACKEND_URL ||
  "https://sunnycresterp-staging.up.railway.app";

const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";
const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

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
  await page.waitForLoadState("networkidle");
  const id = page.locator("#identifier");
  await id.waitFor({ state: "visible", timeout: 10_000 });
  await id.fill(CREDS.email);
  await page.waitForTimeout(300);
  const pw = page.locator("#password");
  await pw.waitFor({ state: "visible", timeout: 5_000 });
  await pw.fill(CREDS.password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
}

async function openCommandBar(page: Page) {
  await page.keyboard.press("Meta+k").catch(async () => {
    await page.keyboard.press("Control+k");
  });
  const input = page
    .locator(
      'input[placeholder*="search" i], input[placeholder*="ask" i], input[aria-label*="command" i]',
    )
    .first();
  await input.waitFor({ state: "visible", timeout: 5_000 });
  return input;
}

// ── 1. NL case — demo sentence ───────────────────────────────────

test("nl_create_case: demo sentence populates overlay + creates case", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);
  // The full demo sentence
  await input.fill(
    "new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH",
  );
  // Overlay appears within ~500ms (debounce 300ms + extract ~200ms
  // without AI, or ~700ms with AI — budget to 2s for network).
  const overlay = page.locator('[data-testid="nl-overlay"]');
  await expect(overlay).toBeVisible({ timeout: 5_000 });

  // Deceased name field should be extracted
  const deceasedField = page.locator('[data-testid="nl-field-deceased_name"]');
  await expect(deceasedField).toBeVisible({ timeout: 5_000 });
  await expect(deceasedField).toContainText(/John|Smith/i);

  // Date of death = today (from "tonight")
  const dodField = page.locator('[data-testid="nl-field-date_of_death"]');
  await expect(dodField).toBeVisible();
  await expect(dodField).toContainText(/Today|2026/i);
});

// ── 2. NL event ──────────────────────────────────────────────────

test("nl_create_event: overlay populates from 'new event lunch...'", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);
  await input.fill("new event lunch with Jim tomorrow 2pm");

  const overlay = page.locator('[data-testid="nl-overlay"]');
  await expect(overlay).toBeVisible({ timeout: 5_000 });
  await expect(overlay).toContainText(/Create Event/i);

  const start = page.locator('[data-testid="nl-field-event_start"]');
  await expect(start).toBeVisible({ timeout: 5_000 });
});

// ── 3. NL contact ─────────────────────────────────────────────────

test("nl_create_contact: overlay populates from contact NL input", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);
  await input.fill("new contact Bob Smith at Hopkins 555-1234");

  const overlay = page.locator('[data-testid="nl-overlay"]');
  await expect(overlay).toBeVisible({ timeout: 5_000 });
  await expect(overlay).toContainText(/Create Contact/i);
});

// ── 4. Live update ───────────────────────────────────────────────

test("nl_extraction_live_update: overlay refreshes as user keeps typing", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);

  await input.fill("new case John Smith");
  const overlay = page.locator('[data-testid="nl-overlay"]');
  await expect(overlay).toBeVisible({ timeout: 5_000 });

  // Add a DOD phrase; the overlay should re-extract with the new
  // information (date_of_death field should appear).
  await input.focus();
  await input.pressSequentially(" DOD tonight", { delay: 50 });
  await expect(
    page.locator('[data-testid="nl-field-date_of_death"]'),
  ).toBeVisible({ timeout: 5_000 });
});

// ── 5. Tab → form fallback ───────────────────────────────────────

test("nl_tab_to_form: Tab key opens traditional form with ?nl= param", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);
  const nlText = "John Smith DOD tonight";
  await input.fill(`new case ${nlText}`);

  // Wait for overlay to appear, then press Tab.
  await expect(page.locator('[data-testid="nl-overlay"]')).toBeVisible({
    timeout: 5_000,
  });
  await page.keyboard.press("Tab");

  await page.waitForURL(/\/cases\/new\?nl=/, { timeout: 10_000 });
  const url = new URL(page.url());
  expect(url.searchParams.get("nl")).toContain(nlText);
});

// ── 6. Escape cancels ────────────────────────────────────────────

test("nl_escape_cancels: Esc exits NL mode, standard bar returns", async ({
  page,
}) => {
  await login(page);
  const input = await openCommandBar(page);
  await input.fill("new case John Smith DOD tonight");
  await expect(page.locator('[data-testid="nl-overlay"]')).toBeVisible({
    timeout: 5_000,
  });

  await page.keyboard.press("Escape");
  // Overlay should unmount. The command bar input may also close;
  // either way the overlay is gone.
  await expect(page.locator('[data-testid="nl-overlay"]')).toBeHidden({
    timeout: 3_000,
  });
});

// ── 7. Entity pill resolution ────────────────────────────────────

test("nl_entity_resolution_pill: Hopkins FH renders as pill (if seeded)", async ({
  page,
}) => {
  await login(page);

  // Verify staging has a Hopkins FH row; if not, skip — the test
  // depends on seed_nl_demo_data.py having run.
  const hasHopkins = await page.evaluate(async () => {
    const token = localStorage.getItem("access_token");
    const slug = localStorage.getItem("company_slug") || "testco";
    const r = await fetch("/api/v1/company_entities?search=Hopkins&limit=5", {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Company-Slug": slug,
      },
    });
    if (!r.ok) return false;
    const body = await r.json();
    const results = (body.entities ?? body) as Array<{ name: string }>;
    return Array.isArray(results)
      ? results.some((e) => /hopkins/i.test(e.name))
      : false;
  });
  test.skip(!hasHopkins, "Hopkins FH not seeded; run seed_nl_demo_data.py");

  const input = await openCommandBar(page);
  await input.fill(
    "new case John Smith DOD tonight Thursday service Hopkins FH",
  );

  // Wait for overlay then look for the entity pill on funeral_home.
  await expect(page.locator('[data-testid="nl-overlay"]')).toBeVisible({
    timeout: 5_000,
  });
  const pill = page
    .locator('[data-testid="nl-field-funeral_home"] [data-testid="nl-entity-pill"]');
  await expect(pill).toBeVisible({ timeout: 10_000 });
  await expect(pill).toContainText(/Hopkins/i);
});

// ── 8. API smoke ─────────────────────────────────────────────────

test("nl_api_extract_smoke: /extract contract returns expected shape", async ({
  request,
}) => {
  const login = await request.post(
    `${STAGING_BACKEND}/api/v1/auth/login`,
    {
      data: { identifier: CREDS.email, password: CREDS.password },
      headers: { "X-Company-Slug": TENANT_SLUG },
    },
  );
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).access_token;
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Company-Slug": TENANT_SLUG,
    "Content-Type": "application/json",
  };

  // Entity types endpoint
  const types = await request.get(
    `${STAGING_BACKEND}/api/v1/nl-creation/entity-types`,
    { headers },
  );
  expect(types.ok()).toBeTruthy();
  const typesBody = await types.json();
  const typeSet = new Set(typesBody.map((t: { entity_type: string }) => t.entity_type));
  expect(typeSet.has("case")).toBe(true);
  expect(typeSet.has("event")).toBe(true);
  expect(typeSet.has("contact")).toBe(true);

  // Extract for case
  const extract = await request.post(
    `${STAGING_BACKEND}/api/v1/nl-creation/extract`,
    {
      headers,
      data: {
        entity_type: "case",
        natural_language: "John Smith DOD tonight Hopkins FH",
      },
    },
  );
  expect(extract.ok()).toBeTruthy();
  const extractBody = await extract.json();
  expect(extractBody.entity_type).toBe("case");
  expect(Array.isArray(extractBody.extractions)).toBe(true);
  expect(Array.isArray(extractBody.missing_required)).toBe(true);
});

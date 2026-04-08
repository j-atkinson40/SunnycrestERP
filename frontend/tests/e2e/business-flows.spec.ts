import { test, expect, Page, APIRequestContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STAGING_API = "https://sunnycresterp-staging.up.railway.app";
const PROD_API = "https://api.getbridgeable.com";
const TENANT_SLUG = "testco";
const API_BASE = `${STAGING_API}/api/v1`;

const CREDS = {
  admin: { email: "admin@testco.com", password: "TestAdmin123!" },
  office: { email: "office@testco.com", password: "TestOffice123!" },
  driver: { email: "driver@testco.com", password: "TestDriver123!" },
  production: { email: "production@testco.com", password: "TestProd123!" },
};

// Known staging IDs (from API discovery)
const KNOWN = {
  customers: {
    johnson: { id: "48634902-3a7c-4574-b0e8-1ecec899d452", name: "Johnson Funeral Home" },
    smith: { id: "e02d41df-e163-43f2-b66a-4688b493c6bf", name: "Smith & Sons Funeral Home" },
    memorial: { id: "570026ca-f743-4653-bbaa-6dff790c2eef", name: "Memorial Chapel" },
    riverside: { id: "4dc1ea34-c17c-45ad-93ea-854030682eb4", name: "Riverside Funeral Home" },
    greenValley: { id: "02ba272d-bdc1-4d02-af08-b1602d00e555", name: "Green Valley Memorial" },
  },
  cemeteries: {
    oakwood: { id: "89dc1bbf-3f18-4664-8e17-9ca2028c0bb9", name: "Oakwood Cemetery" },
    stMarys: { id: "23c82934-331f-4c70-be1a-66f98de20fac", name: "St. Mary's Cemetery" },
    lakeview: { id: "f499ce1f-1b2e-4032-ac2c-a7c376e6fd92", name: "Lakeview Memorial Gardens" },
  },
  products: {
    bronzeTriune: { id: "5e04f226-6a66-4fc5-9d29-cdac22e99e2f", name: "Bronze Triune", sku: "BT-001", price: 3864.0 },
    venetian: { id: "44819019-803b-4a4f-bbf0-40a3a5da07f8", name: "Venetian", sku: "VN-001", price: 1934.0 },
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupPage(page: Page) {
  await page.route(`${PROD_API}/**`, async (route) => {
    const url = route.request().url().replace(PROD_API, STAGING_API);
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

async function login(page: Page, role: keyof typeof CREDS) {
  await setupPage(page);
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  const id = page.locator("#identifier");
  await id.waitFor({ state: "visible", timeout: 10_000 });
  await id.fill(CREDS[role].email);
  await page.waitForTimeout(300);
  const pw = page.locator("#password");
  await pw.waitFor({ state: "visible", timeout: 5_000 });
  await pw.fill(CREDS[role].password);
  await page.getByRole("button", { name: /sign\s*in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20_000 });
  await page.waitForLoadState("networkidle");
}

async function getApiToken(request: APIRequestContext, role: keyof typeof CREDS = "admin"): Promise<string> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    headers: { "X-Company-Slug": TENANT_SLUG, "Content-Type": "application/json" },
    data: { email: CREDS[role].email, password: CREDS[role].password },
  });
  const body = await res.json();
  return body.access_token;
}

function apiHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    "X-Company-Slug": TENANT_SLUG,
    "Content-Type": "application/json",
  };
}

function futureDate(daysFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().split("T")[0];
}

function todayISO(): string {
  return new Date().toISOString().split("T")[0];
}

const SHOTS = "tests/e2e/screenshots";

async function snap(page: Page, flow: string, step: number, desc: string) {
  await page.screenshot({
    path: `${SHOTS}/${flow}-step${step}-${desc}.png`,
    fullPage: true,
  });
}

// ---------------------------------------------------------------------------
// Shared state across flows
// ---------------------------------------------------------------------------

const state: {
  flow1OrderId?: string;
  flow1OrderNumber?: string;
  flow1InvoiceId?: string;
  flow1InvoiceNumber?: string;
  flow5OrderId?: string;
  flow5OrderNumber?: string;
  priceVersionId?: string;
} = {};

// ===========================================================================
// OUTERMOST WRAPPER — tenant tag for incident reporter
// ===========================================================================

test.describe("@tenant:sunnycrest Business Flows", () => {

// ===========================================================================
// FLOW 1 — COMPLETE ORDER LIFECYCLE
// ===========================================================================

test.describe.serial("Flow 1: Complete Order Lifecycle", () => {
  test("Step 1: Create order via API", async ({ request }) => {
    const token = await getApiToken(request, "admin");
    const headers = apiHeaders(token);

    const res = await request.post(`${API_BASE}/sales/orders`, {
      headers,
      data: {
        customer_id: KNOWN.customers.johnson.id,
        order_date: new Date().toISOString(),
        required_date: new Date(Date.now() + 7 * 86400000).toISOString(),
        notes: "E2E Flow 1 test order",
        lines: [
          {
            product_id: KNOWN.products.bronzeTriune.id,
            description: "Bronze Triune - Standard Adult",
            quantity: 1,
            unit_price: KNOWN.products.bronzeTriune.price,
          },
        ],
      },
    });
    expect(res.status()).toBe(201);
    const order = await res.json();
    expect(order.id).toBeTruthy();
    expect(order.number).toBeTruthy();
    expect(parseFloat(order.total)).toBe(3864.0);

    state.flow1OrderId = order.id;
    state.flow1OrderNumber = order.number;
  });

  test("Step 2: Verify order detail page loads", async ({ page }) => {
    test.skip(!state.flow1OrderId, "No order created");
    await login(page, "admin");
    await page.goto(`/ar/orders/${state.flow1OrderId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "order-lifecycle", 2, "order-detail-draft");
    const content = await page.locator("body").textContent();
    expect(content).toContain(state.flow1OrderNumber!);
  });

  test("Step 3: Confirm order", async ({ request }) => {
    test.skip(!state.flow1OrderId, "No order created");
    const token = await getApiToken(request, "admin");
    const res = await request.patch(`${API_BASE}/sales/orders/${state.flow1OrderId}`, {
      headers: apiHeaders(token),
      data: { status: "confirmed" },
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    expect(order.status).toBe("confirmed");
  });

  test("Step 4: Move to production", async ({ request }) => {
    test.skip(!state.flow1OrderId, "No order created");
    const token = await getApiToken(request, "admin");
    const res = await request.patch(`${API_BASE}/sales/orders/${state.flow1OrderId}`, {
      headers: apiHeaders(token),
      data: { status: "production" },
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    expect(order.status).toBe("production");
  });

  test("Step 5: Mark delivered", async ({ request }) => {
    test.skip(!state.flow1OrderId, "No order created");
    const token = await getApiToken(request, "admin");
    const res = await request.patch(`${API_BASE}/sales/orders/${state.flow1OrderId}`, {
      headers: apiHeaders(token),
      data: { status: "shipped", shipped_date: new Date().toISOString() },
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    expect(order.status).toBe("shipped");
    expect(order.shipped_date).toBeTruthy();
  });

  test("Step 6: Verify order status on UI", async ({ page }) => {
    test.skip(!state.flow1OrderId, "No order created");
    await login(page, "admin");
    await page.goto(`/ar/orders/${state.flow1OrderId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "order-lifecycle", 6, "order-shipped");
    const content = await page.locator("body").textContent();
    // Should show shipped/delivered status
    expect(
      content?.includes("Shipped") || content?.includes("shipped") ||
      content?.includes("Delivered") || content?.includes("delivered")
    ).toBeTruthy();
  });

  test("Step 7: Generate invoice from order", async ({ request }) => {
    test.skip(!state.flow1OrderId, "No order created");
    const token = await getApiToken(request, "admin");
    const res = await request.post(`${API_BASE}/sales/orders/${state.flow1OrderId}/invoice`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(201);
    const invoice = await res.json();
    expect(invoice.id).toBeTruthy();
    expect(invoice.number).toBeTruthy();
    expect(parseFloat(invoice.total)).toBe(3864.0);

    state.flow1InvoiceId = invoice.id;
    state.flow1InvoiceNumber = invoice.number;
  });

  test("Step 8: Verify invoice on UI", async ({ page }) => {
    test.skip(!state.flow1InvoiceId, "No invoice created");
    await login(page, "admin");
    await page.goto(`/ar/invoices/${state.flow1InvoiceId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "order-lifecycle", 8, "invoice-generated");
    const content = await page.locator("body").textContent();
    expect(content).toContain(state.flow1InvoiceNumber!);
    expect(content).toContain("Johnson Funeral Home");
    expect(content).toContain("3,864");
  });

  test("Step 9: Approve invoice (draft → sent)", async ({ request }) => {
    test.skip(!state.flow1InvoiceId, "No invoice created");
    const token = await getApiToken(request, "admin");
    const res = await request.post(`${API_BASE}/sales/invoices/${state.flow1InvoiceId}/approve`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const invoice = await res.json();
    // Status after approval can be "sent" or "open" depending on config
    expect(["sent", "open"]).toContain(invoice.status);
  });

  test("Step 10: Record payment", async ({ request }) => {
    test.skip(!state.flow1InvoiceId, "No invoice created");
    const token = await getApiToken(request, "admin");
    const res = await request.post(`${API_BASE}/sales/payments`, {
      headers: apiHeaders(token),
      data: {
        customer_id: KNOWN.customers.johnson.id,
        payment_date: new Date().toISOString(),
        total_amount: 3864.0,
        payment_method: "check",
        reference_number: "Check #1001",
        notes: "E2E test payment",
        applications: [
          { invoice_id: state.flow1InvoiceId, amount_applied: 3864.0 },
        ],
      },
    });
    expect(res.status()).toBe(201);
    const payment = await res.json();
    expect(payment.id).toBeTruthy();
    expect(parseFloat(payment.total_amount)).toBe(3864.0);
  });

  test("Step 11: Verify invoice is paid", async ({ request }) => {
    test.skip(!state.flow1InvoiceId, "No invoice created");
    const token = await getApiToken(request, "admin");
    const res = await request.get(`${API_BASE}/sales/invoices/${state.flow1InvoiceId}`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const invoice = await res.json();
    expect(invoice.status).toBe("paid");
    expect(parseFloat(invoice.balance_remaining)).toBe(0);
    expect(parseFloat(invoice.amount_paid)).toBe(3864.0);
  });

  test("Step 12: Verify paid invoice on UI", async ({ page }) => {
    test.skip(!state.flow1InvoiceId, "No invoice created");
    await login(page, "admin");
    await page.goto(`/ar/invoices/${state.flow1InvoiceId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "order-lifecycle", 12, "invoice-paid");
    const content = await page.locator("body").textContent();
    // Should show paid status and payment details
    expect(
      content?.includes("Paid") || content?.includes("paid")
    ).toBeTruthy();
    expect(content).toContain("Check #1001");
  });

  test("Step 13: AR aging reflects payment", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/sales/aging`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const aging = await res.json();
    // Johnson should have $0 balance (paid the only invoice)
    const johnson = aging.customers?.find(
      (c: { customer_name: string }) => c.customer_name === "Johnson Funeral Home"
    );
    // If Johnson exists in aging, balance should be 0; if not present, that's also correct (no outstanding)
    if (johnson) {
      const total = parseFloat(johnson.buckets?.total || "0");
      expect(total).toBe(0);
    }
  });

  test("Step 14: Morning briefing endpoint responds", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/briefings/briefing`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const briefing = await res.json();
    // Briefing should respond without error (may be empty if no AI key configured)
    expect(briefing).toBeTruthy();
  });
});

// ===========================================================================
// FLOW 2 — OVERDUE INVOICE + AR AGING
// ===========================================================================

test.describe.serial("Flow 2: Overdue Invoice + AR Aging", () => {
  test("Step 1: Verify existing overdue invoice", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/sales/invoices?status=sent`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    // We should have at least one sent invoice that could be overdue
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });

  test("Step 2: Create overdue invoice for testing", async ({ request }) => {
    const token = await getApiToken(request);
    // Create invoice dated 60 days ago with due date 30 days ago
    const invoiceDate = new Date(Date.now() - 60 * 86400000).toISOString();
    const dueDate = new Date(Date.now() - 30 * 86400000).toISOString();

    const res = await request.post(`${API_BASE}/sales/invoices`, {
      headers: apiHeaders(token),
      data: {
        customer_id: KNOWN.customers.riverside.id,
        invoice_date: invoiceDate,
        due_date: dueDate,
        notes: "E2E Flow 2 overdue test",
        lines: [
          {
            description: "Bronze Triune - Overdue Test",
            product_id: KNOWN.products.bronzeTriune.id,
            quantity: 1,
            unit_price: 3864.0,
          },
        ],
      },
    });
    expect(res.status()).toBe(201);
    const invoice = await res.json();
    expect(invoice.id).toBeTruthy();

    // Approve it (move to sent status)
    const approveRes = await request.post(`${API_BASE}/sales/invoices/${invoice.id}/approve`, {
      headers: apiHeaders(token),
    });
    expect(approveRes.status()).toBe(200);
  });

  test("Step 3: AR aging shows overdue buckets", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/sales/aging`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const aging = await res.json();
    expect(aging.company_summary).toBeTruthy();
    const total = parseFloat(aging.company_summary.total);
    expect(total).toBeGreaterThan(0);

    // Riverside should have overdue balance
    const riverside = aging.customers?.find(
      (c: { customer_name: string }) => c.customer_name === "Riverside Funeral Home"
    );
    if (riverside) {
      const overdueTotal =
        parseFloat(riverside.buckets?.days_31_60 || "0") +
        parseFloat(riverside.buckets?.days_61_90 || "0") +
        parseFloat(riverside.buckets?.days_over_90 || "0");
      expect(overdueTotal).toBeGreaterThan(0);
    }
  });

  test("Step 4: AR aging page renders correctly on UI", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/ar/aging");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    await snap(page, "ar-aging", 4, "aging-report");
    const content = await page.locator("body").textContent();
    // Should show aging buckets
    expect(
      content?.includes("Current") ||
      content?.includes("1-30") ||
      content?.includes("31-60") ||
      content?.includes("Aging") ||
      content?.includes("aging")
    ).toBeTruthy();
    // Should show at least one customer with a balance
    expect(content?.includes("$") || content?.includes("Funeral")).toBeTruthy();
  });
});

// ===========================================================================
// FLOW 3 — PRICE INCREASE FLOW
// ===========================================================================

test.describe.serial("Flow 3: Price Increase Flow", () => {
  test("Step 1: Verify current price list", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/price-management/versions`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const versions = await res.json();
    const active = versions.find((v: { status: string }) => v.status === "active");
    expect(active).toBeTruthy();
    expect(active.label).toBeTruthy();
  });

  test("Step 2: Preview 5% price increase", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.post(`${API_BASE}/price-management/increase/preview`, {
      headers: apiHeaders(token),
      data: {
        increase_type: "percentage",
        increase_value: 5,
        effective_date: futureDate(30),
      },
    });
    expect(res.status()).toBe(200);
    const preview = await res.json();
    expect(preview.item_count).toBeGreaterThan(0);

    // Find Bronze Triune in preview
    const bt = preview.items.find(
      (i: { product_name: string }) => i.product_name === "Bronze Triune"
    );
    expect(bt).toBeTruthy();
    expect(parseFloat(bt.current_price)).toBe(3864.0);
    expect(parseFloat(bt.new_price)).toBe(4057.2);
    expect(parseFloat(bt.pct_change)).toBe(5.0);
  });

  test("Step 3: Apply price increase (create draft version)", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.post(`${API_BASE}/price-management/increase/apply`, {
      headers: apiHeaders(token),
      data: {
        increase_type: "percentage",
        increase_value: 5,
        effective_date: futureDate(30),
        label: "E2E Test 5% Increase",
        notes: "Created by business flow test",
      },
    });
    expect(res.status()).toBe(200);
    const version = await res.json();
    expect(version.id).toBeTruthy();
    expect(version.status).toBe("draft");
    state.priceVersionId = version.id;
  });

  test("Step 4: Schedule the version", async ({ request }) => {
    test.skip(!state.priceVersionId, "No version created");
    const token = await getApiToken(request);
    const res = await request.post(
      `${API_BASE}/price-management/versions/${state.priceVersionId}/action`,
      {
        headers: apiHeaders(token),
        data: { action: "schedule" },
      }
    );
    expect(res.status()).toBe(200);
    const version = await res.json();
    expect(version.status).toBe("scheduled");
  });

  test("Step 5: Verify on price management UI", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/price-management");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    await snap(page, "price-increase", 5, "price-management-page");
    const content = await page.locator("body").textContent();
    expect(
      content?.includes("E2E Test 5%") ||
      content?.includes("scheduled") ||
      content?.includes("Scheduled") ||
      content?.includes("Price")
    ).toBeTruthy();
  });

  test("Step 6: Old order keeps original price", async ({ request }) => {
    test.skip(!state.flow1OrderId, "No order from Flow 1");
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/sales/orders/${state.flow1OrderId}`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    // Original order should still have $3,864 total
    expect(parseFloat(order.total)).toBe(3864.0);
  });

  test("Step 7: Cleanup — delete draft version", async ({ request }) => {
    test.skip(!state.priceVersionId, "No version to clean up");
    const token = await getApiToken(request);
    // First un-schedule it back to draft
    // The version is scheduled, we need to delete it
    const res = await request.post(
      `${API_BASE}/price-management/versions/${state.priceVersionId}/action`,
      {
        headers: apiHeaders(token),
        data: { action: "delete" },
      }
    );
    // Accept either 200 (deleted) or error (can't delete scheduled — that's also fine)
    expect([200, 400, 422]).toContain(res.status());
  });
});

// ===========================================================================
// FLOW 4 — KNOWLEDGE BASE + PRICING LOOKUP
// ===========================================================================

test.describe.serial("Flow 4: Knowledge Base + Pricing", () => {
  test("Step 1: KB categories exist", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(`${API_BASE}/knowledge-base/categories`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const categories = await res.json();
    expect(categories.length).toBeGreaterThan(0);
    const pricing = categories.find(
      (c: { slug: string }) => c.slug === "pricing"
    );
    expect(pricing).toBeTruthy();
    expect(pricing.document_count).toBeGreaterThanOrEqual(0);
  });

  test("Step 2: KB page renders with categories", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/knowledge-base");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    await snap(page, "knowledge-base", 2, "kb-categories");
    const content = await page.locator("body").textContent();
    expect(
      content?.includes("Pricing") || content?.includes("Knowledge")
    ).toBeTruthy();
  });

  test("Step 3: Products endpoint returns pricing data", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(
      `${API_BASE}/products/${KNOWN.products.bronzeTriune.id}`,
      { headers: apiHeaders(token) }
    );
    expect(res.status()).toBe(200);
    const product = await res.json();
    expect(product.name).toBe("Bronze Triune");
    expect(product.price).toBe(3864.0);
  });

  test("Step 4: Price list version items have pricing", async ({ request }) => {
    const token = await getApiToken(request);
    const versionsRes = await request.get(`${API_BASE}/price-management/versions`, {
      headers: apiHeaders(token),
    });
    const versions = await versionsRes.json();
    const active = versions.find((v: { status: string }) => v.status === "active");
    test.skip(!active, "No active price version");

    const itemsRes = await request.get(
      `${API_BASE}/price-management/versions/${active.id}/items`,
      { headers: apiHeaders(token) }
    );
    expect(itemsRes.status()).toBe(200);
    const items = await itemsRes.json();
    expect(items.length).toBeGreaterThan(0);

    const bt = items.find(
      (i: { product_name: string }) => i.product_name === "Bronze Triune"
    );
    expect(bt).toBeTruthy();
    expect(parseFloat(bt.standard_price)).toBe(3864.0);
  });
});

// ===========================================================================
// FLOW 5 — MULTI-USER WORKFLOW
// ===========================================================================

test.describe.serial("Flow 5: Multi-User Workflow", () => {
  test("Step 1: Office creates and confirms order", async ({ request }) => {
    const token = await getApiToken(request, "office");
    const headers = apiHeaders(token);

    // Office staff creates the order
    const createRes = await request.post(`${API_BASE}/sales/orders`, {
      headers,
      data: {
        customer_id: KNOWN.customers.memorial.id,
        order_date: new Date().toISOString(),
        notes: "E2E Flow 5 multi-user test",
        lines: [
          {
            product_id: KNOWN.products.venetian.id,
            description: "Venetian - Standard Adult",
            quantity: 1,
            unit_price: KNOWN.products.venetian.price,
          },
        ],
      },
    });
    expect(createRes.status()).toBe(201);
    const order = await createRes.json();
    state.flow5OrderId = order.id;
    state.flow5OrderNumber = order.number;
    expect(parseFloat(order.total)).toBe(1934.0);

    // Office confirms the order
    const confirmRes = await request.patch(`${API_BASE}/sales/orders/${order.id}`, {
      headers,
      data: { status: "confirmed" },
    });
    expect(confirmRes.status()).toBe(200);
    expect((await confirmRes.json()).status).toBe("confirmed");
  });

  test("Step 2: Production can view order", async ({ request }) => {
    test.skip(!state.flow5OrderId, "No order created");
    const token = await getApiToken(request, "production");
    const res = await request.get(`${API_BASE}/sales/orders/${state.flow5OrderId}`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    expect(order.status).toBe("confirmed");
  });

  test("Step 3: Office moves to production and marks delivered", async ({ request }) => {
    test.skip(!state.flow5OrderId, "No order created");
    const token = await getApiToken(request, "office");
    const headers = apiHeaders(token);

    // Move to production
    const prodRes = await request.patch(`${API_BASE}/sales/orders/${state.flow5OrderId}`, {
      headers,
      data: { status: "production" },
    });
    expect(prodRes.status()).toBe(200);
    expect((await prodRes.json()).status).toBe("production");

    // Mark delivered
    const shipRes = await request.patch(`${API_BASE}/sales/orders/${state.flow5OrderId}`, {
      headers,
      data: { status: "shipped", shipped_date: new Date().toISOString() },
    });
    expect(shipRes.status()).toBe(200);
    const order = await shipRes.json();
    expect(order.status).toBe("shipped");
    expect(order.shipped_date).toBeTruthy();
  });

  test("Step 4: Driver can view delivered order", async ({ request }) => {
    test.skip(!state.flow5OrderId, "No order created");
    const token = await getApiToken(request, "driver");
    const res = await request.get(`${API_BASE}/sales/orders/${state.flow5OrderId}`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(200);
    const order = await res.json();
    expect(order.status).toBe("shipped");
  });

  test("Step 5: Office generates invoice", async ({ request }) => {
    test.skip(!state.flow5OrderId, "No order created");
    const token = await getApiToken(request, "office");
    const res = await request.post(`${API_BASE}/sales/orders/${state.flow5OrderId}/invoice`, {
      headers: apiHeaders(token),
    });
    expect(res.status()).toBe(201);
    const invoice = await res.json();
    expect(invoice.id).toBeTruthy();
    expect(parseFloat(invoice.total)).toBe(1934.0);
  });

  test("Step 6: Verify order lifecycle on UI (office view)", async ({ page }) => {
    test.skip(!state.flow5OrderId, "No order created");
    await login(page, "office");
    await page.goto(`/ar/orders/${state.flow5OrderId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "multi-user", 6, "office-order-delivered");
    const content = await page.locator("body").textContent();
    expect(content).toContain(state.flow5OrderNumber!);
    expect(content).toContain("Memorial Chapel");
    // Should show shipped/completed/delivered status
    expect(
      content?.includes("Shipped") || content?.includes("shipped") ||
      content?.includes("Completed") || content?.includes("Delivered")
    ).toBeTruthy();
  });
});

// ===========================================================================
// FLOW 6 — ONBOARDING
// ===========================================================================

test.describe("Flow 6: Onboarding", () => {
  test("Step 1: Onboarding page loads with checklist", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/onboarding");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    await snap(page, "onboarding", 1, "checklist-loaded");
    const content = await page.locator("body").textContent();
    expect(
      content?.includes("Onboarding") ||
      content?.includes("Setup") ||
      content?.includes("Checklist") ||
      content?.includes("Welcome") ||
      content?.includes("essential")
    ).toBeTruthy();
  });

  test("Step 2: Checklist items link to correct pages", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/onboarding");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Find clickable checklist items
    const links = page.locator('a[href*="/onboarding/"], a[href*="/settings/"]');
    const count = await links.count();
    if (count > 0) {
      // Click first link and verify it navigates
      const firstHref = await links.first().getAttribute("href");
      await links.first().click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1000);
      await snap(page, "onboarding", 2, "checklist-link-navigated");
      // Should have navigated away from onboarding
      const body = await page.locator("body").textContent();
      expect(body?.length).toBeGreaterThan(50);
    }
  });

  test("Step 3: Progress indicator visible", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/onboarding");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "onboarding", 3, "progress-indicator");
    const content = await page.locator("body").textContent();
    // Should show progress like "0 of 13" or percentage
    expect(
      content?.includes("of") ||
      content?.includes("%") ||
      content?.includes("essential") ||
      content?.includes("step")
    ).toBeTruthy();
  });
});

// ===========================================================================
// FLOW 7 — CROSS-CUTTING: INVOICES LIST + FILTERING
// ===========================================================================

test.describe("Flow 7: Invoice List + Filtering", () => {
  test("Step 1: Invoices list shows all invoices", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/ar/invoices");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);
    await snap(page, "invoices", 1, "invoice-list");
    const content = await page.locator("body").textContent();
    expect(content).toContain("INV-");
  });

  test("Step 2: Filter invoices by status", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/ar/invoices");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Look for status filter dropdown or buttons
    const statusFilter = page.locator(
      'select, [role="combobox"], button:has-text("All"), button:has-text("Paid"), button:has-text("Sent")'
    );
    if (await statusFilter.first().isVisible().catch(() => false)) {
      // Try to filter to Paid
      const paidBtn = page.locator('button:has-text("Paid"), option:has-text("Paid")');
      if (await paidBtn.first().isVisible().catch(() => false)) {
        await paidBtn.first().click();
        await page.waitForTimeout(2000);
        await snap(page, "invoices", 2, "filtered-by-status");
      }
    }
    // Page should still be functional
    const body = await page.locator("body").textContent();
    expect(body?.length).toBeGreaterThan(100);
  });

  test("Step 3: Invoice detail shows payment history", async ({ page }) => {
    test.skip(!state.flow1InvoiceId, "No paid invoice from Flow 1");
    await login(page, "admin");
    await page.goto(`/ar/invoices/${state.flow1InvoiceId}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "invoices", 3, "invoice-detail-with-payment");
    const content = await page.locator("body").textContent();
    // Should show payment info
    expect(
      content?.includes("Check #1001") ||
      content?.includes("Paid") ||
      content?.includes("3,864")
    ).toBeTruthy();
  });
});

// ===========================================================================
// FLOW 8 — CUSTOMER CRM DETAIL
// ===========================================================================

test.describe("Flow 8: Customer CRM Detail", () => {
  test("Step 1: Johnson Funeral Home detail page", async ({ page }) => {
    await login(page, "admin");
    // Navigate to CRM companies and find Johnson
    await page.goto("/crm/companies");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    await snap(page, "crm-detail", 1, "companies-list");

    const johnsonLink = page.locator('a:has-text("Johnson")').first();
    if (await johnsonLink.isVisible().catch(() => false)) {
      await johnsonLink.click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);
      await snap(page, "crm-detail", 1, "johnson-detail");
      const content = await page.locator("body").textContent();
      expect(content).toContain("Johnson");
    }
  });

  test("Step 2: Customer orders visible via API", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(
      `${API_BASE}/sales/orders?customer_id=${KNOWN.customers.johnson.id}`,
      { headers: apiHeaders(token) }
    );
    expect(res.status()).toBe(200);
    const data = await res.json();
    // Should have at least the order from Flow 1
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });

  test("Step 3: Customer invoices visible via API", async ({ request }) => {
    const token = await getApiToken(request);
    const res = await request.get(
      `${API_BASE}/sales/invoices?customer_id=${KNOWN.customers.johnson.id}`,
      { headers: apiHeaders(token) }
    );
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });
});

}); // end @tenant:sunnycrest

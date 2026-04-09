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
};

const KNOWN = {
  customers: {
    johnson: { id: "48634902-3a7c-4574-b0e8-1ecec899d452", name: "Johnson Funeral Home" },
  },
  cemeteries: {
    oakwood: { id: "89dc1bbf-3f18-4664-8e17-9ca2028c0bb9", name: "Oakwood Cemetery" },
  },
  products: {
    gravelinerSS: { id: "039d765d-2e0f-4f52-a1fd-5637059a11a0", name: "Graveliner SS", sku: "GS-001", price: 880.0 },
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

function todayISO(): string {
  return new Date().toISOString().split("T")[0];
}

const SHOTS = "tests/e2e/screenshots/ssc";

async function snap(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

const state: {
  orderId?: string;
  orderNumber?: string;
  deliveryId?: string;
  certId?: string;
  certNumber?: string;
  order2Id?: string;
  order2Number?: string;
  delivery2Id?: string;
  cert2Id?: string;
} = {};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe.serial("Social Service Certificates", () => {

  test("1 — Create order with Graveliner SS product", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const orderRes = await request.post(`${API_BASE}/sales/orders`, {
      headers: h,
      data: {
        customer_id: KNOWN.customers.johnson.id,
        cemetery_id: KNOWN.cemeteries.oakwood.id,
        order_date: new Date().toISOString(),
        required_date: new Date().toISOString(),
        scheduled_date: todayISO(),
        deceased_name: "John A. Smith",
        notes: "SSC E2E test order",
        lines: [
          {
            product_id: KNOWN.products.gravelinerSS.id,
            description: "Graveliner SS",
            quantity: 1,
            unit_price: KNOWN.products.gravelinerSS.price,
          },
        ],
      },
    });
    expect(orderRes.ok()).toBeTruthy();
    const order = await orderRes.json();
    state.orderId = order.id;
    state.orderNumber = order.number;
    expect(state.orderId).toBeTruthy();
    expect(state.orderNumber).toBeTruthy();

    // PATCH to set deceased_name (create_sales_order doesn't copy it)
    const patchRes = await request.patch(`${API_BASE}/sales/orders/${state.orderId}`, {
      headers: h,
      data: { deceased_name: "John A. Smith" },
    });
    expect(patchRes.ok()).toBeTruthy();
  });

  test("2 — Confirm the order", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.patch(`${API_BASE}/sales/orders/${state.orderId}`, {
      headers: h,
      data: { status: "confirmed" },
    });
    expect(res.ok()).toBeTruthy();
    const updated = await res.json();
    expect(updated.status).toBe("confirmed");
  });

  test("3 — Create delivery, complete it → certificate auto-generated", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    // Manually create a delivery linked to the order
    const createRes = await request.post(`${API_BASE}/delivery/deliveries`, {
      headers: h,
      data: {
        delivery_type: "standard",
        order_id: state.orderId,
        customer_id: KNOWN.customers.johnson.id,
        requested_date: todayISO(),
        priority: "normal",
      },
    });
    expect(createRes.ok()).toBeTruthy();
    const delivery = await createRes.json();
    state.deliveryId = delivery.id;

    // Complete the delivery
    const completeRes = await request.post(`${API_BASE}/delivery/${state.deliveryId}/complete`, {
      headers: h,
      data: {},
    });
    expect(completeRes.ok()).toBeTruthy();

    // Verify certificate was auto-generated
    const certRes = await request.get(`${API_BASE}/social-service-certificates/pending`, { headers: h });
    expect(certRes.ok()).toBeTruthy();
    const pending = await certRes.json();
    const cert = pending.find((c: any) => c.certificate_number === `${state.orderNumber}-SSC`);
    expect(cert).toBeTruthy();
    state.certId = cert.id;
    state.certNumber = cert.certificate_number;
    expect(cert.status).toBe("pending_approval");
    expect(cert.deceased_name).toBe("John A. Smith");
    expect(cert.funeral_home_name).toContain("Johnson");
  });

  test("4 — Get certificate detail", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.get(`${API_BASE}/social-service-certificates/${state.certId}`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const detail = await res.json();
    expect(detail.certificate_number).toBe(state.certNumber);
    expect(detail.order_id).toBe(state.orderId);
    expect(detail.status).toBe("pending_approval");
  });

  test("5 — Get PDF presigned URL", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.get(`${API_BASE}/social-service-certificates/${state.certId}/pdf`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.url).toBeTruthy();
    expect(data.url).toContain("http");
  });

  test("6 — Approve certificate", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.post(`${API_BASE}/social-service-certificates/${state.certId}/approve`, {
      headers: h,
      data: {},
    });
    expect(res.ok()).toBeTruthy();
    const result = await res.json();
    expect(["approved", "sent"]).toContain(result.status);
    expect(result.certificate_number).toBe(state.certNumber);
  });

  test("7 — Certificate no longer in pending list", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.get(`${API_BASE}/social-service-certificates/pending`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const pending = await res.json();
    const found = pending.find((c: any) => c.id === state.certId);
    expect(found).toBeFalsy();
  });

  test("8 — Certificate appears in /all with approved/sent status", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.get(`${API_BASE}/social-service-certificates/all`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const all = await res.json();
    const cert = all.find((c: any) => c.id === state.certId);
    expect(cert).toBeTruthy();
    expect(["approved", "sent"]).toContain(cert.status);
  });

  test("9 — Create second order, deliver, then void certificate", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    // Create order
    const orderRes = await request.post(`${API_BASE}/sales/orders`, {
      headers: h,
      data: {
        customer_id: KNOWN.customers.johnson.id,
        cemetery_id: KNOWN.cemeteries.oakwood.id,
        order_date: new Date().toISOString(),
        required_date: new Date().toISOString(),
        scheduled_date: todayISO(),
        deceased_name: "Jane B. Doe",
        notes: "SSC E2E void test",
        lines: [
          {
            product_id: KNOWN.products.gravelinerSS.id,
            description: "Graveliner SS",
            quantity: 1,
            unit_price: KNOWN.products.gravelinerSS.price,
          },
        ],
      },
    });
    expect(orderRes.ok()).toBeTruthy();
    const order2 = await orderRes.json();
    state.order2Id = order2.id;
    state.order2Number = order2.number;

    // PATCH to set deceased_name (create_sales_order doesn't copy it)
    await request.patch(`${API_BASE}/sales/orders/${state.order2Id}`, {
      headers: h,
      data: { deceased_name: "Jane B. Doe" },
    });

    // Confirm
    const confirmRes = await request.patch(`${API_BASE}/sales/orders/${state.order2Id}`, {
      headers: h,
      data: { status: "confirmed" },
    });
    expect(confirmRes.ok()).toBeTruthy();

    // Create delivery
    const createDelRes = await request.post(`${API_BASE}/delivery/deliveries`, {
      headers: h,
      data: {
        delivery_type: "standard",
        order_id: state.order2Id,
        customer_id: KNOWN.customers.johnson.id,
        requested_date: todayISO(),
        priority: "normal",
      },
    });
    expect(createDelRes.ok()).toBeTruthy();
    const delivery2 = await createDelRes.json();
    state.delivery2Id = delivery2.id;

    // Complete delivery
    const completeRes = await request.post(`${API_BASE}/delivery/${state.delivery2Id}/complete`, {
      headers: h,
      data: {},
    });
    expect(completeRes.ok()).toBeTruthy();

    // Find the new certificate
    const certRes = await request.get(`${API_BASE}/social-service-certificates/pending`, { headers: h });
    const pending = await certRes.json();
    const cert2 = pending.find((c: any) => c.certificate_number === `${state.order2Number}-SSC`);
    expect(cert2).toBeTruthy();
    state.cert2Id = cert2.id;

    // Void the certificate
    const voidRes = await request.post(`${API_BASE}/social-service-certificates/${state.cert2Id}/void`, {
      headers: h,
      data: { reason: "E2E test void — duplicate order" },
    });
    expect(voidRes.ok()).toBeTruthy();
    const voidResult = await voidRes.json();
    expect(voidResult.status).toBe("voided");
    expect(voidResult.void_reason).toBe("E2E test void — duplicate order");
  });

  test("10 — Voided cert appears with voided status in /all", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.get(`${API_BASE}/social-service-certificates/all?status=voided`, { headers: h });
    expect(res.ok()).toBeTruthy();
    const voided = await res.json();
    const cert = voided.find((c: any) => c.id === state.cert2Id);
    expect(cert).toBeTruthy();
    expect(cert.status).toBe("voided");
    expect(cert.void_reason).toContain("duplicate order");
  });

  test("11 — Management page loads and shows certificates", async ({ page }) => {
    await login(page, "admin");
    await setupPage(page);
    await page.goto("/social-service-certificates");
    await page.waitForLoadState("networkidle");

    // Wait for table content
    await page.waitForSelector("table", { timeout: 10_000 });
    await snap(page, "management-page-loaded");

    // Should have at least the certificates we created
    const rows = page.locator("tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Verify certificate numbers appear
    const text = await page.textContent("body");
    expect(text).toContain("-SSC");
  });

  test("12 — Morning briefing SSC block shows for pending certs", async ({ request, page }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    // Create a third order with SS graveliner to have a pending cert
    const orderRes = await request.post(`${API_BASE}/sales/orders`, {
      headers: h,
      data: {
        customer_id: KNOWN.customers.johnson.id,
        cemetery_id: KNOWN.cemeteries.oakwood.id,
        order_date: new Date().toISOString(),
        required_date: new Date().toISOString(),
        scheduled_date: todayISO(),
        deceased_name: "Robert C. Wilson",
        notes: "SSC E2E briefing test",
        lines: [
          {
            product_id: KNOWN.products.gravelinerSS.id,
            description: "Graveliner SS",
            quantity: 1,
            unit_price: KNOWN.products.gravelinerSS.price,
          },
        ],
      },
    });
    const order3 = await orderRes.json();

    // PATCH to set deceased_name (create_sales_order doesn't copy it)
    await request.patch(`${API_BASE}/sales/orders/${order3.id}`, {
      headers: h,
      data: { deceased_name: "Robert C. Wilson" },
    });

    // Confirm
    await request.patch(`${API_BASE}/sales/orders/${order3.id}`, {
      headers: h,
      data: { status: "confirmed" },
    });

    // Create delivery
    const createDelRes = await request.post(`${API_BASE}/delivery/deliveries`, {
      headers: h,
      data: {
        delivery_type: "standard",
        order_id: order3.id,
        customer_id: KNOWN.customers.johnson.id,
        requested_date: todayISO(),
        priority: "normal",
      },
    });
    expect(createDelRes.ok()).toBeTruthy();
    const delivery3 = await createDelRes.json();

    // Complete delivery
    await request.post(`${API_BASE}/delivery/${delivery3.id}/complete`, {
      headers: h,
      data: {},
    });

    // Now login and go to dashboard to see the briefing
    await login(page, "admin");
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    await snap(page, "dashboard-with-ssc-block");

    // Check that the SSC section text appears
    const body = await page.textContent("body");
    expect(body).toContain("Social Service Certificates");
  });

  test("13 — Cannot approve an already-voided certificate", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.post(`${API_BASE}/social-service-certificates/${state.cert2Id}/approve`, {
      headers: h,
      data: {},
    });
    expect(res.status()).toBe(400);
  });

  test("14 — Cannot void an already-voided certificate", async ({ request }) => {
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.post(`${API_BASE}/social-service-certificates/${state.cert2Id}/void`, {
      headers: h,
      data: { reason: "double void attempt" },
    });
    expect(res.status()).toBe(400);
  });

  test("15 — Status filter works on management page", async ({ page }) => {
    await login(page, "admin");
    await setupPage(page);
    await page.goto("/social-service-certificates");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("table", { timeout: 10_000 });

    // Filter to voided only
    await page.click("button:has-text('All statuses')");
    await page.waitForTimeout(300);
    await page.click("[role='option']:has-text('Voided')");
    await page.waitForTimeout(1000);

    await snap(page, "filtered-voided");

    // All visible rows should have "Voided" badge
    const badges = page.locator("tbody span:has-text('Voided')");
    const count = await badges.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

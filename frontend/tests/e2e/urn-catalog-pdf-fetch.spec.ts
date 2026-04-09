import { test, expect, APIRequestContext } from "@playwright/test";

const STAGING_API = "https://sunnycresterp-staging.up.railway.app";
const API_BASE = `${STAGING_API}/api/v1`;
const TENANT_SLUG = "testco";

const CREDS = { email: "admin@testco.com", password: "TestAdmin123!" };

async function getApiToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    headers: { "X-Company-Slug": TENANT_SLUG, "Content-Type": "application/json" },
    data: { email: CREDS.email, password: CREDS.password },
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

test.describe("Urn Catalog PDF Auto-Fetch", () => {
  test("fetch-pdf endpoint downloads catalog and detects changes", async ({ request }) => {
    test.setTimeout(300_000); // 5 min — PDF download + parse can be slow
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    // First call — should download the PDF
    const res = await request.post(`${API_BASE}/urns/catalog/fetch-pdf`, {
      headers: h,
      timeout: 120_000,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(typeof data.downloaded).toBe("boolean");
    expect(typeof data.changed).toBe("boolean");

    if (data.downloaded) {
      expect(data.pdf_url).toBeTruthy();
      expect(data.pdf_url).toContain("http");
    }

    // Verify tenant settings were updated with catalog_pdf_last_fetched
    const settingsRes = await request.get(`${API_BASE}/urns/settings`, { headers: h });
    expect(settingsRes.ok()).toBeTruthy();
    const settings = await settingsRes.json();
    expect(settings.catalog_pdf_last_fetched).toBeTruthy();
    expect(settings.catalog_pdf_hash).toBeTruthy();

    // Second call — should detect no change (same PDF)
    const res2 = await request.post(`${API_BASE}/urns/catalog/fetch-pdf`, {
      headers: h,
      timeout: 120_000,
    });
    expect(res2.ok()).toBeTruthy();
    const data2 = await res2.json();
    expect(data2.downloaded).toBe(true);
    expect(data2.changed).toBe(false); // Same PDF, hash unchanged
    expect(data2.sync_log_id).toBeNull(); // No parse triggered
  });

  test("force flag triggers re-parse even when PDF unchanged", async ({ request }) => {
    test.setTimeout(300_000);
    const token = await getApiToken(request);
    const h = apiHeaders(token);

    const res = await request.post(`${API_BASE}/urns/catalog/fetch-pdf?force=true`, {
      headers: h,
      timeout: 120_000,
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.downloaded).toBe(true);
    expect(data.changed).toBe(true); // Force always reports as changed
    expect(data.sync_log_id).toBeTruthy(); // Parse was triggered
  });
});

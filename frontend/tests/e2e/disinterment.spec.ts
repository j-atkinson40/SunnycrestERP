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
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 20_000,
  });
  await page.waitForLoadState("networkidle");
}

async function getApiToken(
  request: APIRequestContext,
  role: keyof typeof CREDS = "admin"
): Promise<string> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    headers: {
      "X-Company-Slug": TENANT_SLUG,
      "Content-Type": "application/json",
    },
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

const SHOTS = "tests/e2e/screenshots/disinterment";

async function snap(page: Page, name: string) {
  await page.screenshot({
    path: `${SHOTS}/${name}.png`,
    fullPage: true,
  });
}

// ---------------------------------------------------------------------------
// Shared state across tests
// ---------------------------------------------------------------------------

const state: {
  token?: string;
  caseId?: string;
  caseNumber?: string;
  intakeToken?: string;
  chargeTypeIds?: string[];
  hazardChargeTypeId?: string;
  rotationListId?: string;
  rotationMemberIds?: string[];
  driverUserId?: string;
  envelopeId?: string;
  invoiceId?: string;
  // Seeded entities
  cemeteryMappedId?: string;
  cemeteryUnmappedId?: string;
  funeralHomeId?: string;
  locationIds?: string[];
} = {};

// ---------------------------------------------------------------------------
// Seed helper — enables modules and creates test data via API
// ---------------------------------------------------------------------------

async function ensureExtensionsEnabled(
  request: APIRequestContext,
  token: string
): Promise<void> {
  // Install disinterment_management extension via POST /extensions/{key}/install
  const res = await request.post(
    `${API_BASE}/extensions/disinterment_management/install`,
    { headers: apiHeaders(token) }
  );
  // 200 = installed, 409 = already installed — both OK
  if (!res.ok() && res.status() !== 409) {
    // Fallback: try enabling as a module (pre-migration staging)
    await request.put(`${API_BASE}/modules/disinterment_management`, {
      headers: apiHeaders(token),
      data: { enabled: true },
    });
    await request.put(`${API_BASE}/modules/union_rotation`, {
      headers: apiHeaders(token),
      data: { enabled: true },
    });
  }
}

// ===========================================================================
// SETUP — seed test data via API before all tests
// ===========================================================================

test.describe.serial("Disinterment Flow Tests", () => {
  test.beforeAll(async ({ request }) => {
    state.token = await getApiToken(request, "admin");

    // Enable required extensions
    await ensureExtensionsEnabled(request, state.token);

    // Discover driver user ID by logging in as driver and calling /auth/me
    const driverToken = await getApiToken(request, "driver");
    const driverMeRes = await request.get(`${API_BASE}/auth/me`, {
      headers: apiHeaders(driverToken),
    });
    if (driverMeRes.ok()) {
      const driverMe = await driverMeRes.json();
      state.driverUserId = driverMe.id;
    }

    // Seed charge types (3 total, 1 hazard pay)
    const chargeTypeNames = [
      { name: "Equipment Rental", calculation_type: "flat", default_rate: 250, is_hazard_pay: false },
      { name: "Transport Fee", calculation_type: "per_mile", default_rate: 3.5, is_hazard_pay: false },
      { name: "Hazard Removal", calculation_type: "flat", default_rate: 500, is_hazard_pay: true },
    ];

    state.chargeTypeIds = [];
    for (const ct of chargeTypeNames) {
      const res = await request.post(`${API_BASE}/disinterment-charge-types`, {
        headers: apiHeaders(state.token),
        data: ct,
      });
      if (res.ok()) {
        const body = await res.json();
        state.chargeTypeIds.push(body.id);
        if (ct.is_hazard_pay) state.hazardChargeTypeId = body.id;
      }
    }

    // Seed a rotation list for hazard_pay
    const rotRes = await request.post(`${API_BASE}/union-rotations`, {
      headers: apiHeaders(state.token),
      data: {
        name: "Disinterment Hazard — Test",
        trigger_type: "hazard_pay",
        assignment_mode: "sole_driver",
        trigger_config: {},
      },
    });
    if (rotRes.ok()) {
      const rotBody = await rotRes.json();
      state.rotationListId = rotBody.id;
    }

    // Add driver as rotation member if we have both IDs
    if (state.rotationListId && state.driverUserId) {
      await request.put(
        `${API_BASE}/union-rotations/${state.rotationListId}/members`,
        {
          headers: apiHeaders(state.token),
          data: {
            members: [
              { user_id: state.driverUserId, rotation_position: 1, active: true },
            ],
          },
        }
      );
    }
  });

  // =========================================================================
  // 1. Create a disinterment case — returns case_number and intake_token
  // =========================================================================

  test("1. Create a disinterment case", async ({ request }) => {
    const res = await request.post(`${API_BASE}/disinterments`, {
      headers: apiHeaders(state.token!),
      data: { decedent_name: "John Doe" },
    });

    expect(res.status()).toBe(201);
    const body = await res.json();

    expect(body.id).toBeTruthy();
    expect(body.case_number).toMatch(/^DIS-\d{4}-\d{4}$/);
    expect(body.status).toBe("intake");
    expect(body.intake_token).toBeTruthy();
    expect(body.decedent_name).toBe("John Doe");

    state.caseId = body.id;
    state.caseNumber = body.case_number;
    state.intakeToken = body.intake_token;
  });

  // =========================================================================
  // 2. Validate intake token (public endpoint)
  // =========================================================================

  test("2. Validate intake token", async ({ request }) => {
    const res = await request.get(`${API_BASE}/intake/${state.intakeToken}`, {
      headers: { "Content-Type": "application/json" },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.case_number).toBe(state.caseNumber);
    expect(body.already_submitted).toBe(false);
    expect(body.company_name).toBeTruthy();
  });

  // =========================================================================
  // 3. Submit intake form (public endpoint)
  // =========================================================================

  test("3. Submit intake form", async ({ request }) => {
    const res = await request.post(`${API_BASE}/intake/${state.intakeToken}`, {
      headers: { "Content-Type": "application/json" },
      data: {
        decedent_name: "John Doe",
        date_of_death: "2025-01-15",
        date_of_burial: "2025-01-20",
        vault_description: "Standard concrete vault",
        cemetery_name: "Oakwood",
        cemetery_lot_section: "Section B",
        cemetery_lot_space: "Lot 42",
        reason: "Family relocation to new state",
        destination: "Greenfield Memorial Park, Ohio",
        funeral_director_name: "Jane Smith",
        funeral_director_email: "jane@smithfh.com",
        funeral_director_phone: "555-0123",
        funeral_home_name: "Smith",
        next_of_kin: [
          {
            name: "Mary Doe",
            email: "mary@doe.com",
            phone: "555-0456",
            relationship: "Spouse",
          },
        ],
        confirmed_accurate: true,
      },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.case_number).toBe(state.caseNumber);
  });

  // =========================================================================
  // 4. Duplicate intake submission blocked (409)
  // =========================================================================

  test("4. Duplicate intake submission blocked", async ({ request }) => {
    const res = await request.post(`${API_BASE}/intake/${state.intakeToken}`, {
      headers: { "Content-Type": "application/json" },
      data: {
        decedent_name: "John Doe",
        reason: "Duplicate test",
        destination: "Nowhere",
        funeral_director_name: "Test",
        funeral_director_email: "test@test.com",
      },
    });

    expect(res.status()).toBe(409);
  });

  // =========================================================================
  // 5. Get case detail after intake — has submitted data
  // =========================================================================

  test("5. Get case detail after intake", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/disinterments/${state.caseId}`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("intake");
    expect(body.decedent_name).toBe("John Doe");
    expect(body.reason).toBe("Family relocation to new state");
    expect(body.intake_submitted_at).toBeTruthy();
    expect(body.signatures).toHaveLength(4);
    expect(body.signatures[0].status).toBe("not_sent");
  });

  // =========================================================================
  // 6. List cases — search by decedent name
  // =========================================================================

  test("6. List cases with search", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/disinterments?search=John+Doe`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.items).toBeDefined();
    expect(body.total).toBeGreaterThanOrEqual(1);

    const match = body.items.find(
      (i: { id: string }) => i.id === state.caseId
    );
    expect(match).toBeTruthy();
    expect(match.case_number).toBe(state.caseNumber);
  });

  // =========================================================================
  // 7. List cases filtered by status
  // =========================================================================

  test("7. List cases filtered by status", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/disinterments?status=intake`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.items.length).toBeGreaterThanOrEqual(1);
    for (const item of body.items) {
      expect(item.status).toBe("intake");
    }
  });

  // =========================================================================
  // 8. Update intake data (staff review/edit)
  // =========================================================================

  test("8. Update intake data", async ({ request }) => {
    const res = await request.patch(
      `${API_BASE}/disinterments/${state.caseId}/intake`,
      {
        headers: apiHeaders(state.token!),
        data: {
          vault_description: "Bronze vault, reinforced",
          cemetery_lot_section: "Section A",
        },
      }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.vault_description).toBe("Bronze vault, reinforced");
    expect(body.cemetery_lot_section).toBe("Section A");
  });

  // =========================================================================
  // 9. Accept quote — advances to quote_accepted
  // =========================================================================

  test("9. Accept quote with hazard pay", async ({ request }) => {
    const quoteAmount = 1250.0;

    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/accept-quote?quote_amount=${quoteAmount}&has_hazard_pay=true`,
      { headers: apiHeaders(state.token!) }
    );

    if (res.status() !== 200) {
      const errBody = await res.json().catch(() => ({}));
      console.error("Accept quote failed:", res.status(), JSON.stringify(errBody));
    }
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("quote_accepted");
    expect(body.accepted_quote_amount).toBeTruthy();
    expect(body.has_hazard_pay).toBe(true);
  });

  // =========================================================================
  // 10. Send for signatures — triggers DocuSign (stub mode)
  // =========================================================================

  test("10. Send for signatures", async ({ request }) => {
    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/send-signatures`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("signatures_pending");
    expect(body.docusign_envelope_id).toBeTruthy();
    state.envelopeId = body.docusign_envelope_id;

    // At least one signer should be "sent"
    const sentCount = body.signatures.filter(
      (s: { status: string }) => s.status === "sent"
    ).length;
    expect(sentCount).toBeGreaterThanOrEqual(1);
  });

  // =========================================================================
  // 11. Cannot schedule before signatures complete (422)
  // =========================================================================

  test("11. Cannot schedule before signatures complete", async ({
    request,
  }) => {
    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/schedule`,
      {
        headers: apiHeaders(state.token!),
        data: {
          scheduled_date: futureDate(7),
          assigned_driver_id: state.driverUserId || null,
        },
      }
    );

    expect(res.status()).toBe(422);
  });

  // =========================================================================
  // 12. DocuSign webhook — first signer completes
  // =========================================================================

  test("12. DocuSign webhook — funeral_home signs", async ({ request }) => {
    const res = await request.post(`${API_BASE}/docusign/webhook`, {
      headers: { "Content-Type": "application/json" },
      data: {
        envelopeId: state.envelopeId,
        recipients: {
          signers: [
            { roleName: "funeral_home", status: "Completed" },
          ],
        },
      },
    });

    expect(res.status()).toBe(200);

    // Check case — should still be signatures_pending
    const caseRes = await request.get(
      `${API_BASE}/disinterments/${state.caseId}`,
      { headers: apiHeaders(state.token!) }
    );
    const caseBody = await caseRes.json();
    expect(caseBody.status).toBe("signatures_pending");

    const fhSig = caseBody.signatures.find(
      (s: { party: string }) => s.party === "funeral_home"
    );
    expect(fhSig.status).toBe("signed");
  });

  // =========================================================================
  // 13. DocuSign webhook — remaining signers complete → signatures_complete
  // =========================================================================

  test("13. DocuSign webhook — all signers complete", async ({ request }) => {
    // Send completion for remaining parties
    for (const role of ["cemetery", "next_of_kin", "manufacturer"]) {
      await request.post(`${API_BASE}/docusign/webhook`, {
        headers: { "Content-Type": "application/json" },
        data: {
          envelopeId: state.envelopeId,
          recipients: {
            signers: [{ roleName: role, status: "Completed" }],
          },
        },
      });
    }

    // Check case — should now be signatures_complete
    const caseRes = await request.get(
      `${API_BASE}/disinterments/${state.caseId}`,
      { headers: apiHeaders(state.token!) }
    );
    const caseBody = await caseRes.json();
    expect(caseBody.status).toBe("signatures_complete");

    // All signatures should be "signed" or "not_sent"
    for (const sig of caseBody.signatures) {
      expect(["signed", "not_sent"]).toContain(sig.status);
    }
  });

  // =========================================================================
  // 14. Schedule disinterment — with rotation assignment for hazard_pay
  // =========================================================================

  test("14. Schedule disinterment", async ({ request }) => {
    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/schedule`,
      {
        headers: apiHeaders(state.token!),
        data: {
          scheduled_date: futureDate(7),
          assigned_driver_id: state.driverUserId || null,
          assigned_crew: [],
        },
      }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("scheduled");
    expect(body.scheduled_date).toBeTruthy();

    // If rotation was configured and driver matched, rotation_assignment_id may be set
    // (depends on whether module was enabled and rotation list has active members)
  });

  // =========================================================================
  // 15. Complete case — auto-generates invoice
  // =========================================================================

  test("15. Complete case with auto-invoice", async ({ request }) => {
    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/complete`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("complete");
    expect(body.completed_at).toBeTruthy();

    // Invoice may or may not be generated depending on whether a customer
    // record is linked to the funeral home. Either way, completion succeeds.
    if (body.invoice_id) {
      state.invoiceId = body.invoice_id;
    }
  });

  // =========================================================================
  // 16. Cannot cancel a completed case (422)
  // =========================================================================

  test("16. Cannot cancel a completed case", async ({ request }) => {
    const res = await request.post(
      `${API_BASE}/disinterments/${state.caseId}/cancel`,
      { headers: apiHeaders(state.token!) }
    );

    expect(res.status()).toBe(422);
  });

  // =========================================================================
  // 17. Create and cancel a case from intake stage
  // =========================================================================

  test("17. Create and cancel a case", async ({ request }) => {
    // Create
    const createRes = await request.post(`${API_BASE}/disinterments`, {
      headers: apiHeaders(state.token!),
      data: { decedent_name: "Cancel Test" },
    });
    expect(createRes.status()).toBe(201);
    const created = await createRes.json();

    // Cancel
    const cancelRes = await request.post(
      `${API_BASE}/disinterments/${created.id}/cancel`,
      { headers: apiHeaders(state.token!) }
    );
    expect(cancelRes.status()).toBe(200);
    const cancelled = await cancelRes.json();
    expect(cancelled.status).toBe("cancelled");
  });

  // =========================================================================
  // 18. Invalid intake token returns 404
  // =========================================================================

  test("18. Invalid intake token returns 404", async ({ request }) => {
    const res = await request.get(`${API_BASE}/intake/totally-invalid-token`, {
      headers: { "Content-Type": "application/json" },
    });
    expect(res.status()).toBe(404);
  });

  // =========================================================================
  // 19. Case not found returns 404
  // =========================================================================

  test("19. Case not found returns 404", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/disinterments/00000000-0000-0000-0000-000000000000`,
      { headers: apiHeaders(state.token!) }
    );
    expect(res.status()).toBe(404);
  });

  // =========================================================================
  // 20. Charge type CRUD
  // =========================================================================

  test("20. Charge type CRUD", async ({ request }) => {
    // Create
    const createRes = await request.post(
      `${API_BASE}/disinterment-charge-types`,
      {
        headers: apiHeaders(state.token!),
        data: {
          name: "CRUD Test Type",
          calculation_type: "hourly",
          default_rate: 75,
          is_hazard_pay: false,
        },
      }
    );
    expect(createRes.status()).toBe(201);
    const created = await createRes.json();
    expect(created.name).toBe("CRUD Test Type");

    // List
    const listRes = await request.get(
      `${API_BASE}/disinterment-charge-types?include_inactive=true`,
      { headers: apiHeaders(state.token!) }
    );
    expect(listRes.status()).toBe(200);
    const list = await listRes.json();
    expect(list.length).toBeGreaterThanOrEqual(1);

    // Update (toggle active off)
    const updateRes = await request.patch(
      `${API_BASE}/disinterment-charge-types/${created.id}`,
      {
        headers: apiHeaders(state.token!),
        data: { active: false },
      }
    );
    expect(updateRes.status()).toBe(200);
    const updated = await updateRes.json();
    expect(updated.active).toBe(false);

    // Delete (soft)
    const deleteRes = await request.delete(
      `${API_BASE}/disinterment-charge-types/${created.id}`,
      { headers: apiHeaders(state.token!) }
    );
    expect(deleteRes.status()).toBe(204);
  });

  // =========================================================================
  // 21. UI — Disinterment list page loads
  // =========================================================================

  test("21. UI — Disinterment list page loads", async ({ page }) => {
    await login(page, "admin");
    await page.goto("/disinterments");
    await page.waitForLoadState("networkidle");
    await snap(page, "21-list-page");

    // Check for the page heading
    const heading = page.getByRole("heading", { name: /disinterment/i });
    await expect(heading).toBeVisible({ timeout: 10_000 });

    // Should show at least one case from API tests
    const bodyText = await page.textContent("body");
    // The page should have rendered (not blank or error)
    expect(bodyText).toBeTruthy();
  });

  // =========================================================================
  // 22. UI — Case detail page loads with pipeline
  // =========================================================================

  test("22. UI — Case detail page loads", async ({ page }) => {
    await login(page, "admin");

    if (state.caseId) {
      await page.goto(`/disinterments/${state.caseId}`);
      await page.waitForLoadState("networkidle");
      await snap(page, "22-detail-page");

      // Should see the case number or decedent name
      const bodyText = await page.textContent("body");
      expect(
        bodyText?.includes("John Doe") || bodyText?.includes("DIS-")
      ).toBeTruthy();
    }
  });
});

// ===========================================================================
// UNION ROTATION TESTS
// ===========================================================================

test.describe.serial("Union Rotation Tests", () => {
  const rotState: {
    token?: string;
    listId?: string;
    memberIds?: string[];
    driverUserId?: string;
  } = {};

  test.beforeAll(async ({ request }) => {
    rotState.token = await getApiToken(request, "admin");

    // Get driver user ID by logging in as driver
    const driverToken = await getApiToken(request, "driver");
    const driverMeRes = await request.get(`${API_BASE}/auth/me`, {
      headers: apiHeaders(driverToken),
    });
    if (driverMeRes.ok()) {
      const driverMe = await driverMeRes.json();
      rotState.driverUserId = driverMe.id;
    }
  });

  // =========================================================================
  // 23. Create rotation list
  // =========================================================================

  test("23. Create rotation list", async ({ request }) => {
    const res = await request.post(`${API_BASE}/union-rotations`, {
      headers: apiHeaders(rotState.token!),
      data: {
        name: "Saturday Crew — Test",
        trigger_type: "day_of_week",
        assignment_mode: "longest_day",
        trigger_config: { days: ["saturday"] },
      },
    });

    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.id).toBeTruthy();
    expect(body.name).toBe("Saturday Crew — Test");
    expect(body.trigger_type).toBe("day_of_week");
    expect(body.assignment_mode).toBe("longest_day");
    rotState.listId = body.id;
  });

  // =========================================================================
  // 24. List rotation lists
  // =========================================================================

  test("24. List rotation lists", async ({ request }) => {
    const res = await request.get(`${API_BASE}/union-rotations`, {
      headers: apiHeaders(rotState.token!),
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThanOrEqual(1);

    const found = body.find(
      (l: { id: string }) => l.id === rotState.listId
    );
    expect(found).toBeTruthy();
    expect(found.trigger_type).toBe("day_of_week");
  });

  // =========================================================================
  // 25. Add members to rotation list (PUT replace)
  // =========================================================================

  test("25. Add members to rotation list", async ({ request }) => {
    if (!rotState.driverUserId) {
      test.skip();
      return;
    }

    const res = await request.put(
      `${API_BASE}/union-rotations/${rotState.listId}/members`,
      {
        headers: apiHeaders(rotState.token!),
        data: {
          members: [
            { user_id: rotState.driverUserId, rotation_position: 1, active: true },
          ],
        },
      }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThanOrEqual(1);

    const member = body.find(
      (m: { user_id: string }) => m.user_id === rotState.driverUserId
    );
    expect(member).toBeTruthy();
    expect(member.rotation_position).toBe(1);
    expect(member.active).toBe(true);
    rotState.memberIds = body.map((m: { id: string }) => m.id);
  });

  // =========================================================================
  // 26. Get members with user names
  // =========================================================================

  test("26. Get members with user names", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/union-rotations/${rotState.listId}/members`,
      { headers: apiHeaders(rotState.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);

    // Each member should have user_name populated
    for (const m of body) {
      if (m.user_id === rotState.driverUserId) {
        expect(m.user_name).toBeTruthy();
      }
    }
  });

  // =========================================================================
  // 27. Toggle member inactive
  // =========================================================================

  test("27. Toggle member inactive", async ({ request }) => {
    if (!rotState.memberIds || rotState.memberIds.length === 0) {
      test.skip();
      return;
    }

    const memberId = rotState.memberIds[0];
    const res = await request.patch(
      `${API_BASE}/union-rotations/${rotState.listId}/members/${memberId}`,
      {
        headers: apiHeaders(rotState.token!),
        data: { active: false },
      }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.active).toBe(false);

    // Re-activate for future tests
    await request.patch(
      `${API_BASE}/union-rotations/${rotState.listId}/members/${memberId}`,
      {
        headers: apiHeaders(rotState.token!),
        data: { active: true },
      }
    );
  });

  // =========================================================================
  // 28. Assignment history — initially empty
  // =========================================================================

  test("28. Assignment history — initially empty", async ({ request }) => {
    const res = await request.get(
      `${API_BASE}/union-rotations/${rotState.listId}/history`,
      { headers: apiHeaders(rotState.token!) }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.items).toBeDefined();
    expect(body.total).toBeDefined();
    // New list shouldn't have assignments yet
    expect(body.items).toHaveLength(0);
  });

  // =========================================================================
  // 29. Update rotation list
  // =========================================================================

  test("29. Update rotation list", async ({ request }) => {
    const res = await request.patch(
      `${API_BASE}/union-rotations/${rotState.listId}`,
      {
        headers: apiHeaders(rotState.token!),
        data: { name: "Saturday Crew — Updated" },
      }
    );

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.name).toBe("Saturday Crew — Updated");
  });

  // =========================================================================
  // 30. Delete rotation list (soft)
  // =========================================================================

  test("30. Delete rotation list", async ({ request }) => {
    // Create a throwaway list to delete
    const createRes = await request.post(`${API_BASE}/union-rotations`, {
      headers: apiHeaders(rotState.token!),
      data: {
        name: "Delete Me — Test",
        trigger_type: "manual",
        assignment_mode: "sole_driver",
        trigger_config: {},
      },
    });
    expect(createRes.status()).toBe(201);
    const created = await createRes.json();

    const deleteRes = await request.delete(
      `${API_BASE}/union-rotations/${created.id}`,
      { headers: apiHeaders(rotState.token!) }
    );
    expect(deleteRes.status()).toBe(204);

    // Verify it no longer appears in list
    const listRes = await request.get(`${API_BASE}/union-rotations`, {
      headers: apiHeaders(rotState.token!),
    });
    const list = await listRes.json();
    const found = list.find((l: { id: string }) => l.id === created.id);
    expect(found).toBeFalsy();
  });
});

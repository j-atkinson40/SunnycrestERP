#!/usr/bin/env python3
"""Seed staging via the API — no direct DB access needed.

Run: python scripts/seed_staging_api.py

Uses the staging backend API to create test data.
Requires: STAGING_URL env var (defaults to https://sunnycresterp-staging.up.railway.app)
"""

import os
import sys
import httpx

BASE = os.environ.get("STAGING_URL", "https://sunnycresterp-staging.up.railway.app")
API = f"{BASE}/api/v1"
SLUG = "testco"

# Admin credentials — register first, then login
ADMIN_EMAIL = "admin@testco.com"
ADMIN_PASSWORD = "TestAdmin123!"


def _headers_with_slug(token=None):
    """Build headers with tenant slug + optional auth."""
    h = {"X-Company-Slug": SLUG}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def main():
    client = httpx.Client(timeout=30.0)
    print(f"=== Staging API Seed ===")
    print(f"Target: {BASE}")
    print(f"Tenant slug: {SLUG}")
    print()

    # Step 1: Register company + admin via public endpoint
    print("[1] Registering company + admin user...")
    r = client.post(f"{API}/companies/register", json={
        "company_name": "Test Vault Co",
        "company_slug": SLUG,
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "first_name": "Admin",
        "last_name": "User",
    })
    if r.status_code in (200, 201):
        print(f"  -> Registered company + admin: {r.status_code}")
    elif r.status_code == 409 or "already" in r.text.lower() or "taken" in r.text.lower():
        print(f"  -> Already exists, continuing")
    else:
        print(f"  -> Register response: {r.status_code} {r.text[:300]}")

    # Step 2: Login with tenant slug header
    print("[2] Logging in as admin...")
    r = client.post(f"{API}/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, headers={"X-Company-Slug": SLUG})
    if r.status_code != 200:
        print(f"  FAILED: {r.status_code} {r.text[:300]}")
        sys.exit(1)
    token = r.json()["access_token"]
    headers = _headers_with_slug(token)
    print(f"  -> Logged in OK")

    # Step 3: Create product categories
    print("[3] Creating product categories...")
    cat_ids = {}
    cats = [
        "Burial Vaults - Triple Reinforced",
        "Burial Vaults - Double Reinforced",
        "Burial Vaults - Single Reinforced",
        "Burial Vaults - Non Reinforced",
        "Graveside Service",
        "Other Charges",
    ]
    for name in cats:
        r = client.post(f"{API}/products/categories", headers=headers, json={"name": name})
        if r.status_code in (200, 201):
            cat_ids[name] = r.json()["id"]
            print(f"  -> {name}: created")
        elif r.status_code == 409:
            print(f"  -> {name}: already exists")
        else:
            print(f"  -> {name}: {r.status_code} {r.text[:100]}")

    # Step 4: Create products
    print("[4] Creating products...")
    products = [
        ("Wilbert Bronze", "WB-001", 13452.00, "Burial Vaults - Triple Reinforced"),
        ("Bronze Triune", "BT-001", 3864.00, "Burial Vaults - Double Reinforced"),
        ("Copper Triune", "CT-001", 3457.00, "Burial Vaults - Double Reinforced"),
        ("SST Triune", "SST-001", 2850.00, "Burial Vaults - Double Reinforced"),
        ("Cameo Rose", "CR-001", 2850.00, "Burial Vaults - Double Reinforced"),
        ("Veteran Triune", "VT-001", 2850.00, "Burial Vaults - Double Reinforced"),
        ("Tribute", "TR-001", 2570.00, "Burial Vaults - Single Reinforced"),
        ("Venetian", "VN-001", 1934.00, "Burial Vaults - Single Reinforced"),
        ("Continental", "CN-001", 1607.00, "Burial Vaults - Single Reinforced"),
        ("Salute", "SL-001", 1475.00, "Burial Vaults - Single Reinforced"),
        ("Monticello", "MN-001", 1405.00, "Burial Vaults - Single Reinforced"),
        ("Monarch", "MO-001", 1176.00, "Burial Vaults - Non Reinforced"),
        ("Graveliner", "GL-001", 996.00, "Burial Vaults - Non Reinforced"),
        ("Graveliner SS", "GS-001", 880.00, "Burial Vaults - Non Reinforced"),
        ("Full Equipment (with product)", "FE-WP", 300.00, "Graveside Service"),
        ("Full Equipment (without product)", "FE-NP", 600.00, "Graveside Service"),
        ("Lowering Device & Grass (with)", "LD-WP", 185.00, "Graveside Service"),
        ("Lowering Device & Grass (without)", "LD-NP", 487.00, "Graveside Service"),
        ("Tent Only (with)", "TO-WP", 225.00, "Graveside Service"),
        ("Tent Only (without)", "TO-NP", 557.00, "Graveside Service"),
        ("Sunday & Holiday", "SH-001", 550.00, "Other Charges"),
        ("Saturday Spring Burial", "SSB-001", 200.00, "Other Charges"),
        ("Late Arrival (per 30 min)", "LA-001", 75.00, "Other Charges"),
        ("Legacy Rush Fee", "LR-001", 100.00, "Other Charges"),
        ("Late Notice", "LN-001", 250.00, "Other Charges"),
    ]
    created = 0
    for name, sku, price, cat_name in products:
        payload = {"name": name, "sku": sku, "price": price}
        if cat_name in cat_ids:
            payload["category_id"] = cat_ids[cat_name]
        r = client.post(f"{API}/products", headers=headers, json=payload)
        if r.status_code in (200, 201):
            created += 1
        else:
            print(f"  -> {name}: {r.status_code} {r.text[:80]}")
    print(f"  -> {created}/{len(products)} products created")

    # Step 5: Create cemeteries
    print("[5] Creating cemeteries...")
    cems = [
        {"name": "Oakwood Cemetery", "city": "Auburn", "state": "NY"},
        {"name": "St. Mary's Cemetery", "city": "Skaneateles", "state": "NY",
         "cemetery_provides_lowering_device": True, "cemetery_provides_grass": True, "cemetery_provides_tent": True},
        {"name": "Lakeview Memorial Gardens", "city": "Syracuse", "state": "NY"},
    ]
    for cem in cems:
        r = client.post(f"{API}/cemeteries", headers=headers, json=cem)
        if r.status_code in (200, 201):
            print(f"  -> {cem['name']}: created")
        else:
            print(f"  -> {cem['name']}: {r.status_code} {r.text[:80]}")

    # Step 6: Create a price list version via preview + apply
    print("[6] Creating price list version...")
    r = client.post(f"{API}/price-management/increase/apply", headers=headers, json={
        "increase_type": "percentage",
        "increase_value": 0,
        "effective_date": "2026-04-07",
        "label": "Initial Price List 2026",
    })
    if r.status_code in (200, 201):
        vid = r.json().get("id")
        print(f"  -> Version created: {vid}")
        # Activate it
        r2 = client.post(f"{API}/price-management/versions/{vid}/action", headers=headers,
                         json={"action": "activate"})
        if r2.status_code == 200:
            print(f"  -> Activated")
    else:
        print(f"  -> {r.status_code} {r.text[:200]}")

    # Step 7: Seed KB categories
    print("[7] Knowledge base...")
    r = client.get(f"{API}/knowledge-base/categories", headers=headers)
    if r.status_code == 200:
        print(f"  -> Categories loaded ({len(r.json())} categories)")
    else:
        print(f"  -> KB categories: {r.status_code}")

    print()
    print("=== Seed complete ===")
    print(f"  Login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  API: {API}")


if __name__ == "__main__":
    main()

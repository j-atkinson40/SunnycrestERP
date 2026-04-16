"""Production smoke tests — lightweight read-only HTTP checks per tenant."""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.admin_smoke_test_result import AdminSmokeTestResult
from app.models.company import Company


UNIVERSAL_CHECKS = [
    ("health", "GET", "/api/v1/health", None, 200),
    ("vault_items", "GET", "/api/v1/vault/items?limit=1", "auth", 200),
    ("vault_summary", "GET", "/api/v1/vault/summary", "auth", 200),
]

VERTICAL_CHECKS = {
    "manufacturing": [
        ("orders", "GET", "/api/v1/sales/orders?limit=1", "auth", 200),
        ("crm_companies", "GET", "/api/v1/companies?limit=1", "auth", 200),
        ("programs", "GET", "/api/v1/programs/", "auth", 200),
    ],
    "funeral_home": [
        # Cases endpoint — placeholder, feature not yet built
        # ("cases", "GET", "/api/v1/cases?limit=1", "auth", 200),
    ],
    "cemetery": [
        # Plots endpoint — placeholder, feature not yet built
    ],
    "crematory": [],
}


async def _run_check(
    http: httpx.AsyncClient,
    base_url: str,
    tenant_slug: str,
    token: str | None,
    check: tuple,
) -> dict:
    name, method, path, auth_mode, expected_status = check
    headers = {"X-Company-Slug": tenant_slug}
    if auth_mode == "auth" and token:
        headers["Authorization"] = f"Bearer {token}"
    start = time.time()
    try:
        resp = await http.request(method, f"{base_url}{path}", headers=headers, timeout=10.0)
        elapsed = (time.time() - start) * 1000
        return {
            "check": name,
            "status_code": resp.status_code,
            "expected": expected_status,
            "passed": resp.status_code == expected_status,
            "elapsed_ms": int(elapsed),
            "error": None if resp.status_code == expected_status
                else f"expected {expected_status}, got {resp.status_code}",
        }
    except Exception as e:
        return {
            "check": name,
            "status_code": 0,
            "expected": expected_status,
            "passed": False,
            "elapsed_ms": int((time.time() - start) * 1000),
            "error": str(e)[:200],
        }


async def _get_smoke_token(
    http: httpx.AsyncClient, base_url: str, tenant_slug: str
) -> str | None:
    """Try to get a token for the tenant via a seeded admin account.

    Returns None if login fails — checks requiring auth will be marked failed.
    """
    email = os.getenv("SMOKE_TEST_EMAIL", "admin@testco.com")
    password = os.getenv("SMOKE_TEST_PASSWORD", "TestAdmin123!")
    try:
        resp = await http.post(
            f"{base_url}/api/v1/auth/login",
            headers={"X-Company-Slug": tenant_slug, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:
        pass
    return None


async def run_smoke_test(
    db: Session,
    company_id: str,
    trigger: str = "manual",
    deployment_id: str | None = None,
    triggered_by_admin_id: str | None = None,
    base_url_override: str | None = None,
) -> AdminSmokeTestResult:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError("Company not found")

    # Record start
    result = AdminSmokeTestResult(
        company_id=company_id,
        deployment_id=deployment_id,
        triggered_by_admin_id=triggered_by_admin_id,
        trigger=trigger,
        status="running",
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    base_url = base_url_override or os.getenv(
        "PRODUCTION_API_URL", "https://api.getbridgeable.com"
    )

    vertical = (company.vertical or "manufacturing").lower()
    checks = list(UNIVERSAL_CHECKS) + list(VERTICAL_CHECKS.get(vertical, []))

    start_ts = time.time()
    failures = []
    passed = 0

    async with httpx.AsyncClient() as http:
        token = await _get_smoke_token(http, base_url, company.slug)
        tasks = [_run_check(http, base_url, company.slug, token, c) for c in checks]
        check_results = await asyncio.gather(*tasks)

    for cr in check_results:
        if cr["passed"]:
            passed += 1
        else:
            failures.append(cr)

    duration = time.time() - start_ts
    result.checks_total = len(checks)
    result.checks_passed = passed
    result.checks_failed = len(failures)
    result.failures = failures if failures else None
    result.duration_seconds = duration
    result.status = "passed" if not failures else "failed"
    result.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(result)
    return result


def list_recent_results(
    db: Session, company_id: str | None = None, limit: int = 20
) -> list[AdminSmokeTestResult]:
    q = db.query(AdminSmokeTestResult)
    if company_id:
        q = q.filter(AdminSmokeTestResult.company_id == company_id)
    return q.order_by(AdminSmokeTestResult.started_at.desc()).limit(limit).all()


async def run_smoke_for_deployment(
    db: Session,
    deployment_id: str,
    affected_verticals: list[str],
    admin_user_id: str | None = None,
) -> list[AdminSmokeTestResult]:
    """Run parallel smoke tests for all live tenants in affected verticals."""
    q = db.query(Company).filter(Company.is_active == True)  # noqa: E712
    if "all" not in affected_verticals:
        q = q.filter(Company.vertical.in_(affected_verticals))
    # Exclude staging-flagged tenants (names starting with 'test' or 'staging')
    companies = [c for c in q.all() if not (c.slug or "").startswith(("test-", "staging-"))]

    async def _run_one(cid):
        try:
            return await run_smoke_test(
                db=db,
                company_id=cid,
                trigger="post_deployment",
                deployment_id=deployment_id,
                triggered_by_admin_id=admin_user_id,
            )
        except Exception:
            return None

    results = await asyncio.gather(*[_run_one(c.id) for c in companies])
    return [r for r in results if r is not None]

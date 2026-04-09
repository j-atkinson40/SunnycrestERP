#!/usr/bin/env python3
"""
Full end-to-end test of the 13-agent accounting suite against local PostgreSQL.
Steps 3-13 of the E2E spec.
"""
import json
import os
import sys
import time
from datetime import date

import requests

BASE = "http://localhost:8000/api/v1"
HEADERS = {"X-Company-Slug": "default", "Content-Type": "application/json"}
REPORT_DIR = "/tmp/agent_e2e_reports"

os.makedirs(REPORT_DIR, exist_ok=True)


def login():
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "admin@testco.com",
        "password": "TestAdmin123!",
    }, headers=HEADERS)
    r.raise_for_status()
    token = r.json()["access_token"]
    HEADERS["Authorization"] = f"Bearer {token}"
    print(f"  Token: {token[:20]}...")
    return token


def create_job(job_type: str, period_start: str, period_end: str, dry_run: bool = True):
    """Create an agent job and return its ID."""
    r = requests.post(f"{BASE}/agents/accounting", json={
        "job_type": job_type,
        "period_start": period_start,
        "period_end": period_end,
        "dry_run": dry_run,
    }, headers=HEADERS)
    if r.status_code != 201:
        print(f"  ERROR creating {job_type}: {r.status_code} {r.text}")
        return None
    data = r.json()
    return data["id"]


def poll_job(job_id: str, label: str, timeout: int = 60) -> dict:
    """Poll until job reaches a terminal state. Return full job dict."""
    start = time.time()
    last_status = ""
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/agents/accounting/{job_id}", headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        status = data["status"]
        if status != last_status:
            last_status = status
        if status in ("awaiting_approval", "complete", "failed", "rejected"):
            return data
        time.sleep(1)
    print(f"  TIMEOUT waiting for {label} (last status: {last_status})")
    return data


def approve_job(job: dict, expect_lock: bool = False) -> dict:
    """Approve a job via its approval token."""
    token = job.get("approval_token")
    if not token:
        print(f"  ERROR: No approval_token on job {job['id'][:8]}")
        return job
    r = requests.post(f"{BASE}/agents/approve/{token}", json={
        "action": "approve",
    }, headers={"Content-Type": "application/json"})
    if r.status_code != 200:
        print(f"  ERROR approving: {r.status_code} {r.text}")
        return job
    return r.json()


def get_anomalies(job_id: str) -> list:
    r = requests.get(f"{BASE}/agents/accounting/{job_id}/anomalies", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_report_html(job_id: str) -> str:
    r = requests.get(f"{BASE}/agents/accounting/{job_id}/report", headers=HEADERS)
    if r.status_code == 200:
        return r.text
    return ""


def print_job_summary(label: str, job: dict, anomalies: list = None):
    """Print compact job summary."""
    status = job["status"]
    anomaly_count = job.get("anomaly_count", 0)
    steps = job.get("run_log", [])
    step_count = len(steps) if steps else 0
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Status: {status} | Steps: {step_count} | Anomalies: {anomaly_count}")
    if steps:
        for s in steps:
            msg = s.get("message", "")[:80] if isinstance(s, dict) else str(s)[:80]
            step_name = s.get("step_name", "?") if isinstance(s, dict) else "?"
            print(f"    [{step_name}] {msg}")
    if anomalies:
        for a in anomalies[:10]:
            sev = a.get("severity", "?")
            desc = a.get("description", "")[:70]
            print(f"    {sev}: {desc}")
    print(f"{'='*60}")


# Track results for final summary
RESULTS = {}


def record(name, job, anomalies=None):
    RESULTS[name] = {
        "status": job["status"],
        "anomaly_count": job.get("anomaly_count", 0),
        "step_count": len(job.get("run_log", []) or []),
        "anomalies": anomalies or [],
        "job_id": job["id"],
        "approval_token": job.get("approval_token"),
    }


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 3 — Authenticate")
print("=" * 60)
login()

# ─── STEP 4: Weekly Agents ────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4 — Weekly Agents")
print("=" * 60)

weekly_agents = [
    ("ar_collections", "AR Collections", "2025-11-01", "2025-11-30"),
    ("unbilled_orders", "Unbilled Orders", "2025-11-01", "2025-11-30"),
    ("cash_receipts_matching", "Cash Receipts", "2025-11-01", "2025-11-30"),
]

for job_type, label, ps, pe in weekly_agents:
    print(f"\n  Creating {label}...")
    jid = create_job(job_type, ps, pe, dry_run=True)
    if not jid:
        continue
    job = poll_job(jid, label)
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary(label, job, anomalies)
    record(job_type, job, anomalies)

# ─── STEP 5: Month-End Close November ────────────────────────────
print("\n" + "=" * 60)
print("STEP 5 — Month-End Close (November)")
print("=" * 60)

jid = create_job("month_end_close", "2025-11-01", "2025-11-30", dry_run=False)
if jid:
    job = poll_job(jid, "Month-End Close Nov", timeout=120)
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("Month-End Close — November", job, anomalies)
    record("month_end_close_nov", job, anomalies)

    # ─── STEP 6: Approve November ─────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 6 — Approve November Close")
    print("=" * 60)

    if job["status"] == "awaiting_approval":
        approved = approve_job(job, expect_lock=True)
        print(f"  Approved → status: {approved['status']}")
        record("month_end_close_nov_approved", approved)

        # Verify period lock
        r = requests.get(f"{BASE}/agents/periods/locked", headers=HEADERS)
        if r.status_code == 200:
            locks = r.json()
            nov_locks = [l for l in locks if l.get("period_start") == "2025-11-01"]
            print(f"  Period locks: {len(locks)} total, {len(nov_locks)} for November")
        else:
            print(f"  Period locks endpoint: {r.status_code}")
    else:
        print(f"  Skipping approval — job status is {job['status']}")

# ─── STEP 7: Quarterly Agents ────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 7 — Quarterly Agents")
print("=" * 60)

quarterly_agents = [
    ("estimated_tax_prep", "Estimated Tax Prep", "2025-10-01", "2025-12-31"),
    ("inventory_reconciliation", "Inventory Reconciliation", "2025-10-01", "2025-12-31"),
    ("budget_vs_actual", "Budget vs Actual (no budget yet)", "2025-11-01", "2025-11-30"),
]

for job_type, label, ps, pe in quarterly_agents:
    print(f"\n  Creating {label}...")
    jid = create_job(job_type, ps, pe, dry_run=True)
    if not jid:
        continue
    job = poll_job(jid, label)
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary(label, job, anomalies)
    record(job_type, job, anomalies)

# ─── STEP 8: Annual Agents ───────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 8 — Annual Agents")
print("=" * 60)

# 8a. Annual Budget
print("\n  Creating Annual Budget...")
jid = create_job("annual_budget", "2025-01-01", "2025-12-31", dry_run=True)
if jid:
    job = poll_job(jid, "Annual Budget")
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("Annual Budget", job, anomalies)
    record("annual_budget", job, anomalies)

    # Approve annual budget so BvA can find it
    if job["status"] == "awaiting_approval":
        approved = approve_job(job)
        print(f"  Annual Budget approved → status: {approved['status']}")
        record("annual_budget_approved", approved)

# 8b. Approve the first BvA so we can re-run
if "budget_vs_actual" in RESULTS and RESULTS["budget_vs_actual"]["status"] == "awaiting_approval":
    first_bva = RESULTS["budget_vs_actual"]
    # Need to get full job data to have approval_token
    r = requests.get(f"{BASE}/agents/accounting/{first_bva['job_id']}", headers=HEADERS)
    if r.status_code == 200:
        first_bva_job = r.json()
        if first_bva_job.get("approval_token"):
            approved_bva = approve_job(first_bva_job)
            print(f"  First BvA approved → status: {approved_bva['status']}")

# 8c. Re-run Budget vs Actual (should now find formal budget)
print("\n  Re-running Budget vs Actual (with budget)...")
jid = create_job("budget_vs_actual", "2025-11-01", "2025-11-30", dry_run=True)
if jid:
    job = poll_job(jid, "BvA with Budget")
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("Budget vs Actual (with budget)", job, anomalies)
    record("budget_vs_actual_with_budget", job, anomalies)

    # Check if comparison_type is now formal_budget
    report = job.get("report_payload", {})
    comp_type = None
    if report:
        comp_type = report.get("comparison_type") or report.get("comparison_basis", {}).get("type")
    print(f"  Phase 9↔13 integration: comparison_type = {comp_type}")

# 8c. 1099 Prep
print("\n  Creating 1099 Prep...")
jid = create_job("1099_prep", "2025-01-01", "2025-12-31", dry_run=True)
if jid:
    job = poll_job(jid, "1099 Prep")
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("1099 Prep", job, anomalies)
    record("1099_prep", job, anomalies)

# ─── STEP 9: Year-End Close ──────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 9 — Year-End Close (December)")
print("=" * 60)

jid = create_job("year_end_close", "2025-12-01", "2025-12-31", dry_run=False)
if jid:
    job = poll_job(jid, "Year-End Close", timeout=180)
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("Year-End Close — December", job, anomalies)
    record("year_end_close", job, anomalies)

    # Print all 13 step results
    steps = job.get("run_log", []) or []
    print(f"\n  Year-End Close Steps ({len(steps)}/13):")
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            print(f"    Step {i+1}: [{s.get('step_name', '?')}] {s.get('message', '')[:80]}")

    if job["status"] == "awaiting_approval":
        approved = approve_job(job, expect_lock=True)
        print(f"  Year-End Close approved → status: {approved['status']}")
        record("year_end_close_approved", approved)

# ─── STEP 10: Tax Package ────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 10 — Tax Package (2025)")
print("=" * 60)

jid = create_job("tax_package", "2025-01-01", "2025-12-31", dry_run=True)
if jid:
    job = poll_job(jid, "Tax Package", timeout=120)
    anomalies = get_anomalies(jid) if job["status"] in ("awaiting_approval", "complete") else []
    print_job_summary("Tax Package — 2025", job, anomalies)
    record("tax_package", job, anomalies)

    # Get and save the report
    report_html = get_report_html(jid)
    if report_html:
        path = os.path.join(REPORT_DIR, "tax_package_2025.html")
        with open(path, "w") as f:
            f.write(report_html)
        print(f"  Report saved: {path} ({len(report_html)} chars)")

# ─── STEP 11: Integration Checks ─────────────────────────────────
print("\n" + "=" * 60)
print("STEP 11 — Inter-Agent Integration Checks")
print("=" * 60)

# Check via direct DB
from sqlalchemy import create_engine, text
engine = create_engine("postgresql://localhost:5432/bridgeable_dev")
with engine.connect() as conn:
    # Period locks
    locks = conn.execute(text(
        "SELECT period_start, period_end, is_active FROM period_locks ORDER BY period_start"
    )).fetchall()
    print(f"\n  Period Locks: {len(locks)}")
    for l in locks:
        print(f"    {l[0]} → {l[1]} (active={l[2]})")

    # Statement runs
    runs = conn.execute(text(
        "SELECT id, period_start, period_end, status FROM statement_runs ORDER BY period_start"
    )).fetchall()
    print(f"\n  Statement Runs: {len(runs)}")
    for r in runs:
        print(f"    {r[1]} → {r[2]} (status={r[3]})")

    # Agent jobs audit trail
    jobs = conn.execute(text(
        "SELECT job_type, status, anomaly_count, period_start, period_end "
        "FROM agent_jobs WHERE period_start IS NOT NULL ORDER BY created_at"
    )).fetchall()
    print(f"\n  Agent Jobs Audit Trail: {len(jobs)}")
    for j in jobs:
        print(f"    {j[0]:30s} {j[1]:20s} anomalies={j[2]} ({j[3]} → {j[4]})")

    # Anomaly distribution
    dist = conn.execute(text(
        "SELECT aa.severity, COUNT(*) "
        "FROM agent_anomalies aa "
        "JOIN agent_jobs aj ON aa.agent_job_id = aj.id "
        "WHERE aj.period_start IS NOT NULL "
        "GROUP BY aa.severity ORDER BY aa.severity"
    )).fetchall()
    print(f"\n  Anomaly Distribution:")
    for d in dist:
        print(f"    {d[0]}: {d[1]}")

# ─── STEP 12: Save Report HTMLs ──────────────────────────────────
print("\n" + "=" * 60)
print("STEP 12 — Save Report HTML Files")
print("=" * 60)

report_agents = [
    ("month_end_close_nov", "month_end_close_nov.html"),
    ("ar_collections", "ar_collections.html"),
    ("year_end_close", "year_end_close.html"),
    ("1099_prep", "prep_1099.html"),
    ("annual_budget", "annual_budget.html"),
]

for key, filename in report_agents:
    if key in RESULTS:
        jid = RESULTS[key]["job_id"]
        html = get_report_html(jid)
        if html:
            path = os.path.join(REPORT_DIR, filename)
            with open(path, "w") as f:
                f.write(html)
            print(f"  Saved: {filename} ({len(html)} chars)")
        else:
            print(f"  No report for {key}")

# ─── STEP 13: Final Summary ──────────────────────────────────────
print("\n")
print("╔" + "═" * 58 + "╗")
print("║" + " ACCOUNTING AGENT SUITE — E2E TEST REPORT".center(58) + "║")
print("╠" + "═" * 58 + "╣")
print("║" + f" {'Agent':<30} {'Status':<15} {'Anomalies':>10}" + " ║")
print("╠" + "═" * 58 + "╣")

total_pass = 0
total_fail = 0

display_order = [
    ("ar_collections", "AR Collections"),
    ("unbilled_orders", "Unbilled Orders"),
    ("cash_receipts_matching", "Cash Receipts"),
    ("month_end_close_nov", "Month-End Close (Nov)"),
    ("estimated_tax_prep", "Estimated Tax Prep"),
    ("inventory_reconciliation", "Inventory Reconciliation"),
    ("budget_vs_actual", "Budget vs Actual (1st)"),
    ("annual_budget", "Annual Budget"),
    ("budget_vs_actual_with_budget", "Budget vs Actual (2nd)"),
    ("1099_prep", "1099 Prep"),
    ("year_end_close", "Year-End Close"),
    ("tax_package", "Tax Package"),
]

for key, label in display_order:
    if key in RESULTS:
        r = RESULTS[key]
        status = r["status"]
        passed = status in ("awaiting_approval", "complete")
        symbol = "PASS" if passed else "FAIL"
        if passed:
            total_pass += 1
        else:
            total_fail += 1
        print(f"║ {symbol} {label:<28} {status:<15} {r['anomaly_count']:>10} ║")
    else:
        total_fail += 1
        print(f"║ SKIP {label:<28} {'not run':<15} {'—':>10} ║")

print("╠" + "═" * 58 + "╣")
print(f"║ Total: {total_pass} passed, {total_fail} failed".ljust(59) + "║")
print(f"║ Reports saved: {REPORT_DIR}".ljust(59) + "║")
print("╚" + "═" * 58 + "╝")

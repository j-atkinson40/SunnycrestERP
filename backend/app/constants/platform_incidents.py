"""Error taxonomy constants for the Bridgeable self-repair system.

Defines incident categories, severity levels, resolution tiers,
and tenant health score values used across platform health monitoring.
"""

# ── Incident categories ────────────────────────────────────────────────────

INCIDENT_CATEGORIES: dict[str, dict[str, str]] = {
    "infra": {
        "label": "Infrastructure",
        "default_tier": "auto_fix",
        "description": "DB connection, Railway restart, network",
    },
    "auth": {
        "label": "Authentication",
        "default_tier": "auto_fix",
        "description": "Expired session, bad JWT, SSO failure",
    },
    "background_job": {
        "label": "Background Job",
        "default_tier": "auto_fix",
        "description": "Health score job failed, nightly canary missed",
    },
    "config": {
        "label": "Configuration",
        "default_tier": "auto_remediate",
        "description": "Tenant preset drifted from defaults",
    },
    "migration": {
        "label": "Migration",
        "default_tier": "auto_remediate",
        "description": "Alembic migration did not apply cleanly",
    },
    "data_integrity": {
        "label": "Data Integrity",
        "default_tier": "escalate",
        "description": "FK violation, orphaned record, corrupt state",
    },
    "billing": {
        "label": "Billing",
        "default_tier": "escalate",
        "description": "Payment anomaly, usage spike, subscription error",
    },
    "api_contract": {
        "label": "API Contract",
        "default_tier": "escalate",
        "description": "Frontend/backend schema mismatch after deploy",
    },
}

# ── Severity levels ────────────────────────────────────────────────────────

INCIDENT_SEVERITIES: list[str] = ["low", "medium", "high", "critical"]

# ── Resolution tiers ───────────────────────────────────────────────────────

RESOLUTION_TIERS: list[str] = ["auto_fix", "auto_remediate", "escalate"]

# ── Resolution statuses ────────────────────────────────────────────────────

RESOLUTION_STATUSES: list[str] = [
    "pending",
    "in_progress",
    "resolved",
    "escalated",
    "ignored",
]

# ── Incident detection sources ─────────────────────────────────────────────

INCIDENT_SOURCES: list[str] = [
    "playwright",
    "healthcheck",
    "background_job",
    "manual",
    "sentry",
]

# ── Tenant health score values ─────────────────────────────────────────────

TENANT_HEALTH_SCORES: list[str] = [
    "healthy",
    "watch",
    "degraded",
    "critical",
    "unknown",
]

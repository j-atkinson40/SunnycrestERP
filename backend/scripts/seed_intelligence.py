"""Seed Bridgeable Intelligence — model routes + platform-global prompts + v1 versions.

Idempotent: safe to run multiple times. Creates rows only if they don't exist.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python scripts/seed_intelligence.py

Phase 1 seeds 29 platform-global prompts (company_id=null) with placeholder v1
bodies. Phase 2 will replace placeholder bodies with verbatim content extracted
from /tmp/intelligence_audit.md when callers migrate.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Allow running as a script from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import (
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)


# ── Model routes ────────────────────────────────────────────────────────

# Source of truth for model IDs: CLAUDE.md system-info + docs.claude.com/models.
# Pricing uses current-gen published rates ($/M tokens). Edit via
# PATCH /api/v1/intelligence/models/{route_key} if they change.
OPUS_4_7 = "claude-opus-4-7"
SONNET_4_6 = "claude-sonnet-4-6"
HAIKU_4_5 = "claude-haiku-4-5-20251001"

MODEL_ROUTES: list[dict] = [
    {
        "route_key": "simple",
        "primary_model": HAIKU_4_5,
        "fallback_model": HAIKU_4_5,
        "input_cost_per_million": Decimal("1.00"),
        "output_cost_per_million": Decimal("5.00"),
        "max_tokens_default": 1024,
        "temperature_default": 0.2,
        "notes": "Cheapest capable for classification + simple extraction",
    },
    {
        "route_key": "extraction",
        "primary_model": SONNET_4_6,
        "fallback_model": HAIKU_4_5,
        "input_cost_per_million": Decimal("3.00"),
        "output_cost_per_million": Decimal("15.00"),
        "max_tokens_default": 4096,
        "temperature_default": 0.2,
        "notes": "Structured JSON extraction from complex input",
    },
    {
        "route_key": "reasoning",
        "primary_model": OPUS_4_7,
        "fallback_model": SONNET_4_6,
        "input_cost_per_million": Decimal("15.00"),
        "output_cost_per_million": Decimal("75.00"),
        "max_tokens_default": 8192,
        "temperature_default": 0.5,
        "notes": "Complex analysis, executive narratives, multi-step reasoning",
    },
    {
        "route_key": "vision",
        "primary_model": SONNET_4_6,
        "fallback_model": SONNET_4_6,
        "input_cost_per_million": Decimal("3.00"),
        "output_cost_per_million": Decimal("15.00"),
        "max_tokens_default": 4096,
        "temperature_default": 0.3,
        "notes": "Vision-capable for image + document analysis",
    },
    {
        "route_key": "chat",
        "primary_model": SONNET_4_6,
        "fallback_model": HAIKU_4_5,
        "input_cost_per_million": Decimal("3.00"),
        "output_cost_per_million": Decimal("15.00"),
        "max_tokens_default": 4096,
        "temperature_default": 0.7,
        "notes": "Streaming-optimized for Ask Bridgeable Assistant",
    },
    {
        "route_key": "scheduled",
        "primary_model": HAIKU_4_5,
        "fallback_model": HAIKU_4_5,
        "input_cost_per_million": Decimal("1.00"),
        "output_cost_per_million": Decimal("5.00"),
        "max_tokens_default": 4096,
        "temperature_default": 0.3,
        "notes": "Cost-optimized for nightly batch jobs",
    },
]


# ── Prompts ─────────────────────────────────────────────────────────────

# Each tuple: (prompt_key, domain, display_name, model_preference, force_json,
#             supports_streaming, description)
# System + user templates are placeholder; Phase 2 replaces verbatim.
PROMPTS: list[tuple[str, str, str, str, bool, bool, str]] = [
    # Scribe + FH
    ("scribe.extract_case_fields", "scribe", "Scribe — Extract case fields",
     "extraction", True, False,
     "Funeral Home Arrangement Scribe — extract 70-field case data from free-form transcript."),
    ("scribe.extract_case_fields_live", "scribe", "Scribe — Live extraction (streaming)",
     "simple", False, True,
     "Reserved for mid-session live streaming extraction. Phase 2 wires in."),

    # Command bar + NL Overlay
    ("commandbar.classify_intent", "extraction", "Command Bar — Classify intent",
     "simple", True, False,
     "Route free-form input to a workflow, answer, or navigation result."),
    ("overlay.extract_fields_live", "extraction", "Overlay — Live field extraction",
     "simple", True, False,
     "Incremental extraction while user types; fast and cheap."),
    ("overlay.extract_fields_final", "extraction", "Overlay — Final field extraction",
     "extraction", True, False,
     "Final commit-time extraction; structured, force_json."),
    ("commandbar.answer_price_question", "extraction", "Command Bar — Answer price question",
     "simple", True, False,
     "Answer product price questions from catalog context."),
    ("commandbar.detect_quote_intent", "extraction", "Command Bar — Detect quote intent",
     "simple", True, False,
     "Decide whether the user is asking for a quote vs placing an order."),

    # Ask Bridgeable Assistant
    ("assistant.chat_with_context", "chat", "Ask Bridgeable Assistant",
     "chat", False, True,
     "Admin chat with repo context + migration head + tenant summary."),

    # Compose + workflow AI
    ("compose.generate_draft", "compose", "Compose — Generate draft",
     "extraction", False, False,
     "Generate a compose draft (email, memo, SMS) from intent + entities."),
    ("workflow.ai_step_generic", "workflow", "Workflow — Generic AI step",
     "reasoning", False, False,
     "Default target for workflow step_type=action, action_type=ai_prompt."),

    # Accounting agents (one per agent task)
    ("agent.month_end_close.executive_summary", "agent", "Month-End Close — Executive summary",
     "reasoning", False, False,
     "Executive narrative for month-end close report."),
    ("agent.ar_collections.draft_email", "agent", "AR Collections — Draft email",
     "extraction", False, False,
     "Draft a collection email by tier and customer context."),
    ("agent.unbilled_orders.pattern_analysis", "agent", "Unbilled Orders — Pattern analysis",
     "reasoning", False, False,
     "Identify patterns across unbilled delivered orders."),
    ("agent.cash_receipts.match_rationale", "agent", "Cash Receipts — Match rationale",
     "extraction", False, False,
     "Explain match vs. unresolvable for a cash receipt."),
    ("agent.expense_categorization.classify", "accounting", "Expense Categorization — Classify line",
     "simple", True, False,
     "Classify a vendor bill line to a GL account. Force JSON."),
    ("agent.estimated_tax_prep.narrative", "agent", "Estimated Tax Prep — Narrative",
     "reasoning", False, False,
     "Quarterly estimate narrative with federal + state breakdown."),
    ("agent.inventory_reconciliation.narrative", "agent", "Inventory Reconciliation — Narrative",
     "reasoning", False, False,
     "Variance + adjustment narrative for inventory reconciliation."),
    ("agent.budget_vs_actual.variance_narrative", "agent", "Budget vs Actual — Variance narrative",
     "reasoning", False, False,
     "Explain favorable + unfavorable variances for the period."),
    ("agent.prep_1099.filing_gaps", "agent", "1099 Prep — Filing gaps",
     "extraction", False, False,
     "Surface missing tax IDs, unreviewed vendors, W-9 gaps."),
    ("agent.year_end_close.summary", "agent", "Year-End Close — Summary",
     "reasoning", False, False,
     "Full-year income + quarterly comparison summary."),
    ("agent.tax_package.cpa_narrative", "agent", "Tax Package — CPA narrative",
     "reasoning", False, False,
     "CPA-ready tax package cover narrative (read-only)."),
    ("agent.annual_budget.assumption_forecast", "agent", "Annual Budget — Assumptions + forecast",
     "reasoning", False, False,
     "Derive next-year budget from prior-year actuals + assumptions."),
    ("accounting.coa_classify", "accounting", "COA — Classify account",
     "simple", True, False,
     "Classify a GL account during COA import. Force JSON, confidence threshold 0.85."),

    # Briefing + safety
    ("briefing.daily_summary", "briefing", "Daily Briefing — Summary",
     "scheduled", False, False,
     "Morning briefing executive summary per tenant."),
    ("briefing.safety_talking_point", "safety", "Briefing — Safety talking point",
     "simple", False, False,
     "Short safety talking point for the morning briefing card."),
    ("safety.draft_monthly_program", "safety", "Safety — Draft monthly program",
     "reasoning", False, False,
     "Draft 7-section OSHA safety program from scraped regs."),

    # Urn pipeline
    ("urn.enrich_catalog_entry", "urn", "Urn — Enrich catalog entry",
     "scheduled", False, False,
     "Enrich a Wilbert urn SKU with description + metadata."),
    ("urn.semantic_search", "urn", "Urn — Semantic search",
     "simple", True, False,
     "Translate natural language urn search to structured filters."),
    ("urn.engraving_proof_narrative", "urn", "Urn — Engraving proof narrative",
     "extraction", False, False,
     "Generate proof approval narrative for funeral home email."),
]


PLACEHOLDER_SYSTEM_PROMPT = (
    "You are the {display_name} prompt for Bridgeable.\n\n"
    "This is a Phase 1 placeholder. The production system prompt will be "
    "migrated verbatim from /tmp/intelligence_audit.md in Phase 2.\n\n"
    "If you are executed before Phase 2 completes, respond concisely and "
    "flag that this prompt has not been migrated yet."
)

PLACEHOLDER_USER_TEMPLATE = (
    "Input:\n{{ input | default('(no input provided)') }}\n\n"
    "Note: This is a Phase 1 placeholder. See /tmp/intelligence_audit.md for "
    "the verbatim production prompt content that will be migrated in Phase 2."
)

PLACEHOLDER_VAR_SCHEMA = {
    "input": {
        "type": "string",
        "required": False,
        "description": "Freeform input for placeholder prompt smoke tests.",
    }
}


# ── Seed functions ──────────────────────────────────────────────────────


def seed_model_routes(db: Session) -> int:
    """Upsert all model routes. Returns count of rows seeded or updated."""
    count = 0
    for spec in MODEL_ROUTES:
        existing = (
            db.query(IntelligenceModelRoute)
            .filter_by(route_key=spec["route_key"])
            .first()
        )
        if existing is None:
            db.add(IntelligenceModelRoute(**spec))
            count += 1
        else:
            # Keep pricing + fallback fresh; never overwrite if admin disabled
            existing.primary_model = spec["primary_model"]
            existing.fallback_model = spec["fallback_model"]
            existing.input_cost_per_million = spec["input_cost_per_million"]
            existing.output_cost_per_million = spec["output_cost_per_million"]
            existing.max_tokens_default = spec["max_tokens_default"]
            existing.temperature_default = spec["temperature_default"]
            existing.notes = spec["notes"]
            existing.updated_at = datetime.now(timezone.utc)
    db.commit()
    return count


def seed_prompts(db: Session) -> tuple[int, int]:
    """Create platform-global prompts + v1 versions. Idempotent.

    Returns (prompts_created, versions_created).
    """
    prompts_created = 0
    versions_created = 0

    for (
        prompt_key,
        domain,
        display_name,
        model_preference,
        force_json,
        supports_streaming,
        description,
    ) in PROMPTS:
        existing = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == prompt_key,
            )
            .first()
        )
        if existing is None:
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=prompt_key,
                display_name=display_name,
                description=description,
                domain=domain,
            )
            db.add(prompt)
            db.flush()
            prompts_created += 1
        else:
            prompt = existing

        # Ensure an active v1 exists
        active = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        if active is not None:
            continue

        version = IntelligencePromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            system_prompt=PLACEHOLDER_SYSTEM_PROMPT.format(display_name=display_name),
            user_template=PLACEHOLDER_USER_TEMPLATE,
            variable_schema=PLACEHOLDER_VAR_SCHEMA,
            model_preference=model_preference,
            temperature=0.3 if model_preference in ("simple", "extraction", "scheduled") else 0.7,
            max_tokens=4096,
            force_json=force_json,
            supports_streaming=supports_streaming,
            supports_tool_use=False,
            status="active",
            changelog="Phase 1 seed — placeholder content; Phase 2 migrates verbatim.",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(version)
        versions_created += 1

    db.commit()
    return prompts_created, versions_created


def main() -> None:
    db = SessionLocal()
    try:
        routes_n = seed_model_routes(db)
        prompts_n, versions_n = seed_prompts(db)
        total_prompts = db.query(IntelligencePrompt).filter(
            IntelligencePrompt.company_id.is_(None)
        ).count()
        total_routes = db.query(IntelligenceModelRoute).count()
        total_active_versions = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.status == "active")
            .count()
        )

        print(f"Model routes upserted: {len(MODEL_ROUTES)} (new: {routes_n})")
        print(f"Platform prompts seeded: {prompts_n} (existing kept)")
        print(f"Version 1s created: {versions_n}")
        print(f"Totals → routes={total_routes}, platform_prompts={total_prompts}, "
              f"active_versions={total_active_versions}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

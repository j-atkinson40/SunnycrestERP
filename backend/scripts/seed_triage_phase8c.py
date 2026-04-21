"""Seed Workflow Arc Phase 8c triage Intelligence prompts.

Three prompts, one per 8c migration:
  - triage.month_end_close_context_question
  - triage.ar_collections_context_question
  - triage.expense_categorization_context_question

Uses Option A idempotent seed pattern (same as Phase 6 briefings,
Phase 8b cash receipts):
  - No existing prompt              → create + v1 active
  - Exactly 1 version matching      → no-op
  - Exactly 1 version differing     → deactivate v1 + create v2
  - Multiple versions (admin custom)→ skip with warning

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_triage_phase8c.py
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


logger = logging.getLogger(__name__)


_VARIABLE_SCHEMA = {
    "item_json": {"type": "string", "required": True},
    "user_question": {"type": "string", "required": True},
    "tenant_context": {"type": "string", "required": True},
    "related_entities_json": {"type": "string", "required": False},
}
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number"},
        "sources": {"type": "array"},
    },
    "required": ["answer", "confidence"],
}


@dataclass(frozen=True)
class PromptSpec:
    prompt_key: str
    display_name: str
    description: str
    system_prompt: str


_USER_TEMPLATE = "{{user_question}}"


_PROMPTS: list[PromptSpec] = [
    PromptSpec(
        prompt_key="triage.month_end_close_context_question",
        display_name="Triage — Month-End Close context question",
        description=(
            "Answer user questions about a month-end-close run under "
            "approval triage. Grounds in the AgentJob's executive "
            "summary + step outputs + anomalies + flagged customers."
        ),
        system_prompt=(
            "You help an accounting user decide whether to approve or "
            "reject a month-end-close run. Ground every answer in the "
            "provided agent-job data + related entities. The related "
            "entities include: the AgentJob with executive summary "
            "(total_revenue, total_ar, collection_rate_pct, prior "
            "period comparison), up to 5 flagged customers with their "
            "anomaly types, and the prior completed month-end-close "
            "for comparison.\n\n"
            "Answer concretely. When asked about a specific customer "
            "or anomaly, cite the customer_id + anomaly_type + "
            "severity. If the data doesn't support an answer, say "
            "so; do NOT hallucinate.\n\n"
            "Return JSON with `answer` (string), `confidence` "
            "(0.0-1.0), `sources` (array of record references, each "
            "like `{\"entity_type\": \"customer\", \"entity_id\": "
            "\"...\"}`).\n\n"
            "Agent job: {{item_json}}\n"
            "Related entities: {{related_entities_json}}\n"
            "Tenant: {{tenant_context}}"
        ),
    ),
    PromptSpec(
        prompt_key="triage.ar_collections_context_question",
        display_name="Triage — AR Collections context question",
        description=(
            "Answer user questions about a drafted collection email "
            "under triage. Grounds in the customer + their open "
            "invoices + past collection-email deliveries."
        ),
        system_prompt=(
            "You help an accounting user decide whether to dispatch a "
            "drafted AR-collections email. Ground every answer in the "
            "payment-history data provided. Related entities include: "
            "the Customer row (account_status, billing_email), up to "
            "5 open invoices ranked by age, and up to 3 past "
            "collection emails sent to this customer.\n\n"
            "Answer concretely. When discussing the drafted email's "
            "tone, reference the customer's specific tier "
            "(FOLLOW_UP / ESCALATE / CRITICAL) and why they landed "
            "there. If the data doesn't support an answer, say so.\n\n"
            "Return JSON with `answer`, `confidence`, `sources`.\n\n"
            "Triage item: {{item_json}}\n"
            "Related entities: {{related_entities_json}}\n"
            "Tenant: {{tenant_context}}"
        ),
    ),
    PromptSpec(
        prompt_key="triage.expense_categorization_context_question",
        display_name="Triage — Expense Categorization context question",
        description=(
            "Answer user questions about a vendor-bill-line "
            "categorization decision under triage. Grounds in the "
            "line + parent bill + vendor + past categorized lines for "
            "the same vendor (pattern-matching aid)."
        ),
        system_prompt=(
            "You help an accounting user decide how to categorize a "
            "vendor-bill line. Ground every answer in the line data + "
            "vendor history. Related entities include: the "
            "VendorBillLine, the parent VendorBill, the Vendor, and "
            "up to 3 past categorized lines for the same vendor.\n\n"
            "When suggesting a category, cite the specific pattern "
            "from vendor history (e.g., 'this vendor's last 3 lines "
            "were all categorized as `rent`'). If the AI's proposed "
            "category is inconsistent with vendor history, flag that. "
            "If the data doesn't support an answer, say so.\n\n"
            "Return JSON with `answer`, `confidence`, `sources`.\n\n"
            "Triage item: {{item_json}}\n"
            "Related entities: {{related_entities_json}}\n"
            "Tenant: {{tenant_context}}"
        ),
    ),
]


def _matches(version: IntelligencePromptVersion, spec: PromptSpec) -> bool:
    return (
        version.system_prompt == spec.system_prompt
        and version.user_template == _USER_TEMPLATE
    )


def _create_version(
    db: Session,
    prompt: IntelligencePrompt,
    spec: PromptSpec,
    version_number: int,
    changelog: str,
) -> IntelligencePromptVersion:
    version = IntelligencePromptVersion(
        prompt_id=prompt.id,
        version_number=version_number,
        system_prompt=spec.system_prompt,
        user_template=_USER_TEMPLATE,
        variable_schema=_VARIABLE_SCHEMA,
        response_schema=_RESPONSE_SCHEMA,
        model_preference="simple",
        temperature=0.3,
        max_tokens=1024,
        force_json=True,
        supports_streaming=False,
        supports_tool_use=False,
        status="active",
        changelog=changelog,
        activated_at=datetime.now(timezone.utc),
    )
    db.add(version)
    return version


def seed_one(db: Session, spec: PromptSpec) -> dict[str, int]:
    stats = {"created": 0, "updated": 0, "noop": 0, "skipped_custom": 0}

    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == spec.prompt_key,
        )
        .first()
    )
    if prompt is None:
        prompt = IntelligencePrompt(
            company_id=None,
            prompt_key=spec.prompt_key,
            display_name=spec.display_name,
            description=spec.description,
            domain="triage",
        )
        db.add(prompt)
        db.flush()
        _create_version(
            db, prompt, spec, version_number=1,
            changelog=f"Phase 8c seed — {spec.prompt_key}.",
        )
        db.commit()
        stats["created"] = 1
        return stats

    versions = (
        db.query(IntelligencePromptVersion)
        .filter(IntelligencePromptVersion.prompt_id == prompt.id)
        .all()
    )
    if len(versions) > 1:
        logger.warning(
            "Prompt %s has %d versions — admin customization in flight. "
            "Skipping platform update.",
            spec.prompt_key,
            len(versions),
        )
        stats["skipped_custom"] = 1
        return stats
    if len(versions) == 1:
        existing = versions[0]
        if _matches(existing, spec):
            stats["noop"] = 1
            return stats
        existing.status = "retired"
        db.flush()
        next_version_number = (existing.version_number or 1) + 1
        _create_version(
            db, prompt, spec, version_number=next_version_number,
            changelog=(
                f"Phase 8c re-seed — platform update to "
                f"{spec.prompt_key}."
            ),
        )
        db.commit()
        stats["updated"] = 1
        return stats

    _create_version(
        db, prompt, spec, version_number=1,
        changelog=(
            f"Phase 8c seed — adding v1 to existing empty prompt "
            f"{spec.prompt_key}."
        ),
    )
    db.commit()
    stats["created"] = 1
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    totals = {"created": 0, "updated": 0, "noop": 0, "skipped_custom": 0}
    db = SessionLocal()
    try:
        for spec in _PROMPTS:
            s = seed_one(db, spec)
            for k, v in s.items():
                totals[k] = totals.get(k, 0) + v
            logger.info(
                "[seed-triage-phase8c] %s → %s", spec.prompt_key, s
            )
        logger.info("[seed-triage-phase8c] totals: %s", totals)
    finally:
        db.close()


if __name__ == "__main__":
    main()

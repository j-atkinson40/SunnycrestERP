"""Seed Workflow Arc Phase 8b triage Intelligence prompt.

Adds `triage.cash_receipts_context_question` — the AI question prompt
for the cash receipts matching triage queue.

Uses Option A idempotent seed pattern (same as Phase 6 briefings):

  - No existing prompt              → create + v1 active
  - Exactly 1 version matching      → no-op
  - Exactly 1 version differing     → deactivate v1 + create v2
  - Multiple versions (admin custom)→ skip with warning

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_triage_phase8b.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


logger = logging.getLogger(__name__)


_PROMPT_KEY = "triage.cash_receipts_context_question"
_DISPLAY_NAME = "Triage — Cash Receipts Matching context question"
_DESCRIPTION = (
    "Answer user questions about an unresolved cash receipt match. "
    "Grounds in the payment record + candidate invoices + customer "
    "payment history."
)

_SYSTEM_PROMPT = (
    "You help an accounting user decide how to match an incoming "
    "customer payment to an open invoice. Ground every answer in the "
    "payment + related entity data provided. The related entities "
    "include: the CustomerPayment row, the paying Customer, up to 5 "
    "candidate open invoices ranked by how close their balance is to "
    "the payment amount, and up to 3 past applied payment/invoice "
    "pairs for this same customer (pattern-matching aid).\n\n"
    "Answer the user's question concretely. When suggesting an "
    "invoice match, cite the specific invoice number + balance. When "
    "flagging a split, cite the invoices + amounts. If the data "
    "doesn't support an answer, say so; do NOT hallucinate.\n\n"
    "Return JSON with `answer` (string), `confidence` (0.0-1.0), "
    "`sources` (array of record references — e.g. "
    "`{\"entity_type\": \"invoice\", \"entity_id\": \"...\"}` — "
    "that backs each claim in your answer).\n\n"
    "Payment + anomaly: {{item_json}}\n"
    "Related entities: {{related_entities_json}}\n"
    "Tenant: {{tenant_context}}"
)
_USER_TEMPLATE = "{{user_question}}"


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


def _matches(version: IntelligencePromptVersion) -> bool:
    return (
        version.system_prompt == _SYSTEM_PROMPT
        and version.user_template == _USER_TEMPLATE
    )


def _create_version(
    db: Session, prompt: IntelligencePrompt, version_number: int, changelog: str
) -> IntelligencePromptVersion:
    version = IntelligencePromptVersion(
        prompt_id=prompt.id,
        version_number=version_number,
        system_prompt=_SYSTEM_PROMPT,
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


def seed_prompt(db: Session) -> dict[str, int]:
    """Returns counts: {created, updated, noop, skipped_custom}."""
    stats = {"created": 0, "updated": 0, "noop": 0, "skipped_custom": 0}

    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == _PROMPT_KEY,
        )
        .first()
    )
    if prompt is None:
        # Fresh install — create prompt + v1
        prompt = IntelligencePrompt(
            company_id=None,
            prompt_key=_PROMPT_KEY,
            display_name=_DISPLAY_NAME,
            description=_DESCRIPTION,
            domain="triage",
        )
        db.add(prompt)
        db.flush()
        _create_version(
            db, prompt, version_number=1,
            changelog="Phase 8b seed — Cash Receipts Matching AI context question.",
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
            "Skipping platform update. Reconcile via Intelligence admin UI.",
            _PROMPT_KEY,
            len(versions),
        )
        stats["skipped_custom"] = 1
        return stats

    if len(versions) == 1:
        existing = versions[0]
        if _matches(existing):
            stats["noop"] = 1
            return stats
        # Content drifted — deactivate v1, create v2
        existing.status = "retired"
        db.flush()
        next_version_number = (existing.version_number or 1) + 1
        _create_version(
            db, prompt, version_number=next_version_number,
            changelog=(
                "Phase 8b re-seed — platform update. Previous version "
                "deactivated (no admin customization detected)."
            ),
        )
        db.commit()
        stats["updated"] = 1
        return stats

    # No versions at all (odd state — prompt without versions)
    _create_version(
        db, prompt, version_number=1,
        changelog="Phase 8b seed — adding v1 to existing prompt without a version.",
    )
    db.commit()
    stats["created"] = 1
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        stats = seed_prompt(db)
        logger.info("[seed-triage-phase8b] %s", stats)
    finally:
        db.close()


if __name__ == "__main__":
    main()

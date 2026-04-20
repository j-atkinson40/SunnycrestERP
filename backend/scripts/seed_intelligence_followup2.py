"""Seed follow-up 2 — vertical-aware v2 of the triage Q&A prompts.

Re-seeds `triage.task_context_question` and
`triage.ss_cert_context_question` with a VERTICAL-APPROPRIATE
TERMINOLOGY block so Claude's answers use the right vocabulary per
tenant (cases vs orders vs burials vs cremations). Follows Phase 6's
Option A idempotent pattern (diff-check + v1→v2 bump):

  - No existing prompt row       → create prompt + v1 active.
  - Exactly 1 version + content matches current seed → no-op.
  - Exactly 1 version + content DIFFERS → deactivate v1, create v2
    active with the new body. This is the platform-update path: a
    fresh deploy on top of a Phase 5 install.
  - Multiple versions exist      → skip with warning log. Admin has
    already customized this prompt; don't force-overwrite. Manual
    reconciliation via the Intelligence admin UI.

Variables added to v2 (all optional so the v1 call sites continue
working during the transition):
  - `vertical`          (manufacturing / funeral_home / cemetery /
                         crematory — branches the terminology block)
  - `user_role`         (role slug for framing)
  - `queue_name`        (for the framing line)
  - `queue_description` (same)
  - `item_type`         (entity type label)

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_intelligence_followup2.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import (
    IntelligencePrompt,
    IntelligencePromptVersion,
)

logger = logging.getLogger(__name__)


# ── Shared schemas ──────────────────────────────────────────────────


_VAR_SCHEMA = {
    # v1 variables (kept for back-compat — every caller already sends
    # these, the v2 prompt body still references them).
    "item_json": {"type": "string", "required": True},
    "user_question": {"type": "string", "required": True},
    "tenant_context": {"type": "string", "required": True},
    "related_entities_json": {"type": "string", "required": False},
    # v2 additions — all optional so v1 code paths (none today, but
    # defensively) don't fail validation. The vertical + queue vars
    # drive the Jinja terminology + framing blocks.
    "vertical": {"type": "string", "required": False},
    "user_role": {"type": "string", "required": False},
    "queue_name": {"type": "string", "required": False},
    "queue_description": {"type": "string", "required": False},
    "item_type": {"type": "string", "required": False},
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


_VERTICAL_BLOCK = """

VERTICAL-APPROPRIATE TERMINOLOGY (CRITICAL — do NOT mix terminology across verticals):
The user's business vertical is: {{ vertical }}
Use ONLY terminology appropriate to this vertical:
{% if vertical == "manufacturing" %}- orders, work orders, production, deliveries, invoices, quotes, customers
- Do NOT use: cases, arrangements, deceased, families, interments, burials, cremations, certificates
{% elif vertical == "funeral_home" %}- cases, arrangements, services, families, decedents, funeral homes
- Do NOT use: orders, work orders, production, pours, deliveries
{% elif vertical == "cemetery" %}- burials, plots, interments, services, families
- Do NOT use: orders, work orders, production, cases, arrangements
{% elif vertical == "crematory" %}- cremations, services, certificates, families, decedents
- Do NOT use: orders, work orders, production, pours, cases, arrangements, burials, plots
{% else %}- This tenant's vertical is unset; use generic business language (records, items).
{% endif %}
"""


_TASK_SYSTEM_PROMPT = (
    "You answer questions about a task under triage. Ground every "
    "answer in the task record provided. If the question is outside "
    "the task's context or related entities, say so; do NOT "
    "hallucinate. Return JSON with `answer`, `confidence` (0.0-1.0), "
    "`sources` (array of record refs you used, each with "
    "`entity_type`, `entity_id`, `display_label`, optional "
    "`snippet`).\n\n"
    "Task: {{item_json}}\n"
    "Related entities: {{related_entities_json}}\n"
    "Tenant: {{tenant_context}}"
    + _VERTICAL_BLOCK +
    "\nQueue: {{ queue_name }} — {{ queue_description }}\n"
    "Role: {{ user_role }}\n"
    "Keep the answer concise — 2-4 sentences unless the question "
    "genuinely requires more detail."
)


_SS_CERT_SYSTEM_PROMPT = (
    "You answer questions about a social service certificate under "
    "approval triage. Ground answers in the certificate record + "
    "related order + past certificates. Do NOT hallucinate. Return "
    "JSON with `answer`, `confidence` (0.0-1.0), `sources` (array of "
    "record refs, each with `entity_type`, `entity_id`, "
    "`display_label`, optional `snippet`).\n\n"
    "Certificate: {{item_json}}\n"
    "Related entities: {{related_entities_json}}\n"
    "Tenant: {{tenant_context}}"
    + _VERTICAL_BLOCK +
    "\nQueue: {{ queue_name }} — {{ queue_description }}\n"
    "Role: {{ user_role }}\n"
    "Keep the answer concise — 2-4 sentences unless the question "
    "genuinely requires more detail."
)


_USER_TEMPLATE = "{{user_question}}"


_PROMPTS = [
    {
        "prompt_key": "triage.task_context_question",
        "display_name": "Triage — Task context question",
        "description": (
            "Answer user questions about a task being triaged. "
            "Grounds in the task record + related entities. "
            "Vertical-aware terminology (v2 adds the vertical block)."
        ),
        "domain": "triage",
        "system_prompt": _TASK_SYSTEM_PROMPT,
        "user_template": _USER_TEMPLATE,
        "changelog_update": (
            "Platform update (follow-up 2) — vertical-aware "
            "terminology block + queue framing added."
        ),
    },
    {
        "prompt_key": "triage.ss_cert_context_question",
        "display_name": "Triage — SS Certificate context question",
        "description": (
            "Answer user questions about a social service certificate "
            "under triage. Grounds in the certificate record + related "
            "order + past certificates. Vertical-aware terminology "
            "(v2 adds the vertical block)."
        ),
        "domain": "triage",
        "system_prompt": _SS_CERT_SYSTEM_PROMPT,
        "user_template": _USER_TEMPLATE,
        "changelog_update": (
            "Platform update (follow-up 2) — vertical-aware "
            "terminology block + queue framing added."
        ),
    },
]


def _seed_prompts(db: Session) -> dict[str, int]:
    created_prompts = 0
    created_versions = 0
    skipped_customized = 0
    noop_matched = 0
    bumped_to_v2 = 0

    for spec in _PROMPTS:
        existing = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == spec["prompt_key"],
            )
            .first()
        )
        if existing is None:
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=spec["prompt_key"],
                display_name=spec["display_name"],
                description=spec["description"],
                domain=spec["domain"],
            )
            db.add(prompt)
            db.flush()
            created_prompts += 1
            version = IntelligencePromptVersion(
                prompt_id=prompt.id,
                version_number=1,
                system_prompt=spec["system_prompt"],
                user_template=spec["user_template"],
                variable_schema=_VAR_SCHEMA,
                response_schema=_RESPONSE_SCHEMA,
                model_preference="simple",
                temperature=0.3,
                max_tokens=1024,
                force_json=True,
                supports_streaming=False,
                supports_tool_use=False,
                status="active",
                changelog=(
                    "Follow-up 2 seed — triage Q&A with vertical-aware "
                    "terminology."
                ),
                activated_at=datetime.now(timezone.utc),
            )
            db.add(version)
            created_versions += 1
            continue

        versions = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.prompt_id == existing.id)
            .order_by(IntelligencePromptVersion.version_number.asc())
            .all()
        )
        if len(versions) > 1:
            # Admin has customized — do not force-overwrite.
            logger.warning(
                "Prompt %s has %d versions; skipping platform update. "
                "Reconcile manually via the Intelligence admin UI.",
                spec["prompt_key"],
                len(versions),
            )
            skipped_customized += 1
            continue

        if len(versions) == 1:
            v1 = versions[0]
            if (
                v1.system_prompt == spec["system_prompt"]
                and v1.user_template == spec["user_template"]
            ):
                noop_matched += 1
                continue
            # Platform update — deactivate v1, create v2 active.
            v1.status = "retired"
            v2 = IntelligencePromptVersion(
                prompt_id=existing.id,
                version_number=v1.version_number + 1,
                system_prompt=spec["system_prompt"],
                user_template=spec["user_template"],
                variable_schema=_VAR_SCHEMA,
                response_schema=_RESPONSE_SCHEMA,
                model_preference="simple",
                temperature=0.3,
                max_tokens=1024,
                force_json=True,
                supports_streaming=False,
                supports_tool_use=False,
                status="active",
                changelog=spec["changelog_update"],
                activated_at=datetime.now(timezone.utc),
            )
            db.add(v2)
            # Also refresh the parent description so admin UI reflects
            # the updated summary.
            existing.description = spec["description"]
            created_versions += 1
            bumped_to_v2 += 1
            continue

        # Prompt row exists but no versions — create v1.
        v1 = IntelligencePromptVersion(
            prompt_id=existing.id,
            version_number=1,
            system_prompt=spec["system_prompt"],
            user_template=spec["user_template"],
            variable_schema=_VAR_SCHEMA,
            response_schema=_RESPONSE_SCHEMA,
            model_preference="simple",
            temperature=0.3,
            max_tokens=1024,
            force_json=True,
            supports_streaming=False,
            supports_tool_use=False,
            status="active",
            changelog="Follow-up 2 seed — triage Q&A (orphan prompt).",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v1)
        created_versions += 1

    db.commit()
    return {
        "created_prompts": created_prompts,
        "created_versions": created_versions,
        "bumped_to_v2": bumped_to_v2,
        "noop_matched": noop_matched,
        "skipped_customized": skipped_customized,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = SessionLocal()
    try:
        stats = _seed_prompts(db)
    finally:
        db.close()
    print(
        "Follow-up 2 prompt seed:",
        " ".join(f"{k}={v}" for k, v in stats.items()),
    )


if __name__ == "__main__":
    main()

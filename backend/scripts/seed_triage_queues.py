"""Seed Phase 5 triage Intelligence prompts + validate platform configs.

Platform-default queue configs live in-code
(`app.services.triage.platform_defaults`) and auto-register at
import time. This script exists to:

  1. Verify the in-code platform configs load + parse correctly.
  2. Seed the two Intelligence prompts used by the queues' AI
     question features.

Re-running is safe — both steps are idempotent.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_triage_queues.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion
from app.services.triage import list_platform_configs


# ── Intelligence prompt seed specs ──────────────────────────────────


_SHARED_VAR_SCHEMA = {
    "item_json": {"type": "string", "required": True},
    "user_question": {"type": "string", "required": True},
    "tenant_context": {"type": "string", "required": True},
    "related_entities_json": {"type": "string", "required": False},
}
_SHARED_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number"},
        "sources": {"type": "array"},
    },
    "required": ["answer", "confidence"],
}


_PROMPTS = [
    {
        "prompt_key": "triage.task_context_question",
        "display_name": "Triage — Task context question",
        "description": (
            "Answer user questions about a task being triaged. "
            "Grounds in the task record + related entities."
        ),
        "system_prompt": (
            "You answer questions about a task under triage. Ground "
            "every answer in the task record provided. If the "
            "question is outside the task's context or related "
            "entities, say so; do NOT hallucinate. Return JSON with "
            "`answer`, `confidence` (0.0-1.0), `sources` (array of "
            "record refs you used).\n\n"
            "Task: {{item_json}}\n"
            "Related entities: {{related_entities_json}}\n"
            "Tenant: {{tenant_context}}"
        ),
        "user_template": "{{user_question}}",
    },
    {
        "prompt_key": "triage.ss_cert_context_question",
        "display_name": "Triage — SS Certificate context question",
        "description": (
            "Answer user questions about a social service certificate "
            "under triage. Grounds in the certificate record + related "
            "order + delivery context."
        ),
        "system_prompt": (
            "You answer questions about a social service certificate "
            "under approval triage. Ground answers in the certificate "
            "record + related order. Do NOT hallucinate. Return JSON "
            "with `answer`, `confidence`, `sources`.\n\n"
            "Certificate: {{item_json}}\n"
            "Related entities: {{related_entities_json}}\n"
            "Tenant: {{tenant_context}}"
        ),
        "user_template": "{{user_question}}",
    },
]


def _seed_prompts(db: Session) -> int:
    created = 0
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
                domain="triage",
            )
            db.add(prompt)
            db.flush()
            created += 1
        else:
            prompt = existing
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
            system_prompt=spec["system_prompt"],
            user_template=spec["user_template"],
            variable_schema=_SHARED_VAR_SCHEMA,
            response_schema=_SHARED_RESPONSE_SCHEMA,
            model_preference="simple",
            temperature=0.3,
            max_tokens=1024,
            force_json=True,
            supports_streaming=False,
            supports_tool_use=False,
            status="active",
            changelog="Phase 5 seed — Triage AI context question.",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(version)
    db.commit()
    return created


def main() -> None:
    # Step 1 — validate platform configs loaded
    configs = list_platform_configs()
    print(
        f"[seed-triage-queues] platform configs loaded: "
        f"{[c.queue_id for c in configs]}"
    )
    if not configs:
        raise SystemExit(
            "No platform configs registered. Did "
            "`app.services.triage.platform_defaults` load correctly?"
        )

    # Step 2 — seed the Intelligence prompts
    db = SessionLocal()
    try:
        prompts_created = _seed_prompts(db)
        print(f"[seed-triage-queues] prompts_created={prompts_created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

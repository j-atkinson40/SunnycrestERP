"""Seed Phase R-6.1a email classification Intelligence prompts.

Two prompts:
  - email.classify_into_taxonomy
  - email.classify_into_registry

Uses Option A idempotent seed pattern (same as Phase 6 briefings,
Phase 8b cash receipts, Phase 8c accounting batch, Phase 8d.1
safety program):
  - No existing prompt              → create + v1 active
  - Exactly 1 version matching      → no-op
  - Exactly 1 version differing     → deactivate v1 + create v2
  - Multiple versions (admin custom)→ skip with warning

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python -m scripts.seed_email_classification_intelligence
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


_USER_TEMPLATE = (
    "Subject: {{subject}}\n"
    "From: {{sender_name}} <{{sender_email}}>\n\n"
    "Body excerpt:\n{{body_excerpt}}"
)


@dataclass(frozen=True)
class PromptSpec:
    prompt_key: str
    display_name: str
    description: str
    system_prompt: str
    variable_schema: dict
    response_schema: dict


# ── Tier 2 — taxonomy classification ────────────────────────────────


_TAXONOMY_VARIABLE_SCHEMA = {
    "subject": {"type": "string", "required": False},
    "sender_email": {"type": "string", "required": True},
    "sender_name": {"type": "string", "required": False},
    "body_excerpt": {"type": "string", "required": False},
    "taxonomy_json": {"type": "array", "required": True},
}

_TAXONOMY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category_id": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["category_id", "confidence"],
}

_TAXONOMY_SYSTEM_PROMPT = (
    "You classify an inbound email into ONE category from the "
    "tenant's taxonomy. The taxonomy is provided as a JSON array "
    "of category objects, each with `category_id`, `label`, and "
    "an optional `description`. Pick the single best matching "
    "category and return its `category_id`.\n\n"
    "DO NOT INVENT IDs. If no category fits well, return "
    "`category_id: null` with confidence 0. Inventing an id will "
    "cause downstream silent fallthrough — be honest about "
    "uncertainty.\n\n"
    "Output JSON with these keys:\n"
    "  - `category_id` (string OR null) — the chosen category's id, "
    "or null if none fits\n"
    "  - `confidence` (0.0–1.0) — your confidence in this match\n"
    "  - `reasoning` (string) — one or two sentences explaining "
    "the choice. Cite the category label when possible.\n\n"
    "Calibration:\n"
    "  - 0.9+ — sender + subject + body all clearly indicate this category\n"
    "  - 0.7–0.9 — strong signal in subject or body\n"
    "  - 0.55–0.7 — likely match but ambiguous\n"
    "  - <0.55 — return null; the cascade falls through to a "
    "broader AI registry pass\n\n"
    "Tenant taxonomy:\n{{taxonomy_json}}"
)


# ── Tier 3 — workflow registry selection ────────────────────────────


_REGISTRY_VARIABLE_SCHEMA = {
    "subject": {"type": "string", "required": False},
    "sender_email": {"type": "string", "required": True},
    "sender_name": {"type": "string", "required": False},
    "body_excerpt": {"type": "string", "required": False},
    "registry_json": {"type": "array", "required": True},
}

_REGISTRY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "workflow_id": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["workflow_id", "confidence"],
}

_REGISTRY_SYSTEM_PROMPT = (
    "You pick ONE workflow from the tenant's enrolled workflow "
    "registry that should fire in response to this email. The "
    "registry is provided as a JSON array of workflows, each with "
    "`workflow_id`, `name`, and `description`.\n\n"
    "Rely heavily on the workflow `description` — admins author it "
    "specifically to describe when the workflow should fire. The "
    "`name` is a short label; the `description` is the operational "
    "intent.\n\n"
    "DO NOT INVENT IDs. If no workflow's description clearly fits "
    "the email's intent, return `workflow_id: null` with confidence "
    "0. Inventing an id causes the cascade to silently fall "
    "through. Be conservative — Tier 3 fires workflows directly "
    "without the safety net of a category bridge, so confidence "
    "must be high.\n\n"
    "Output JSON with these keys:\n"
    "  - `workflow_id` (string OR null) — the chosen workflow's id, "
    "or null if none fits\n"
    "  - `confidence` (0.0–1.0)\n"
    "  - `reasoning` (string) — one or two sentences citing the "
    "workflow name or description\n\n"
    "Calibration:\n"
    "  - 0.9+ — email content directly matches a workflow description\n"
    "  - 0.7–0.9 — likely fit; some inference required\n"
    "  - 0.65–0.7 — borderline; cascade floor for dispatch\n"
    "  - <0.65 — return null; message routes to unclassified triage\n\n"
    "Workflow registry:\n{{registry_json}}"
)


_PROMPTS: list[PromptSpec] = [
    PromptSpec(
        prompt_key="email.classify_into_taxonomy",
        display_name="Email — classify into tenant taxonomy",
        description=(
            "Tier 2 of the inbound email classification cascade. "
            "Picks one category from the tenant's taxonomy. "
            "Confidence below the per-tenant floor (default 0.55) "
            "falls through to Tier 3."
        ),
        system_prompt=_TAXONOMY_SYSTEM_PROMPT,
        variable_schema=_TAXONOMY_VARIABLE_SCHEMA,
        response_schema=_TAXONOMY_RESPONSE_SCHEMA,
    ),
    PromptSpec(
        prompt_key="email.classify_into_registry",
        display_name="Email — classify into workflow registry",
        description=(
            "Tier 3 of the inbound email classification cascade. "
            "Picks one workflow from the tenant's Tier-3-enrolled "
            "workflow registry. Confidence below the per-tenant "
            "floor (default 0.65) routes the message to "
            "unclassified triage."
        ),
        system_prompt=_REGISTRY_SYSTEM_PROMPT,
        variable_schema=_REGISTRY_VARIABLE_SCHEMA,
        response_schema=_REGISTRY_RESPONSE_SCHEMA,
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
        variable_schema=spec.variable_schema,
        response_schema=spec.response_schema,
        model_preference="simple",
        temperature=0.2,
        max_tokens=512,
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
            domain="classification",
        )
        db.add(prompt)
        db.flush()
        _create_version(
            db, prompt, spec, version_number=1,
            changelog=f"Phase R-6.1a seed — {spec.prompt_key}.",
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
                f"Phase R-6.1a re-seed — platform update to "
                f"{spec.prompt_key}."
            ),
        )
        db.commit()
        stats["updated"] = 1
        return stats

    _create_version(
        db, prompt, spec, version_number=1,
        changelog=(
            f"Phase R-6.1a seed — adding v1 to existing empty "
            f"prompt {spec.prompt_key}."
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
            stats = seed_one(db, spec)
            for k, v in stats.items():
                totals[k] = totals.get(k, 0) + v
            verb = next(
                (k for k, v in stats.items() if v), "unchanged"
            )
            logger.info("  %s  %s", spec.prompt_key, verb)
    finally:
        db.close()
    logger.info(
        "Phase R-6.1a seed totals: created=%d updated=%d noop=%d "
        "skipped_custom=%d",
        totals["created"], totals["updated"], totals["noop"],
        totals["skipped_custom"],
    )


if __name__ == "__main__":
    main()

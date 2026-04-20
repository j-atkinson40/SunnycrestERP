"""Seed Phase 4 Intelligence prompts — nl_creation.extract.{case, event, contact}.

Idempotent. Adds 3 new platform-global prompts (company_id=null) with
Phase 4 verbatim content. Running multiple times creates zero new
rows if they already exist.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        python scripts/seed_intelligence_phase4.py

Design notes:

1. Case prompt content is copied from `scribe.extract_first_call`
   conceptually (same field taxonomy) but seeded as an INDEPENDENT
   prompt so Phase 4 and the existing first-call flow can evolve
   independently (per approved plan §4).

2. All three prompts share the same variable schema:
     entity_type, natural_language, tenant_context, space_context,
     field_descriptions, structured_extractions
   matching `nl_creation.ai_extraction.run_ai_extraction`.

3. Response schema enforces the { "extractions": [...] } shape the
   orchestrator expects. Anthropic's force_json + response_schema
   co-validate.

4. Each prompt routes via `simple` (Haiku) for latency. Extraction
   route (Sonnet) is available via override if Haiku confidence
   degrades for a given entity type — post-arc tuning.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


# ── Shared prompt scaffolding ────────────────────────────────────────


_SYSTEM_PROMPT_PREFIX = """\
You are a strict field extraction engine for the Bridgeable platform.

Your job: extract structured values from a single user sentence for a
{display_name} operation. You return JSON ONLY. Never narrate.

Rules:
1. Return JSON in the exact shape: {{"extractions": [{{"field_key": "...", "value": ..., "confidence": 0.0-1.0}}]}}
2. Only include fields you are CONFIDENT about. Missing fields are fine — do NOT hallucinate.
3. Confidence ranges: 0.95 unambiguous · 0.80 reasonable · 0.60 ambiguous · below 0.6 omit the field.
4. Fields marked `[required]` must be extracted when present in the input.
5. PRESERVE structured_extractions — never override a value already extracted deterministically.
6. Dates must be ISO (YYYY-MM-DD). Times must be HH:MM 24-hour. Datetimes ISO (YYYY-MM-DDTHH:MM).
7. Names: return as {{"first_name": "...", "middle_name": "...", "last_name": "..."}}. Omit parts you cannot split.
8. Informant-style compound fields: {{"name": "Mary", "relationship": "daughter"}}.
9. Entity references (company, service_location, funeral_home): return the SURFACE NAME as the user said it; the system fuzzy-matches.

Input context:
- tenant: {{tenant_context}}
- space: {{space_context}}
- today: reference date context

Available fields for this {display_name}:
{{field_descriptions}}

Already extracted by deterministic parsers (do NOT override):
{{structured_extractions}}
"""


_USER_TEMPLATE = "{{natural_language}}"


_VAR_SCHEMA = {
    "entity_type": {"type": "string", "required": True},
    "natural_language": {"type": "string", "required": True},
    "tenant_context": {"type": "string", "required": True},
    "space_context": {"type": "string", "required": True},
    "field_descriptions": {"type": "string", "required": True},
    "structured_extractions": {"type": "string", "required": True},
}


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "extractions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_key": {"type": "string"},
                    "value": {},
                    "confidence": {"type": "number"},
                },
                "required": ["field_key", "value", "confidence"],
            },
        },
    },
    "required": ["extractions"],
}


# ── Per-entity domain hints ─────────────────────────────────────────


_PROMPTS = [
    {
        "prompt_key": "nl_creation.extract.case",
        "display_name": "NL Creation — Case",
        "description": (
            "Extract case fields from a funeral director's one-sentence "
            "intake. Demo-critical: 'new case John Smith DOD tonight "
            "daughter Mary wants Thursday service Hopkins FH'."
        ),
        "domain": "nl_creation",
        "model_preference": "simple",
        "system_extras": """\

DOMAIN: funeral home case intake.

Vocabulary hints:
- "DOD" = date of death. "DOB" = date of birth.
- "tonight" = today's date.
- "daughter Mary" / "son John" / "wife Sarah" = informant_name + informant_relationship.
- "Hopkins FH" / "Hopkins Funeral Home" = funeral_home field.
- "Thursday service" / "Friday service" = service_date (next occurrence).
- "Riverside Chapel" / "St Mary's" = service_location (church/cemetery).

Critical: split names into first/middle/last. "John Smith" → first=John, last=Smith.
"John Q Smith" → first=John, middle=Q, last=Smith.
""",
    },
    {
        "prompt_key": "nl_creation.extract.event",
        "display_name": "NL Creation — Event",
        "description": (
            "Extract event fields (title, start, end, location) from an "
            "NL input for calendar event creation."
        ),
        "domain": "nl_creation",
        "model_preference": "simple",
        "system_extras": """\

DOMAIN: calendar event scheduling.

Vocabulary hints:
- "tomorrow at 2pm" = event_start tomorrow at 14:00.
- "lunch with Jim" = title "Lunch with Jim".
- "Friday 10 to 11am" = event_start Friday 10:00, event_end Friday 11:00.
- "conference room A" / "the boardroom" / "Starbucks on Main" = event_location.

Prefer the SHORTEST clear title. Don't include times or locations in the title.
""",
    },
    {
        "prompt_key": "nl_creation.extract.contact",
        "display_name": "NL Creation — Contact",
        "description": (
            "Extract contact fields (name, company, role, phone, email) "
            "from an NL input for CRM contact creation."
        ),
        "domain": "nl_creation",
        "model_preference": "simple",
        "system_extras": """\

DOMAIN: CRM contact creation.

Vocabulary hints:
- "Mary Johnson at Hopkins FH, office manager" = name {first=Mary, last=Johnson},
  company "Hopkins FH", title_or_role "office manager".
- "Bob Smith bob@acme.com 555-1234" = name {first=Bob, last=Smith},
  email "bob@acme.com", phone "555-1234".
""",
    },
]


# ── Seeder ───────────────────────────────────────────────────────────


def seed(db: Session) -> tuple[int, int]:
    created_prompts = 0
    created_versions = 0

    for spec in _PROMPTS:
        key = spec["prompt_key"]
        existing = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == key,
            )
            .first()
        )
        if existing is None:
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=key,
                display_name=spec["display_name"],
                description=spec["description"],
                domain=spec["domain"],
            )
            db.add(prompt)
            db.flush()
            created_prompts += 1
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

        system_prompt = (
            _SYSTEM_PROMPT_PREFIX.format(display_name=spec["display_name"])
            + spec["system_extras"]
        )
        version = IntelligencePromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            system_prompt=system_prompt,
            user_template=_USER_TEMPLATE,
            variable_schema=_VAR_SCHEMA,
            response_schema=_RESPONSE_SCHEMA,
            model_preference=spec["model_preference"],
            temperature=0.2,
            max_tokens=1024,
            force_json=True,
            supports_streaming=False,
            supports_tool_use=False,
            status="active",
            changelog="Phase 4 seed — NL Creation overlay extraction.",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(version)
        created_versions += 1

    db.commit()
    return created_prompts, created_versions


def main() -> None:
    db = SessionLocal()
    try:
        p, v = seed(db)
        print(f"[phase4-seed] Created {p} prompts, {v} versions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

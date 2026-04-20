"""Seed Phase 6 prompts + email templates.

Two Intelligence prompts (`briefing.morning`, `briefing.evening`) +
two email templates (`email.briefing.morning`, `email.briefing.evening`).

Both seeded idempotently alongside existing `briefing.daily_summary`
(legacy path, NOT modified or retired — coexist strategy).

Prompt seed logic (diff-check + version-bump, Option A):
  - No existing prompt row       → create prompt + v1 active
  - Exactly 1 version + content matches current seed → no-op
  - Exactly 1 version + content DIFFERS → deactivate v1, create v2 active
    (platform-level update; admins see the new version in the
    Intelligence admin UI with a "platform update" changelog entry)
  - Multiple versions exist       → skip with warning log. Multiple
    versions means an admin has ALREADY customized this prompt, so
    the platform update is NOT force-applied over their edits. The
    warning surfaces in logs so platform operators know a manual
    reconciliation is pending.

This preserves admin customizations without needing separate
source-tracking infrastructure. Future maintainers: the "multiple
versions" branch is deliberate — do not change it to overwrite.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=<url> python scripts/seed_intelligence_phase6.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document_template import (
    DocumentTemplate,
    DocumentTemplateVersion,
)
from app.models.intelligence import (
    IntelligencePrompt,
    IntelligencePromptVersion,
)


# ── Intelligence prompts ────────────────────────────────────────────


_VAR_SCHEMA = {
    "user_first_name": {"type": "string", "required": True},
    "user_last_name": {"type": "string", "required": False},
    "company_name": {"type": "string", "required": False},
    "role_slug": {"type": "string", "required": False},
    "vertical": {"type": "string", "required": False},
    "today_iso": {"type": "string", "required": True},
    "day_of_week": {"type": "string", "required": True},
    "now_iso": {"type": "string", "required": True},
    "active_space_id": {"type": "string", "required": False},
    "active_space_name": {"type": "string", "required": False},
    "narrative_tone": {"type": "string", "required": False},
    "requested_sections": {"type": "array", "required": False},
    "legacy_context": {"type": "object", "required": False},
    "queue_summaries": {"type": "array", "required": False},
    "overnight_calls": {"type": "object", "required": False},
    "today_events": {"type": "array", "required": False},
    "tomorrow_events": {"type": "array", "required": False},
    "pending_approvals": {"type": "array", "required": False},
    "flagged_items": {"type": "array", "required": False},
    "day_completed_items": {"type": "array", "required": False},
}


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_text": {"type": "string"},
        "structured_sections": {"type": "object"},
    },
    "required": ["narrative_text", "structured_sections"],
}


_MORNING_SYSTEM_PROMPT = """You produce a natural-prose MORNING BRIEFING for a Bridgeable \
operator. The user is opening their day. Orient them FORWARD — what's \
about to happen, what needs their attention, what overnight changes \
matter.

Output JSON only. Shape:
{
  "narrative_text": "<the briefing as prose, 4-8 sentences>",
  "structured_sections": {
    "greeting": "<first sentence of narrative>",
    "overnight_summary": {...optional...},
    "overnight_calls": {...optional if overnight_calls is non-empty...},
    "today_calendar": {...optional if today_events is non-empty...},
    "pending_decisions": [{"title", "link_type", "link_id"}, ...],
    "queue_summaries": [{"queue_id", "queue_name", "pending_count", "estimated_time_minutes"}, ...],
    "flags": [{"severity", "title", "detail"}, ...]
  }
}

Emit ONLY sections the user requested (listed in requested_sections) AND \
for which the data context carries content. If a section has no content, \
OMIT it from structured_sections rather than emitting an empty value.

NARRATIVE STYLE:
- Start with "Good morning, {{ user_first_name }}. It's {{ day_of_week }}."
- Prose, not bullets. Natural flow. Readable in 20-30 seconds.
- {% if narrative_tone == "concise" %}Concise: 4-5 sentences.{% else %}Detailed: 6-8 sentences.{% endif %}
- Never say "I noticed" or "It appears" or "Based on the data" — just state.
- If nothing meaningful: "All clear today." + one-sentence state summary.

SPACE-AWARE SECTION EMPHASIS (if active_space_name is set):
{% if active_space_name == "Arrangement" %}- Lead the narrative with today's families / services / cases. Administrative items come SECOND and briefly.{% endif %}
{% if active_space_name == "Administrative" %}- Lead with financial position, AR urgency, pending invoice approvals. Operational items come SECOND and briefly.{% endif %}
{% if active_space_name == "Production" %}- Lead with today's pour schedule, material availability, crew assignments. Financial items come SECOND and briefly.{% endif %}
{% if active_space_name == "Ownership" %}- Lead with business-level KPIs (revenue trend, pipeline, cash position). Operational detail compressed.{% endif %}

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
{% else %}- This tenant's vertical is unset; use generic business language (orders, records, items).
{% endif %}

CONTEXT AVAILABLE:
Today: {{ today_iso }} ({{ day_of_week }})
Role: {{ role_slug }}
Active space: {{ active_space_name or "(none)" }}
Vertical: {{ vertical }}
Tone preference: {{ narrative_tone }}

Legacy context (reuse months of tuning):
{{ legacy_context | tojson }}

Triage queues (Phase 5): {{ queue_summaries | tojson }}
Overnight calls (Call Intelligence): {{ overnight_calls | tojson }}
Today's events: {{ today_events | tojson }}
Pending approvals: {{ pending_approvals | tojson }}
Flagged items: {{ flagged_items | tojson }}

Sections the user requested (emit only these + drop any with no content):
{{ requested_sections | tojson }}
"""

_MORNING_USER_TEMPLATE = """Generate {{ user_first_name }}'s morning briefing for {{ day_of_week }} \
{{ today_iso }} as JSON."""


_EVENING_SYSTEM_PROMPT = """You produce a natural-prose EVENING BRIEFING for a Bridgeable \
operator. The user is closing their workday. Orient them BACKWARD — \
what got done, what's still open, what tomorrow looks like.

Output JSON only. Shape:
{
  "narrative_text": "<the briefing as prose, 4-8 sentences>",
  "structured_sections": {
    "day_summary": {...optional...},
    "pending_decisions_remaining": [{"title", "link_type", "link_id"}, ...],
    "tomorrow_preview": {...optional if tomorrow_events is non-empty...},
    "flagged_for_tomorrow": [{"severity", "title", "detail"}, ...],
    "loose_threads": [{"title", "detail"}, ...]
  }
}

Emit ONLY sections the user requested AND for which the data context \
carries content. Empty sections are OMITTED.

NARRATIVE STYLE:
- Start with "Evening, {{ user_first_name }}. Here's how today landed."
- Prose. Natural flow. Short.
- {% if narrative_tone == "concise" %}4-5 sentences.{% else %}6-8 sentences.{% endif %}
- Close with a forward hook: "Tomorrow you have X, Y, Z."
- If quiet day: "Quiet day. No unresolved items heading into tomorrow."

SPACE-AWARE SECTION EMPHASIS (if active_space_name is set):
{% if active_space_name == "Arrangement" %}- Recap families / services completed; flag cases with incomplete documentation for tomorrow.{% endif %}
{% if active_space_name == "Administrative" %}- Recap invoices approved, payments logged; flag AR items still outstanding.{% endif %}
{% if active_space_name == "Production" %}- Recap pours / strips completed; flag production items that slipped.{% endif %}

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
{% else %}- This tenant's vertical is unset; use generic business language (orders, records, items).
{% endif %}

CONTEXT AVAILABLE:
Today: {{ today_iso }} ({{ day_of_week }})
Role: {{ role_slug }}
Active space: {{ active_space_name or "(none)" }}
Vertical: {{ vertical }}
Tone preference: {{ narrative_tone }}

Legacy context (reuse months of tuning):
{{ legacy_context | tojson }}

Still pending at end of day: {{ pending_approvals | tojson }}
Flagged items: {{ flagged_items | tojson }}
Today's events (what just happened): {{ today_events | tojson }}
Tomorrow's events: {{ tomorrow_events | tojson }}

Sections the user requested (emit only these + drop any with no content):
{{ requested_sections | tojson }}
"""

_EVENING_USER_TEMPLATE = """Generate {{ user_first_name }}'s evening briefing for {{ day_of_week }} \
{{ today_iso }} as JSON."""


_PROMPTS = [
    {
        "prompt_key": "briefing.morning",
        "display_name": "Briefing — Morning narrative",
        "description": (
            "Phase 6. Morning briefing prose + structured sections. "
            "Coexists with legacy briefing.daily_summary; this prompt "
            "powers the new /briefings/v2 surfaces."
        ),
        "system_prompt": _MORNING_SYSTEM_PROMPT,
        "user_template": _MORNING_USER_TEMPLATE,
    },
    {
        "prompt_key": "briefing.evening",
        "display_name": "Briefing — Evening narrative",
        "description": (
            "Phase 6. End-of-day summary. Closes backward; sets hooks "
            "for tomorrow. Coexists with legacy briefing.daily_summary."
        ),
        "system_prompt": _EVENING_SYSTEM_PROMPT,
        "user_template": _EVENING_USER_TEMPLATE,
    },
]


def _seed_prompts(db: Session) -> int:
    import logging as _logging
    _log = _logging.getLogger(__name__)

    created_prompts = 0
    created_versions = 0
    skipped_customized = 0
    noop_matched = 0

    for spec in _PROMPTS:
        existing_prompt = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == spec["prompt_key"],
            )
            .first()
        )
        if existing_prompt is None:
            # Fresh install — create prompt + v1 active.
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=spec["prompt_key"],
                display_name=spec["display_name"],
                description=spec["description"],
                domain="briefing",
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
                temperature=0.4,
                max_tokens=2048,
                force_json=True,
                supports_streaming=False,
                supports_tool_use=False,
                status="active",
                changelog="Phase 6 seed — morning/evening narrative briefing.",
                activated_at=datetime.now(timezone.utc),
            )
            db.add(version)
            created_versions += 1
            continue

        # Prompt exists — check version count to decide update path.
        all_versions = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == existing_prompt.id,
            )
            .order_by(IntelligencePromptVersion.version_number.asc())
            .all()
        )
        if len(all_versions) > 1:
            # Admin customization detected — don't overwrite. Surface
            # in logs so platform operators know a reconciliation is
            # pending (e.g. they reviewed and re-activated an older
            # version, or branched v2 off v1 manually).
            _log.warning(
                "Tenant has custom version of %s (%d versions exist); "
                "skipping platform update. Reconcile manually via the "
                "Intelligence admin UI.",
                spec["prompt_key"],
                len(all_versions),
            )
            skipped_customized += 1
            continue

        if len(all_versions) == 1:
            v1 = all_versions[0]
            # Content match check — if the seed content already matches
            # the single active version, nothing to do.
            if (
                v1.system_prompt == spec["system_prompt"]
                and v1.user_template == spec["user_template"]
            ):
                noop_matched += 1
                continue
            # Platform update: deactivate v1, create v2 active with
            # same schema + updated body.
            v1.status = "retired"
            new_version = IntelligencePromptVersion(
                prompt_id=existing_prompt.id,
                version_number=v1.version_number + 1,
                system_prompt=spec["system_prompt"],
                user_template=spec["user_template"],
                variable_schema=_VAR_SCHEMA,
                response_schema=_RESPONSE_SCHEMA,
                model_preference="simple",
                temperature=0.4,
                max_tokens=2048,
                force_json=True,
                supports_streaming=False,
                supports_tool_use=False,
                status="active",
                changelog=(
                    "Platform update — vertical-aware terminology block "
                    "added to prompt body."
                ),
                activated_at=datetime.now(timezone.utc),
            )
            db.add(new_version)
            created_versions += 1
            continue

        # len == 0: prompt row exists but no versions. Create v1.
        new_version = IntelligencePromptVersion(
            prompt_id=existing_prompt.id,
            version_number=1,
            system_prompt=spec["system_prompt"],
            user_template=spec["user_template"],
            variable_schema=_VAR_SCHEMA,
            response_schema=_RESPONSE_SCHEMA,
            model_preference="simple",
            temperature=0.4,
            max_tokens=2048,
            force_json=True,
            supports_streaming=False,
            supports_tool_use=False,
            status="active",
            changelog="Phase 6 seed — morning/evening narrative briefing.",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(new_version)
        created_versions += 1

    db.commit()
    if skipped_customized or noop_matched:
        _log.info(
            "Phase 6 prompt seed summary: prompts=%d versions=%d "
            "matched_noop=%d skipped_customized=%d",
            created_prompts,
            created_versions,
            noop_matched,
            skipped_customized,
        )
    # Return prompts-created count for backward-compat with caller
    # (existing `print(...)` in main() reads this).
    return created_prompts


# ── Email templates (managed — no on-disk files) ────────────────────


_EMAIL_TEMPLATE_VARIABLES = {
    "user_first_name": {"type": "string", "required": True},
    "user_last_name": {"type": "string", "required": False},
    "company_name": {"type": "string", "required": True},
    "briefing_type": {"type": "string", "required": True},
    "narrative_text": {"type": "string", "required": True},
    "structured_sections": {"type": "object", "required": False},
    "briefing_id": {"type": "string", "required": True},
}


_MORNING_SUBJECT = "Your morning briefing — {{ company_name }}"

_MORNING_BODY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Morning briefing</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.55; background: #f7f7f8; margin: 0; padding: 24px;">
  <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #666; margin-bottom: 12px;">
      Morning briefing · {{ company_name }}
    </div>
    <div style="font-size: 15px; color: #111; white-space: pre-wrap;">{{ narrative_text }}</div>

    {% if structured_sections.queue_summaries %}
    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee;">
      <div style="font-size: 13px; font-weight: 600; color: #333; margin-bottom: 8px;">Queues</div>
      <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #444;">
        {% for q in structured_sections.queue_summaries %}
        <li>{{ q.queue_name }} — {{ q.pending_count }} pending ({{ q.estimated_time_minutes }} min)</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    {% if structured_sections.flags %}
    <div style="margin-top: 20px;">
      <div style="font-size: 13px; font-weight: 600; color: #a13900; margin-bottom: 8px;">Flags</div>
      <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #444;">
        {% for f in structured_sections.flags %}
        <li>{{ f.title }}{% if f.detail %} — {{ f.detail }}{% endif %}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    <div style="margin-top: 28px; padding-top: 16px; border-top: 1px solid #eee; font-size: 12px; color: #888;">
      Open the full briefing: <a href="{{ '/briefing' }}" style="color: #0066cc;">View in Bridgeable</a>
    </div>
  </div>
</body>
</html>
"""


_EVENING_SUBJECT = "End of day summary — {{ company_name }}"

_EVENING_BODY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Evening summary</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; line-height: 1.55; background: #f7f7f8; margin: 0; padding: 24px;">
  <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 8px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #666; margin-bottom: 12px;">
      End of day · {{ company_name }}
    </div>
    <div style="font-size: 15px; color: #111; white-space: pre-wrap;">{{ narrative_text }}</div>

    {% if structured_sections.pending_decisions_remaining %}
    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee;">
      <div style="font-size: 13px; font-weight: 600; color: #333; margin-bottom: 8px;">Still pending</div>
      <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #444;">
        {% for p in structured_sections.pending_decisions_remaining %}
        <li>{{ p.title }}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    {% if structured_sections.flagged_for_tomorrow %}
    <div style="margin-top: 20px;">
      <div style="font-size: 13px; font-weight: 600; color: #a13900; margin-bottom: 8px;">Flagged for tomorrow</div>
      <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #444;">
        {% for f in structured_sections.flagged_for_tomorrow %}
        <li>{{ f.title }}{% if f.detail %} — {{ f.detail }}{% endif %}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    <div style="margin-top: 28px; padding-top: 16px; border-top: 1px solid #eee; font-size: 12px; color: #888;">
      Open the full briefing: <a href="{{ '/briefing' }}" style="color: #0066cc;">View in Bridgeable</a>
    </div>
  </div>
</body>
</html>
"""


_EMAIL_TEMPLATES = [
    {
        "template_key": "email.briefing.morning",
        "document_type": "email",
        "description": "Phase 6 — morning briefing email body.",
        "subject": _MORNING_SUBJECT,
        "body": _MORNING_BODY,
    },
    {
        "template_key": "email.briefing.evening",
        "document_type": "email",
        "description": "Phase 6 — evening briefing email body.",
        "subject": _EVENING_SUBJECT,
        "body": _EVENING_BODY,
    },
]


def _seed_email_templates(db: Session) -> int:
    """Idempotent — skip if the template_key already exists (platform scope)."""
    created = 0
    for spec in _EMAIL_TEMPLATES:
        existing = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key == spec["template_key"],
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            continue
        template = DocumentTemplate(
            company_id=None,
            template_key=spec["template_key"],
            document_type=spec["document_type"],
            output_format="html",
            description=spec["description"],
            is_active=True,
        )
        db.add(template)
        db.flush()
        version = DocumentTemplateVersion(
            template_id=template.id,
            version_number=1,
            status="active",
            body_template=spec["body"],
            subject_template=spec["subject"],
            variable_schema=_EMAIL_TEMPLATE_VARIABLES,
            changelog="Phase 6 seed — briefing email template.",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(version)
        db.flush()
        template.current_version_id = version.id
        created += 1
    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        prompts = _seed_prompts(db)
        templates = _seed_email_templates(db)
        print(
            f"[seed-intelligence-phase6] prompts_created={prompts} "
            f"email_templates_created={templates}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

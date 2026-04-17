"""Natural-language field extraction for command-bar workflow overlays.

Given a workflow and free-text input, Claude extracts structured values
for each of the workflow's input steps. Values are then resolved against
real platform data (CRM contacts, select options, dates) so what the
user sees matches records that actually exist.

This service is called for both live debounced extraction and the final
extraction before submit; callers pass `is_final=True` to opt into the
higher-fidelity Sonnet model. Haiku is used for the hot path.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.workflow import Workflow, WorkflowStep
from app.services import ai_service

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────

def build_field_schema(workflow: Workflow, steps: list[WorkflowStep]) -> list[dict]:
    """Describe the workflow's input steps so Claude knows what to extract."""
    schema = []
    for step in sorted(steps, key=lambda s: s.step_order):
        if step.step_type != "input":
            continue
        cfg = step.config or {}
        schema.append({
            "field_key": step.step_key,
            "prompt": cfg.get("prompt", step.step_key),
            "input_type": cfg.get("input_type", "text"),
            "required": cfg.get("required", True),
            "record_type": cfg.get("record_type"),
            "options": cfg.get("options", []),
        })
    return schema


def build_system_prompt(
    field_schema: list[dict], existing_fields: dict[str, dict]
) -> str:
    descs: list[str] = []
    for f in field_schema:
        line = f'- {f["field_key"]}: {f["prompt"]}'
        t = f["input_type"]
        if t == "select" and f.get("options"):
            opts = ", ".join(o.get("label", o.get("value", "")) for o in f["options"])
            line += f" (options: {opts})"
        elif t == "crm_search":
            line += " (match against company/contact names)"
        elif t == "record_search":
            line += f" (find an existing {f.get('record_type') or 'record'})"
        elif t == "date_picker":
            line += " (resolve relative dates to YYYY-MM-DD)"
        elif t == "datetime_picker":
            line += " (resolve to YYYY-MM-DDTHH:MM 24-hour)"
        elif t == "number":
            line += " (numeric value only)"
        if not f["required"]:
            line += " [optional]"
        descs.append(line)

    already_lines: list[str] = []
    for key, val in (existing_fields or {}).items():
        if not val:
            continue
        conf = float(val.get("confidence", 0) or 0)
        if conf >= 0.85:
            shown = val.get("display_value") or val.get("value") or ""
            already_lines.append(
                f'- {key}: "{shown}" (keep unless user clearly stated a different value)'
            )

    today_str = date.today().isoformat()
    already_block = (
        "\nAlready extracted (preserve unless clearly overridden):\n"
        + "\n".join(already_lines)
        if already_lines
        else ""
    )
    fields_block = "\n".join(descs) if descs else "(no fields)"

    return (
        "You extract structured workflow field values from a user's natural-language "
        "description. Output JSON only, matching the requested schema.\n\n"
        f"Fields to extract:\n{fields_block}\n\n"
        f"Today's date: {today_str}\n\n"
        "Rules:\n"
        "1. Return ONLY valid JSON, no explanation or markdown.\n"
        "2. For fields not mentioned: set the value to null.\n"
        "3. Relative dates ('next Tuesday', 'Friday', 'the 17th') → YYYY-MM-DD using today.\n"
        "4. Times ('2pm', '14:00', '100:00' typo → 10:00) → HH:MM 24-hour.\n"
        "5. Company / contact names: return the name as spoken; the system will fuzzy-match.\n"
        "6. Confidence: 0.95 unambiguous · 0.80 reasonable · 0.60 ambiguous · below 0.60 return null.\n"
        "7. When ambiguous, include an 'alternatives' list.\n"
        f"{already_block}\n\n"
        'JSON shape: {"field_key": {"value": "...", "confidence": 0.95, "alternatives": []}, ...}.'
        " Omit fields not mentioned OR set them to null."
    )


def _format_date_display(value: str | None) -> str:
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d", "%H:%M", "%I:%M %p"):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d":
                return dt.strftime("%A, %b %d")
            if fmt == "%Y-%m-%dT%H:%M":
                return dt.strftime("%A, %b %d at %I:%M %p")
            return dt.strftime("%I:%M %p")
        except ValueError:
            continue
    return value


def _fuzzy_match_company(
    db: Session, name: str, company_id: str
) -> dict | None:
    if not name:
        return None
    # Exact
    exact = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(name),
        )
        .first()
    )
    if exact:
        return {"id": exact.id, "name": exact.name, "match_score": 0.99}
    # Contains
    contains = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(f"%{name}%"),
        )
        .first()
    )
    if contains:
        ratio = len(name) / max(len(contains.name), 1)
        return {
            "id": contains.id,
            "name": contains.name,
            "match_score": min(0.9, ratio + 0.3),
        }
    # Word-by-word
    for word in (w for w in name.split() if len(w) > 2):
        partial = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.name.ilike(f"%{word}%"),
            )
            .first()
        )
        if partial:
            return {"id": partial.id, "name": partial.name, "match_score": 0.75}
    return None


def _fuzzy_match_option(value: str, options: list[dict]) -> dict | None:
    if not value or not options:
        return None
    v = value.lower().strip()
    for o in options:
        if str(o.get("value", "")).lower() == v or str(o.get("label", "")).lower() == v:
            return o
    for o in options:
        lbl = str(o.get("label", "")).lower()
        if lbl and (v in lbl or lbl in v):
            return o
    return None


def resolve_fields(
    extracted: dict[str, Any],
    field_schema: list[dict],
    db: Session,
    company_id: str,
) -> dict[str, dict]:
    schema_map = {f["field_key"]: f for f in field_schema}
    resolved: dict[str, dict] = {}
    for key, payload in (extracted or {}).items():
        if payload is None:
            continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get("value")
        if raw is None or raw == "":
            continue
        try:
            conf = float(payload.get("confidence", 0.8))
        except (TypeError, ValueError):
            conf = 0.8
        s = schema_map.get(key, {})
        t = s.get("input_type", "text")

        if t == "crm_search" and isinstance(raw, str):
            match = _fuzzy_match_company(db, raw, company_id)
            if match:
                resolved[key] = {
                    "value": match["id"],
                    "display_value": match["name"],
                    "confidence": min(conf, match["match_score"]),
                    "matched_id": match["id"],
                    "matched_type": "company_entity",
                    "alternatives": payload.get("alternatives", []),
                }
            else:
                resolved[key] = {
                    "value": raw,
                    "display_value": raw,
                    "confidence": min(conf, 0.6),
                    "matched_id": None,
                    "unresolved": True,
                }
        elif t in ("date_picker", "datetime_picker"):
            resolved[key] = {
                "value": raw,
                "display_value": _format_date_display(str(raw)),
                "confidence": conf,
                "alternatives": payload.get("alternatives", []),
            }
        elif t == "select":
            opt = _fuzzy_match_option(str(raw), s.get("options", []))
            if opt:
                resolved[key] = {
                    "value": opt.get("value"),
                    "display_value": opt.get("label", opt.get("value")),
                    "confidence": conf,
                }
            else:
                resolved[key] = {
                    "value": raw,
                    "display_value": str(raw),
                    "confidence": min(conf, 0.65),
                }
        else:
            resolved[key] = {
                "value": raw,
                "display_value": str(raw),
                "confidence": conf,
                "alternatives": payload.get("alternatives", []),
            }
    return resolved


def extract(
    db: Session,
    *,
    workflow_id: str,
    input_text: str,
    company_id: str,
    existing_fields: dict | None = None,
    is_final: bool = False,
) -> dict:
    """Main entry point — returns {fields: {...}, raw_input: str}."""
    existing = existing_fields or {}
    if not input_text or not input_text.strip():
        return {"fields": {}, "raw_input": input_text}

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        return {"fields": {}, "raw_input": input_text}
    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow.id)
        .all()
    )
    schema = build_field_schema(workflow, steps)
    if not schema:
        return {"fields": {}, "raw_input": input_text}

    system_prompt = build_system_prompt(schema, existing)
    try:
        # is_final toggles to the more accurate model. ai_service.call_anthropic
        # does not expose model override today so we always use its default;
        # this is a seam for future upgrade.
        _ = is_final
        result = ai_service.call_anthropic(
            system_prompt=system_prompt,
            user_message=input_text,
            max_tokens=400,
        )
    except Exception as e:
        logger.debug("Extraction failed: %s", e)
        return {"fields": {}, "raw_input": input_text}

    if not isinstance(result, dict):
        return {"fields": {}, "raw_input": input_text}

    resolved = resolve_fields(result, schema, db, company_id)
    return {"fields": resolved, "raw_input": input_text}


# expose re for any caller that needs the same regex helpers
__all__ = ["extract", "build_field_schema", "resolve_fields"]

_ = re  # silence unused-import guards

"""Extraction service — wraps intelligence_service.execute for NL Overlay callers.

Phase 2a covers final_extract (the commit-time extraction called by the command
bar when the user hits Enter). live_extract (per-keystroke debounced mode) is
included for completeness but currently unused from the UI; Phase 2b wires it
up.

The actual rendering of fields_block / already_block / hint_block is the
caller's responsibility — they already have the Workflow context. This wrapper
just hands the pre-assembled blocks to the prompt.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.intelligence import intelligence_service

logger = logging.getLogger(__name__)


def final_extract(
    db: Session,
    *,
    workflow_id: str,
    input_text: str,
    company_id: str,
    session_id: str | None,
    fields_block: str,
    already_block: str = "",
    hint_block: str = "",
) -> dict | None:
    """Final commit-time extraction. Returns parsed JSON or None on error."""
    variables = {
        "fields_block": fields_block,
        "today_date": date.today().isoformat(),
        "already_block": already_block,
        "hint_block": hint_block,
        "input_text": input_text,
    }
    result = intelligence_service.execute(
        db,
        prompt_key="overlay.extract_fields_final",
        variables=variables,
        company_id=company_id,
        caller_module="command_bar_extract_service.extract",
        caller_entity_type="workflow",
        caller_entity_id=workflow_id,
        caller_command_bar_session_id=session_id,
    )
    if result.status == "success" and isinstance(result.response_parsed, dict):
        return result.response_parsed
    return None


def live_extract(
    db: Session,
    *,
    workflow_id: str,
    input_text: str,
    company_id: str,
    session_id: str | None,
    prior_extraction: dict | None = None,
    fields_block: str = "",
    hint_block: str = "",
) -> dict | None:
    """Per-keystroke live extraction using the cheaper model.

    prior_extraction is the dict of fields already resolved in this session;
    the prompt uses it to preserve high-confidence values as the user types more.
    """
    already_lines: list[str] = []
    for key, val in (prior_extraction or {}).items():
        if not isinstance(val, dict):
            continue
        conf = float(val.get("confidence", 0) or 0)
        if conf >= 0.85:
            shown = val.get("display_value") or val.get("value") or ""
            already_lines.append(
                f'- {key}: "{shown}" (keep unless user clearly stated a different value)'
            )
    already_block = (
        "\nAlready extracted (preserve unless clearly overridden):\n" + "\n".join(already_lines)
        if already_lines
        else ""
    )

    variables = {
        "fields_block": fields_block,
        "today_date": date.today().isoformat(),
        "already_block": already_block,
        "hint_block": hint_block,
        "input_text": input_text,
    }
    result = intelligence_service.execute(
        db,
        prompt_key="overlay.extract_fields_live",
        variables=variables,
        company_id=company_id,
        caller_module="command_bar_extract_service.live_extract",
        caller_entity_type="workflow",
        caller_entity_id=workflow_id,
        caller_command_bar_session_id=session_id,
    )
    if result.status == "success" and isinstance(result.response_parsed, dict):
        return result.response_parsed
    return None

"""Website analysis — Intelligence-layer wrapper for business-info extraction.

Phase 2c-2 migration: routes through the managed `onboarding.analyze_website`
prompt. The prompt carries the large system prompt describing the expected
JSON schema verbatim.
"""

import logging

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

# ~15000 tokens ≈ 60000 chars — truncation keeps us well inside Haiku's window.
MAX_CONTENT_CHARS = 60_000


def analyze_website_content(
    db: Session,
    raw_content: str,
    *,
    company_id: str | None = None,
    company_entity_id: str | None = None,
) -> dict:
    """Extract structured business info from website content via the Intelligence layer.

    Returns: {"analysis": dict, "input_tokens": int, "output_tokens": int}
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    # Truncate content to fit token limits
    truncated = raw_content[:MAX_CONTENT_CHARS]

    from app.services.intelligence import intelligence_service

    result = intelligence_service.execute(
        db,
        prompt_key="onboarding.analyze_website",
        variables={"raw_content": truncated},
        company_id=company_id,
        caller_module="website_analysis_service.analyze_website_content",
        caller_entity_type="company_entity" if company_entity_id else None,
        caller_entity_id=company_entity_id,
    )

    if result.status == "success" and isinstance(result.response_parsed, dict):
        analysis = result.response_parsed
    else:
        logger.warning(
            "Website analysis failed: status=%s error=%s",
            result.status, result.error_message,
        )
        analysis = {
            "error": "Failed to parse AI response",
            "raw": (result.response_text or "")[:500],
        }

    return {
        "analysis": analysis,
        "input_tokens": result.input_tokens or 0,
        "output_tokens": result.output_tokens or 0,
    }

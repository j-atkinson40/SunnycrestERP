"""Phase R-6.1a — Tier 2 prompt definition (documentation).

Canonical seed lives in ``scripts/seed_email_classification_intelligence.py``.
This module is documentation-adjacent-to-code so a developer reading
``tier_2_taxonomy.classify`` can find the prompt shape next to the
caller without leaving the package.
"""

PROMPT_KEY = "email.classify_into_taxonomy"

# Variable schema — keys the prompt's Jinja template references.
# Mirrored verbatim by the seed script. ``required`` flags the LLM
# render-time validator.
VARIABLE_SCHEMA = {
    "subject": {"type": "string", "required": False},
    "sender_email": {"type": "string", "required": True},
    "sender_name": {"type": "string", "required": False},
    "body_excerpt": {"type": "string", "required": False},
    "taxonomy_json": {"type": "array", "required": True},
}

# Response schema — force_json=True parses the LLM output against
# this shape; parse_error raised in intelligence_service maps to
# status="parse_error" returned from execute().
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category_id": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["category_id", "confidence"],
}

"""Phase R-6.1a — Tier 3 prompt definition (documentation).

Canonical seed lives in ``scripts/seed_email_classification_intelligence.py``.
"""

PROMPT_KEY = "email.classify_into_registry"

VARIABLE_SCHEMA = {
    "subject": {"type": "string", "required": False},
    "sender_email": {"type": "string", "required": True},
    "sender_name": {"type": "string", "required": False},
    "body_excerpt": {"type": "string", "required": False},
    "registry_json": {"type": "array", "required": True},
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "workflow_id": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["workflow_id", "confidence"],
}

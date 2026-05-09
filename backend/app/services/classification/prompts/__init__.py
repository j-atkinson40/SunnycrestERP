"""Phase R-6.1a — Classification prompt definitions.

The two managed prompts driving Tier 2 + Tier 3 are seeded via
``backend/scripts/seed_email_classification_intelligence.py``. The
modules in this subpackage document the prompt shape (system_prompt,
user_template, variable_schema, response_schema) for code-search
discoverability and to keep the canonical text adjacent to the code
that consumes it.

The actual seed payload is duplicated in the seed script — the seed
script is the single source of truth for what gets written to the
database. The modules here mirror it for documentation; if they
drift they're documentation, not behavior. The seed-script-as-SOT
matches the Phase 6 / 8b / 8d.1 / Step 5.1 idempotent-seed canon.
"""

from app.services.classification.prompts.email_classify_into_taxonomy import (
    PROMPT_KEY as TIER_2_PROMPT_KEY,
)
from app.services.classification.prompts.email_classify_into_registry import (
    PROMPT_KEY as TIER_3_PROMPT_KEY,
)

__all__ = ["TIER_2_PROMPT_KEY", "TIER_3_PROMPT_KEY"]

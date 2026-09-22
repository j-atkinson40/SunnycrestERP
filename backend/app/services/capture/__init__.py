"""Order capture — what an order must carry, and what is still missing.

Two modules, deliberately separate:

    schema.py   what this tenant asks for, and which questions apply to a vault
    missing.py  given extracted values, what is answered and what is still needed

⚠️ NEITHER CALLS A MODEL. The extraction model pulls values out of a transcript;
it does not decide what an order requires. That split is the ruling
`The model extracts; the server decides what is missing` (DECISIONS 2026-09-22).
"""

from app.services.capture.missing import CaptureState, evaluate
from app.services.capture.schema import (
    FieldDefinition,
    PLATFORM_DEFAULT_FIELDS,
    TenantCaptureConfig,
    VAULT_FIELD_ID,
    resolve_schema,
)

__all__ = [
    "CaptureState",
    "FieldDefinition",
    "PLATFORM_DEFAULT_FIELDS",
    "TenantCaptureConfig",
    "VAULT_FIELD_ID",
    "evaluate",
    "resolve_schema",
]

"""NL Creation — natural language creation with live overlay (Phase 4).

Public surface:

    from app.services.nl_creation import (
        # orchestration
        extract, create,
        # types
        ExtractionRequest, ExtractionResult, FieldExtraction,
        NLEntityConfig, FieldExtractor,
        # errors
        NLCreationError, UnknownEntityType, CreationValidationError,
        # registry
        get_entity_config, list_entity_types, list_entity_configs,
        # resolver (optional imports for callers who want raw hits)
        resolve, resolve_company_entity, resolve_contact, resolve_fh_case,
    )

The service layer is wrapped by `backend/app/api/routes/nl_creation.py`
as the public HTTP surface at `/api/v1/nl-creation/*`.

To add a new entity type:
  1. Append an `NLEntityConfig` in `entity_registry.py` with fields +
     AI prompt key + creator callable + space_defaults.
  2. Seed a new managed prompt in `scripts/seed_intelligence.py` as
     `nl_creation.extract.{entity_type}`.
  3. Add a Playwright spec under `frontend/tests/e2e/nl_create_*`.
"""

from app.services.nl_creation.entity_registry import (
    get_entity_config,
    list_entity_configs,
    list_entity_types,
)
from app.services.nl_creation.entity_resolver import (
    resolve,
    resolve_company_entity,
    resolve_contact,
    resolve_fh_case,
)
from app.services.nl_creation.extractor import create, extract
from app.services.nl_creation.types import (
    CreationValidationError,
    ExtractionRequest,
    ExtractionResult,
    ExtractionSource,
    FieldExtraction,
    FieldExtractor,
    NLCreationError,
    NLEntityConfig,
    UnknownEntityType,
)

__all__ = [
    # orchestration
    "extract",
    "create",
    # types
    "ExtractionRequest",
    "ExtractionResult",
    "FieldExtraction",
    "FieldExtractor",
    "NLEntityConfig",
    "ExtractionSource",
    # errors
    "NLCreationError",
    "UnknownEntityType",
    "CreationValidationError",
    # registry
    "get_entity_config",
    "list_entity_types",
    "list_entity_configs",
    # resolver
    "resolve",
    "resolve_company_entity",
    "resolve_contact",
    "resolve_fh_case",
]

"""Workshop primitive service package — Phase 1D pattern-establisher.

Per BRIDGEABLE_MASTER §3.26.14 Workshop primitive canon: this package
hosts the canonical service layer for Workshop template-type
registration + per-tenant Tune mode customization.

Phase 1D pattern-establisher discipline: registers
``burial_vault_personalization_studio`` as the first Workshop
template-type. Step 2 (Urn Vault Personalization Studio) extends the
registry with ``urn_vault_personalization_studio`` via the same
``register_template_type`` API. Future Generation Focus templates
(Wall Designer, Drawing Takeoff, Audit Prep, Mix Design, Legacy Studio,
monument customizer, engraved urn customizer per §3.26.11.12 strategic
vision) extend the same registry without per-template service forks.

**Public API**:

- ``registry`` — template-type registry (TemplateTypeDescriptor +
  module-level singleton + register/list/reset).
- ``tenant_config`` — per-tenant Tune mode storage + Tune mode boundary
  discipline (operates on Company.settings_json substrate).

**Anti-pattern guards**:

- §2.4.4 Anti-pattern 9 (primitive proliferation under composition
  pressure) — Tune mode is parameter overrides within canonical
  4-options vocabulary; does NOT introduce new option type or
  primitive.
- §3.26.11.12.16 Anti-pattern 4 (primitive count expansion against
  fifth Focus type rejected) — Workshop registry extends Generation
  Focus template registry; does NOT introduce new Focus type.
- §2.4.4 Anti-pattern 8 (vertical-specific code creep) — Workshop
  service is canonical platform substrate; FH-vertical or Mfg-vertical
  specifics dispatched via ``applicable_verticals`` filter, not
  vertical-specific service code.
"""

from __future__ import annotations

from app.services.workshop import registry  # noqa: F401
from app.services.workshop import tenant_config  # noqa: F401

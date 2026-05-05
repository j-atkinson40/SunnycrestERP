"""Personalization Studio canonical service package — Phase 1A canonical-
pattern-establisher of Step 1 Burial Vault Personalization Studio.

Per §3.26.11.12.19 Personalization Studio canonical category +
§3.26.11.12 Generation Focus canon: this package hosts the canonical
service layer for Personalization Studio Generation Focus instances.
Phase 1A canonical-pattern-establisher discipline: Step 2 (Urn Vault
Personalization Studio) inherits the same service module via
``template_type`` discriminator differentiation; future Generation Focus
templates extend the same service module per single-entity-with-discriminator
meta-pattern (§3.26.11.12.20).

**Public API**:

- ``instance_service`` — canonical Generation Focus instance lifecycle
  service (open / commit_canvas_state / get_canvas_state / commit_instance
  / abandon_instance).

**Canonical Document substrate consumption per D-9**: canvas state
persists to canonical Document + DocumentVersion. Each canvas commit
creates a new DocumentVersion with ``is_current=True`` flip per
§3.26.11.12.5 substrate-consumption canonical.

**Anti-pattern guards**:

- §2.4.4 Anti-pattern 8 (vertical-specific code creep) — service is
  canonical Personalization Studio service, NOT FH-vertical or
  Mfg-vertical specific. Per-vertical behavior canonicalized via
  ``authoring_context`` discriminator dispatch.
- §2.4.4 Anti-pattern 9 (primitive proliferation) — service is canonical
  Generation Focus instance lifecycle, NOT new platform primitive.
- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design)
  — service operates on canvas state JSON blob; UI shape is independent
  per canonical operational modes per §3.26.11.12.21.
"""

from __future__ import annotations

from app.services.personalization_studio import instance_service  # noqa: F401
from app.services.personalization_studio import ai_extraction_review  # noqa: F401
# Phase 1E Path B substrate consumption — side-effect-import registers
# the canonical ``personalization_studio_family_approval``
# ActionTypeDescriptor against the central registry per
# §3.26.11.12.19.5 + Pattern A canonical-pattern-establisher discipline.
from app.services.personalization_studio import family_approval  # noqa: F401

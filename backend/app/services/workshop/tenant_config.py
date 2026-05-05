"""Per-tenant Workshop Tune mode configuration — Phase 1D.

Per §3.26.11.12.9 Workshop integration mechanics + §3.26.11.12.19.2
canonical 4-options vocabulary scope freeze: this module hosts the
service layer for per-tenant Tune mode configuration storage +
read/write API.

**Storage substrate**: ``Company.settings_json`` JSONB-as-Text
(canonical existing tenant-configuration substrate per CLAUDE.md §4
settings pattern). Per-tenant Workshop configuration nested under
``Company.settings_json["workshop"][template_type]`` to namespace
across template-types as Step 2 + future templates extend.

The Q1 canonical resolution from r74 (per-tenant display label
customization) lives at ``Company.settings_json["personalization_display_labels"]``
— a sibling top-level key that predates this module. Phase 1D bridges
the two substrates: ``get_tenant_personalization_config`` reads display
labels from the existing key + the rest from the new ``workshop``
namespace; ``update_tenant_personalization_config`` writes both
synchronously.

**Tune mode boundary discipline** per §3.26.11.12.19.2: Tune mode
operates within the canonical 4-options vocabulary. Cannot add/remove
canonical option types — parameter overrides only.

Anti-pattern guards at this module:

- §2.4.4 Anti-pattern 9 (primitive proliferation under composition
  pressure): Tune mode dimensions are bounded canonical set per
  template-type; each dimension is parameter override on canonical
  vocabulary, NOT new option type.
- ``raise_on_unknown_dimension`` enforces Tune mode boundary at
  service-layer write boundary.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.services.personalization_config import (
    CANONICAL_OPTION_TYPES,
    DEFAULT_DISPLAY_LABELS,
    LEGACY_SERIES_PRINTS,
    VINYL_SYMBOLS,
    set_display_labels_for_tenant,
)
from app.services.workshop.registry import (
    CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT,
    TUNE_DIMENSION_DISPLAY_LABELS,
    TUNE_DIMENSION_EMBLEM_CATALOG,
    TUNE_DIMENSION_FONT_CATALOG,
    TUNE_DIMENSION_LEGACY_PRINT_CATALOG,
    get_template_type,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class WorkshopTuneModeError(Exception):
    http_status = 400


class WorkshopTuneModeNotFound(WorkshopTuneModeError):
    http_status = 404


class WorkshopTuneModeBoundaryViolation(WorkshopTuneModeError):
    """Raised when a write attempts to operate outside the canonical
    Tune mode boundary (e.g., adding/removing canonical option types,
    overriding non-registered dimensions, or overriding display labels
    for keys outside ``CANONICAL_OPTION_TYPES``).

    Anti-pattern guard at service substrate per §3.26.11.12.19.2 +
    §2.4.4 Anti-pattern 9.
    """

    http_status = 422


# ─────────────────────────────────────────────────────────────────────
# Default font catalog — Phase 1B canvas substrate ships these as the
# canonical-default font catalog. Per-tenant Tune mode selects subsets
# OR (when empty) inherits the full default catalog. Cannot add fonts
# outside the default catalog at Phase 1D — adding new fonts requires
# template-version bump per §3.26.14 Workshop primitive canon.
# ─────────────────────────────────────────────────────────────────────


DEFAULT_FONT_CATALOG: tuple[str, ...] = (
    "serif",
    "sans",
    "italic",
    "uppercase",
)


# Canonical-default emblem catalog — bounded set; extends via canon
# session, not via Tune mode dimension.
DEFAULT_EMBLEM_CATALOG: tuple[str, ...] = (
    "rose",
    "cross",
    "praying_hands",
    "dove",
    "wreath",
    "star_of_david",
    "masonic",
    "patriotic_flag",
)


# Canonical-default legacy print catalog flattened from LEGACY_SERIES_PRINTS
# at personalization_config.
def _default_legacy_print_catalog() -> tuple[str, ...]:
    flat: list[str] = []
    for category in LEGACY_SERIES_PRINTS:
        for print_name in category.get("prints", []):
            if print_name not in flat:
                flat.append(print_name)
    return tuple(flat)


DEFAULT_LEGACY_PRINT_CATALOG: tuple[str, ...] = _default_legacy_print_catalog()


# ─────────────────────────────────────────────────────────────────────
# Tenant config read
# ─────────────────────────────────────────────────────────────────────


def _settings_dict(company: Company) -> dict:
    if not company.settings_json:
        return {}
    try:
        return json.loads(company.settings_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _workshop_node(settings: dict, template_type: str) -> dict:
    """Return the ``workshop[template_type]`` sub-dict from settings,
    defaulting to ``{}``."""
    workshop = settings.get("workshop") or {}
    if not isinstance(workshop, dict):
        return {}
    node = workshop.get(template_type) or {}
    if not isinstance(node, dict):
        return {}
    return node


def get_tenant_personalization_config(
    db: Session,
    *,
    company_id: str,
    template_type: str,
) -> dict[str, Any]:
    """Return the per-tenant Tune mode configuration for a template-type.

    Returns the canonical full shape with defaults applied — every Tune
    mode dimension surfaces with either the tenant's override OR the
    canonical default. Chrome consumers can render the configuration
    surface directly without secondary default-resolution.

    Returned shape (Phase 1D pattern-establisher):
      {
        "template_type": "<template_type>",
        "display_labels": {<option_type>: <display_label>, ...},
        "emblem_catalog": [<emblem_key>, ...],
        "font_catalog": [<font_key>, ...],
        "legacy_print_catalog": [<print_name>, ...],
        "defaults": {
          "display_labels": {<option_type>: <default_display_label>, ...},
          "emblem_catalog": [...],
          "font_catalog": [...],
          "legacy_print_catalog": [...],
        },
      }

    The ``defaults`` sub-dict surfaces the canonical default values
    alongside the resolved values so the chrome can show "currently:
    customized vs default" without re-fetching.

    Raises:
        WorkshopTuneModeNotFound: template_type not registered OR
            company not found.
    """
    descriptor = get_template_type(template_type)
    if descriptor is None:
        raise WorkshopTuneModeNotFound(
            f"Template type {template_type!r} not registered at Workshop "
            f"substrate."
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise WorkshopTuneModeNotFound(f"Company {company_id!r} not found.")

    settings = _settings_dict(company)
    node = _workshop_node(settings, template_type)

    # Display labels live at the existing top-level key per Q1 r74
    # substrate (predates this module). Pull from there + apply
    # defaults for unset option types.
    display_labels_override = settings.get("personalization_display_labels") or {}
    if not isinstance(display_labels_override, dict):
        display_labels_override = {}

    resolved_display_labels: dict[str, str] = {}
    for option_type in CANONICAL_OPTION_TYPES:
        override = display_labels_override.get(option_type)
        resolved_display_labels[option_type] = (
            override
            if isinstance(override, str) and override
            else DEFAULT_DISPLAY_LABELS.get(option_type, option_type)
        )

    # Per-tenant catalog selection: tenant value OR canonical default.
    # Tenant value is a list of catalog keys (subset of canonical
    # default).
    emblem_catalog = node.get(TUNE_DIMENSION_EMBLEM_CATALOG)
    if not isinstance(emblem_catalog, list) or not emblem_catalog:
        emblem_catalog = list(DEFAULT_EMBLEM_CATALOG)

    font_catalog = node.get(TUNE_DIMENSION_FONT_CATALOG)
    if not isinstance(font_catalog, list) or not font_catalog:
        font_catalog = list(DEFAULT_FONT_CATALOG)

    legacy_print_catalog = node.get(TUNE_DIMENSION_LEGACY_PRINT_CATALOG)
    if not isinstance(legacy_print_catalog, list) or not legacy_print_catalog:
        legacy_print_catalog = list(DEFAULT_LEGACY_PRINT_CATALOG)

    return {
        "template_type": template_type,
        TUNE_DIMENSION_DISPLAY_LABELS: resolved_display_labels,
        TUNE_DIMENSION_EMBLEM_CATALOG: emblem_catalog,
        TUNE_DIMENSION_FONT_CATALOG: font_catalog,
        TUNE_DIMENSION_LEGACY_PRINT_CATALOG: legacy_print_catalog,
        "defaults": {
            TUNE_DIMENSION_DISPLAY_LABELS: dict(DEFAULT_DISPLAY_LABELS),
            TUNE_DIMENSION_EMBLEM_CATALOG: list(DEFAULT_EMBLEM_CATALOG),
            TUNE_DIMENSION_FONT_CATALOG: list(DEFAULT_FONT_CATALOG),
            TUNE_DIMENSION_LEGACY_PRINT_CATALOG: list(DEFAULT_LEGACY_PRINT_CATALOG),
        },
        "vinyl_symbols": list(VINYL_SYMBOLS),
    }


# ─────────────────────────────────────────────────────────────────────
# Tenant config update
# ─────────────────────────────────────────────────────────────────────


def update_tenant_personalization_config(
    db: Session,
    *,
    company_id: str,
    template_type: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update the per-tenant Tune mode configuration for a template-type.

    Partial-update semantics: only dimensions present in ``updates``
    are written; absent dimensions remain at their existing tenant
    override (or canonical default).

    **Tune mode boundary discipline** per §3.26.11.12.19.2:

    - ``display_labels`` keys must be in ``CANONICAL_OPTION_TYPES``
      (delegated to ``set_display_labels_for_tenant`` which raises
      ``ValueError``).
    - ``emblem_catalog`` / ``font_catalog`` / ``legacy_print_catalog``
      values must be subsets of their respective canonical-default
      catalogs (Tune mode cannot add catalog entries; only select
      subset).
    - Dimension keys must be in ``descriptor.tune_mode_dimensions``
      (rejects unknown dimensions with WorkshopTuneModeBoundaryViolation).

    Returns the resolved post-update config (same shape as
    ``get_tenant_personalization_config``).

    Raises:
        WorkshopTuneModeNotFound: template_type not registered OR
            company not found.
        WorkshopTuneModeBoundaryViolation: ``updates`` contains an
            unknown dimension key OR a value outside the canonical
            default catalog.
    """
    descriptor = get_template_type(template_type)
    if descriptor is None:
        raise WorkshopTuneModeNotFound(
            f"Template type {template_type!r} not registered."
        )

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise WorkshopTuneModeNotFound(f"Company {company_id!r} not found.")

    permitted_dimensions = set(descriptor.tune_mode_dimensions)
    unknown = set(updates.keys()) - permitted_dimensions
    if unknown:
        raise WorkshopTuneModeBoundaryViolation(
            f"Unknown Tune mode dimension(s) {sorted(unknown)!r} for "
            f"template_type {template_type!r}; permitted: "
            f"{sorted(permitted_dimensions)!r}. Anti-pattern 9 guard at "
            f"service substrate per §2.4.4."
        )

    settings = _settings_dict(company)

    # Display labels — delegate to existing r74 helper for boundary
    # enforcement (raises ValueError on non-canonical option types).
    if TUNE_DIMENSION_DISPLAY_LABELS in updates:
        labels_update = updates[TUNE_DIMENSION_DISPLAY_LABELS]
        if not isinstance(labels_update, dict):
            raise WorkshopTuneModeBoundaryViolation(
                f"display_labels must be a dict; got {type(labels_update).__name__}"
            )
        try:
            set_display_labels_for_tenant(settings, labels_update)
        except ValueError as exc:
            raise WorkshopTuneModeBoundaryViolation(str(exc)) from exc

    # Per-template Tune mode dimensions live under settings.workshop[template_type].
    workshop = settings.get("workshop") or {}
    if not isinstance(workshop, dict):
        workshop = {}
    node = workshop.get(template_type) or {}
    if not isinstance(node, dict):
        node = {}

    if TUNE_DIMENSION_EMBLEM_CATALOG in updates:
        node[TUNE_DIMENSION_EMBLEM_CATALOG] = _validate_subset(
            updates[TUNE_DIMENSION_EMBLEM_CATALOG],
            DEFAULT_EMBLEM_CATALOG,
            dimension_name=TUNE_DIMENSION_EMBLEM_CATALOG,
        )

    if TUNE_DIMENSION_FONT_CATALOG in updates:
        node[TUNE_DIMENSION_FONT_CATALOG] = _validate_subset(
            updates[TUNE_DIMENSION_FONT_CATALOG],
            DEFAULT_FONT_CATALOG,
            dimension_name=TUNE_DIMENSION_FONT_CATALOG,
        )

    if TUNE_DIMENSION_LEGACY_PRINT_CATALOG in updates:
        node[TUNE_DIMENSION_LEGACY_PRINT_CATALOG] = _validate_subset(
            updates[TUNE_DIMENSION_LEGACY_PRINT_CATALOG],
            DEFAULT_LEGACY_PRINT_CATALOG,
            dimension_name=TUNE_DIMENSION_LEGACY_PRINT_CATALOG,
        )

    workshop[template_type] = node
    settings["workshop"] = workshop

    # Persist via Company.settings_json Text-as-JSON substrate.
    company.settings_json = json.dumps(settings)
    db.flush()

    logger.info(
        "workshop.update_tenant_personalization_config: company=%s "
        "template=%s dimensions_written=%s",
        company_id,
        template_type,
        sorted(updates.keys()),
    )

    return get_tenant_personalization_config(
        db, company_id=company_id, template_type=template_type
    )


def _validate_subset(
    value: Any,
    canonical_default: tuple[str, ...],
    *,
    dimension_name: str,
) -> list[str]:
    """Validate that ``value`` is a list subset of ``canonical_default``.

    Tune mode boundary discipline: per-tenant catalog must be a subset
    of the canonical-default catalog. Empty list resets to canonical
    default at read time. Order from caller is preserved (tenant
    operators may reorder catalog entries).
    """
    if not isinstance(value, list):
        raise WorkshopTuneModeBoundaryViolation(
            f"{dimension_name} must be a list; got {type(value).__name__}"
        )
    # Type check first (precedence over subset check) — surfaces clearer
    # error message when caller supplies non-string entries vs unknown
    # string entries.
    for v in value:
        if not isinstance(v, str):
            raise WorkshopTuneModeBoundaryViolation(
                f"{dimension_name} entries must be strings; got "
                f"{type(v).__name__}"
            )
    canonical_set = set(canonical_default)
    bad = [v for v in value if v not in canonical_set]
    if bad:
        raise WorkshopTuneModeBoundaryViolation(
            f"{dimension_name} contains values not in canonical default: "
            f"{sorted(set(bad))}. Canonical default: {list(canonical_default)}. "
            f"Anti-pattern 9 guard — Tune mode cannot add catalog entries; "
            f"subset selection only."
        )
    seen: set[str] = set()
    deduped: list[str] = []
    for v in value:
        if v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped

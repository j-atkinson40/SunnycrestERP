"""R-8.y.d — Plugin Registry browser introspection endpoint.

Single canonical endpoint surfacing live registry state for every
introspectable plugin category. Non-introspectable categories return
a typed "reason" field with the expected implementation count so the
browser UI can render contract-only state with a coherent banner.

Mounted at `/api/platform/admin/plugin-registry/...` under the
platform router (PlatformUser auth via `get_current_platform_user`).

Architectural pattern: documentation-as-canonical-data — the
contract structure of PLUGIN_CONTRACTS.md drives the response
shape's discriminator. Future migrations flip the
`registry_introspectable` flag without changing the canonical
response shape.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_platform_user
from app.models.platform_user import PlatformUser
from app.services.plugin_registry import (
    CATEGORY_CATALOG,
    get_category_introspection,
    list_category_keys,
)


logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Response shape (canonical across all 24 categories) ─────────────


class _RegistrationEntry(BaseModel):
    key: str
    metadata: dict[str, Any]


class _CategoryRegistrationsResponse(BaseModel):
    category_key: str
    registry_introspectable: bool
    # Set when introspectable.
    registrations: list[_RegistrationEntry] = Field(default_factory=list)
    registry_size: int = 0
    # Set when NOT introspectable.
    reason: str = ""
    expected_implementations_count: int = 0
    tier_hint: str = ""


class _CategorySummary(BaseModel):
    category_key: str
    registry_introspectable: bool
    expected_implementations_count: int
    tier_hint: str


class _CategoriesListResponse(BaseModel):
    categories: list[_CategorySummary]
    total: int


# ─── Endpoints ───────────────────────────────────────────────────────


@router.get("/categories", response_model=_CategoriesListResponse)
def list_categories(
    _user: PlatformUser = Depends(get_current_platform_user),
) -> _CategoriesListResponse:
    """Enumerate every plugin category in the catalog.

    Lightweight — returns just (key, introspectable, expected_count,
    tier_hint) per category. Detail introspection comes from the
    per-category endpoint below.
    """
    summaries = []
    for key in list_category_keys():
        entry = CATEGORY_CATALOG[key]
        summaries.append(
            _CategorySummary(
                category_key=entry.category_key,
                registry_introspectable=entry.introspectable,
                expected_implementations_count=(
                    entry.expected_implementations_count
                ),
                tier_hint=entry.tier_hint,
            )
        )
    return _CategoriesListResponse(categories=summaries, total=len(summaries))


@router.get(
    "/categories/{category_key}/registrations",
    response_model=_CategoryRegistrationsResponse,
)
def get_category_registrations(
    category_key: str,
    _user: PlatformUser = Depends(get_current_platform_user),
) -> _CategoryRegistrationsResponse:
    """Live introspection for a single category.

    For introspectable categories: dispatches to the catalog's
    callable + returns the canonical registrations payload.

    For non-introspectable categories: returns the canonical
    static-state payload with `registry_introspectable=False` +
    `reason` + `expected_implementations_count`.

    Unknown category_keys → 404.
    """
    entry = get_category_introspection(category_key)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown plugin category '{category_key}'. "
                f"Valid keys are documented in PLUGIN_CONTRACTS.md."
            ),
        )

    if not entry.introspectable:
        return _CategoryRegistrationsResponse(
            category_key=entry.category_key,
            registry_introspectable=False,
            reason=entry.reason,
            expected_implementations_count=(
                entry.expected_implementations_count
            ),
            tier_hint=entry.tier_hint,
        )

    # Introspection callable is set — invoke it. Any exception falls
    # through to a static-only payload with the exception message as
    # the reason, so the browser still renders coherently when a
    # registry has a runtime issue.
    assert entry.callable_fn is not None  # narrow type for mypy
    try:
        registrations, registry_size = entry.callable_fn()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Plugin registry introspection failed for %s", category_key
        )
        return _CategoryRegistrationsResponse(
            category_key=entry.category_key,
            registry_introspectable=False,
            reason=(
                f"Introspection failed at runtime: {type(exc).__name__}: "
                f"{exc}"
            ),
            expected_implementations_count=(
                entry.expected_implementations_count
            ),
            tier_hint=entry.tier_hint,
        )

    return _CategoryRegistrationsResponse(
        category_key=entry.category_key,
        registry_introspectable=True,
        registrations=[
            _RegistrationEntry(key=r["key"], metadata=r["metadata"])
            for r in registrations
        ],
        registry_size=registry_size,
        tier_hint=entry.tier_hint,
    )

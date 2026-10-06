"""Opas Product List and Product pane reads.

⚠️ TENANT-SCOPED AUTH, PLATFORM-TIER DATA. Every caller must be a signed-in tenant user,
and what they read is the PLATFORM catalog — the same 52 variants for every tenant. Only
the personalization availability lookup is tenant-specific, and it is keyed off the
caller's own `company_id` rather than anything in the request, so one tenant cannot read
another's configuration by changing a parameter.

⚠️ READ-ONLY. No route here writes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import catalog_pane_service

router = APIRouter()


@router.get("/variants")
def list_variants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The catalog, ordered for grouping by kind.

    No `response_model`: the shape is DELIBERATELY SPARSE — keys are omitted when the
    underlying value is NULL, and a Pydantic model would re-introduce them as nulls, which
    is the thing the ruling forbids. The sparseness is the contract.
    """
    return {"variants": catalog_pane_service.list_variants(db)}


@router.get("/variants/{variant_template_id}")
def get_variant(
    variant_template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One variant. 404 when unknown — never an empty pane."""
    detail = catalog_pane_service.variant_detail(
        db, variant_template_id, company_id=current_user.company_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown variant_template_id")
    return detail


class ResolveRequest(BaseModel):
    phrase: str


@router.post("/resolve")
def resolve_phrase(
    body: ResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a typed phrase to catalog variants. NEVER picks.

    ⚠️ A THIRD ENDPOINT, WHERE PART 1 SPECIFIED TWO, AND THE REASON IS THAT THE RESOLVER
    IS SERVER-SIDE. Routing a product phrase is required by the dispatch and
    `product_name_resolver` is Python: it strips trademark marks BEFORE NFKD (because NFKD
    decomposes `™` to `TM`), applies a suffix list, parses sizes, and reads
    `platform_product_aliases WHERE is_confirmed IS TRUE`. Reimplementing that in
    TypeScript would be a SECOND IMPLEMENTATION OF THE SAME RULES, free to drift from the
    one the capture engine already resolves through — the "two lists" defect this codebase
    keeps recording. One endpoint over the real resolver instead.

    ⚠️ IT RETURNS THE CANDIDATE SET AND THE DISCRIMINATORS, NOT A CHOICE. `Resolution`
    deliberately yields None for `variant_template_id` when ambiguous; the overlay renders a
    numbered pick from `candidates` and the discriminators say what would narrow it. Neither
    the resolver nor the overlay picks.
    """
    from app.services.product_name_resolver import build_index, resolve

    resolution = resolve(build_index(db), body.phrase)
    return {
        "phrase": resolution.phrase,
        "normalized": resolution.normalized,
        "resolved": resolution.resolved,
        # ⚠️ Always a list, even for one candidate: a caller that special-cased a scalar
        # would have two code paths for one concept, and the one-candidate path is the one
        # that gets exercised.
        "candidates": [
            {
                "variant_template_id": c.variant_template_id,
                "name": c.display_name,
                "kind": c.form,
                **({"option_label": c.option_label} if c.option_label else {}),
                **({"sku": c.sku} if c.sku else {}),
                **({"family_slug": c.family_slug} if c.family_slug else {}),
            }
            for c in resolution.candidates
        ],
        "discriminators": [d.value for d in resolution.discriminators],
    }

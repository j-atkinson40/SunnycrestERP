"""Generation Focus headless dispatch registry — Phase R-6.0a.

Maps ``(focus_id, op_id) → callable`` for workflow-driven invocation.
Each registered callable receives ``(db, *, company_id, **kwargs)``
and returns a canonical line-items payload (the same shape the
interactive Confirm-action surface consumes).

R-6.0a wires Burial Vault Personalization Studio as the first
headless target — three operations all routing into the existing
canonical Phase 1C ``ai_extraction_review`` substrate:

  * ``extract_decedent_info`` — multimodal extraction from
    content_blocks (typically inbound email attachments).
  * ``suggest_layout``        — canvas layout suggestion.
  * ``suggest_text_style``    — font + style suggestion.

Future Generation Focuses register additional entries; engine
dispatch reads the registry, never the focus's interactive UI
modules. Extraction-as-pure-function discipline canonical per
canon §3.26.11.12.21 (Generation Focus extraction is separable
from interactive UI).
"""

from __future__ import annotations

import io
from typing import Any, Callable

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.services.personalization_studio import ai_extraction_review


class HeadlessDispatchError(Exception):
    """Base for headless dispatch failures."""


class UnknownGenerationFocus(HeadlessDispatchError):
    """No headless dispatch entries registered for this focus_id."""


class UnknownGenerationFocusOp(HeadlessDispatchError):
    """The focus_id is registered but has no entry for this op_id."""


# Dispatch signature: callable receives (db, *, company_id, **kwargs)
# and returns the canonical line-items payload dict.
_DispatchFn = Callable[..., dict[str, Any]]


# ── Burial Vault Personalization Studio dispatch entries ──────────


def _bvps_extract_decedent_info(
    db: Session,
    *,
    company_id: str,
    instance_id: str,
    content_blocks: list[dict[str, Any]],
    context_summary: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Headless wrapper around the canonical
    ``personalization_studio.ai_extraction_review.extract_decedent_info``
    function. The interactive surface calls the same underlying
    function — extraction-as-pure-function discipline.
    """
    return ai_extraction_review.extract_decedent_info(
        db,
        instance_id=instance_id,
        company_id=company_id,
        content_blocks=content_blocks,
        context_summary=context_summary,
    )


def _bvps_suggest_layout(
    db: Session,
    *,
    company_id: str,
    instance_id: str,
    **_ignored: Any,
) -> dict[str, Any]:
    return ai_extraction_review.suggest_layout(
        db,
        instance_id=instance_id,
        company_id=company_id,
    )


def _bvps_suggest_text_style(
    db: Session,
    *,
    company_id: str,
    instance_id: str,
    family_preferences: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    return ai_extraction_review.suggest_text_style(
        db,
        instance_id=instance_id,
        company_id=company_id,
        family_preferences=family_preferences,
    )


# ── Legacy Generation dispatch entry (option-3 3b.1) ──────────────


def _legacy_generate_proof(
    db: Session,
    *,
    company_id: str,
    sales_order_id: str | None = None,
    deceased_name: str | None = None,
    dates: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Headless legacy-proof generation — composite the order's text onto a
    proof background via the PURE ``legacy_compositor.composite_layout`` (no R2,
    no persisted instance, no schema). Produces the proof OUTPUT: the rendered
    bytes prove a real proof was made. Returns a JSON-able payload (the engine
    stores step output as JSON, so we return metadata, not raw bytes).

    Refinements (NOT 3b.1): real Wilbert-template backgrounds via R2, and
    persisting the proof to a Document so 3d's email step can attach it. This
    produces a real rendered proof headless, which is what unblocks 3d's
    ``invoke_generation_focus(focus_id='legacy_proof_generation')``.
    """
    from PIL import Image

    from app.services import legacy_compositor as compositor

    name = deceased_name
    if name is None and sales_order_id:
        row = db.execute(
            sql_text(
                "SELECT deceased_name FROM sales_orders "
                "WHERE id = :id AND company_id = :cid"
            ),
            {"id": sales_order_id, "cid": company_id},
        ).first()
        name = row.deceased_name if row else None
    name = name or "In Loving Memory"

    # A neutral proof background (real templates via R2 are the 3b.2 refinement).
    bg = Image.new("RGB", (2400, 1600), (28, 24, 22))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG")

    layout = {
        "photos": [],
        "text": {
            "name": name, "dates": dates or "", "x": 0.5, "y": 0.5,
            "font_size": 0.08, "color": "white",
        },
    }
    proof_bytes = compositor.composite_layout(
        buf.getvalue(), layout, output_width=2400
    )
    return {
        "focus_id": "legacy_proof_generation",
        "op": "generate_proof",
        "proof_generated": True,
        "proof_size_bytes": len(proof_bytes),
        "deceased_name": name,
    }


# ── Registry ──────────────────────────────────────────────────────


HEADLESS_DISPATCH: dict[str, dict[str, _DispatchFn]] = {
    "burial_vault_personalization_studio": {
        "extract_decedent_info": _bvps_extract_decedent_info,
        "suggest_layout": _bvps_suggest_layout,
        "suggest_text_style": _bvps_suggest_text_style,
    },
    "legacy_proof_generation": {
        "generate_proof": _legacy_generate_proof,
    },
}


def dispatch(
    focus_id: str,
    op_id: str,
    *,
    db: Session,
    company_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Invoke a registered headless Generation Focus op.

    Raises:
        UnknownGenerationFocus: focus_id has no registered ops.
        UnknownGenerationFocusOp: focus_id registered but op_id missing.
    """
    focus_entries = HEADLESS_DISPATCH.get(focus_id)
    if focus_entries is None:
        raise UnknownGenerationFocus(
            f"No headless dispatch entries for focus_id='{focus_id}'. "
            f"Registered: {sorted(HEADLESS_DISPATCH.keys())}"
        )
    fn = focus_entries.get(op_id)
    if fn is None:
        raise UnknownGenerationFocusOp(
            f"focus_id='{focus_id}' has no op '{op_id}'. "
            f"Registered ops: {sorted(focus_entries.keys())}"
        )
    return fn(db, company_id=company_id, **kwargs)


def list_dispatch_keys() -> list[tuple[str, str]]:
    """Return every registered (focus_id, op_id) tuple."""
    return [
        (focus_id, op_id)
        for focus_id, ops in HEADLESS_DISPATCH.items()
        for op_id in ops
    ]


__all__ = [
    "HEADLESS_DISPATCH",
    "HeadlessDispatchError",
    "UnknownGenerationFocus",
    "UnknownGenerationFocusOp",
    "dispatch",
    "list_dispatch_keys",
]

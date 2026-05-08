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

from typing import Any, Callable

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


# ── Registry ──────────────────────────────────────────────────────


HEADLESS_DISPATCH: dict[str, dict[str, _DispatchFn]] = {
    "burial_vault_personalization_studio": {
        "extract_decedent_info": _bvps_extract_decedent_info,
        "suggest_layout": _bvps_suggest_layout,
        "suggest_text_style": _bvps_suggest_text_style,
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

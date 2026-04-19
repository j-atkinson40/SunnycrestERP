"""Phase D-6 lint: enforce `Document.visible_to()` on tenant-scoped
Document queries.

The D-6 sharing model is only useful if every read path that could
return shared documents goes through `visible_to()`. A raw
`Document.company_id == X` filter returns only owned documents and
silently drops documents that were shared TO X — a security + UX bug.

This test scans `app/` for code that:
  1. Queries the canonical `Document` model (`db.query(Document)` or
     similar) AND
  2. Filters by `company_id ==` directly AND
  3. Is NOT in the PERMANENT_ALLOWLIST below.

Any new code reading Documents cross-tenant must either use
`Document.visible_to(company_id)` OR add itself to
`PERMANENT_ALLOWLIST` with a justification. The allowlist is the
architectural boundary: owner-only reads that by construction
cannot involve shares.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"


# Permanent allowlist — files that legitimately filter Documents by
# owner company_id without going through visible_to(). Each entry
# carries a justification comment.
#
# The core principle: owner-only operations (write, grant, entity-
# relationship lookup where the operation belongs to the owner) DON'T
# need visible_to. Read operations that could cross tenants DO.
PERMANENT_ALLOWLIST = {
    # Renderer fetches by document_id after already validating ownership
    # — owner-only write path (D-1 renderer creates documents for the
    # owning tenant).
    "app/services/documents/document_renderer.py",
    # Sharing service fetches documents to grant shares from; owner-
    # scoped by design (you can only share documents you own).
    "app/services/documents/document_sharing_service.py",
    # The inbox endpoint DELIBERATELY filters by target_company_id on
    # the share, not by Document.company_id — the filter predicate
    # there IS tenant-aware but via the JOIN, not visible_to().
    # The other query sites in documents_v2.py use visible_to() or
    # the owner-only _get_owned_document_or_404 helper.
    "app/api/routes/documents_v2.py",
    # delivery_service, cross_tenant_statement_service, fh/legacy_vault_print_service
    # all filter by owner company_id when they need to find the
    # Document THEY created to attach a share. They don't expose
    # cross-tenant reads; they just use their own company_id to find
    # their own records.
    "app/services/delivery_service.py",
    "app/services/cross_tenant_statement_service.py",
    "app/services/fh/legacy_vault_print_service.py",
    # D-1 generators — each operates in the owning tenant's context to
    # produce a new Document. Not a cross-tenant read path.
    "app/services/disinterment_pdf_service.py",
    "app/services/pdf_generation_service.py",
    "app/services/price_list_pdf_service.py",
    "app/services/statement_pdf_service.py",
    # D-4/D-5 signing: each operation is owner-scoped (signer-side
    # access goes through signer_token, not Document queries).
    "app/services/signing/certificate_service.py",
    "app/services/signing/signature_renderer.py",
    "app/services/signing/signature_service.py",
    "app/services/signing/notification_service.py",
    # Safety program generator — owner-tenant operation.
    "app/services/safety_program_generation_service.py",
    "app/services/social_service_certificate_service.py",
    # Template loader + service — operate on document_templates, not
    # documents (different table; visible_to is for the documents table).
    "app/services/documents/template_loader.py",
    "app/services/documents/template_service.py",
    # Vault service manages VaultItem.shared_with_company_ids directly;
    # VaultItems aren't Documents so visible_to doesn't apply.
    "app/services/vault_service.py",
    # D-7 delivery service — fetches documents to attach, owner-scoped
    # by design (caller's company_id threaded through SendParams; the
    # service queries Document.id + company_id for the owner's own
    # document to attach). Sending TO another tenant is expressed via
    # the recipient, not by querying documents as that tenant.
    "app/services/delivery/delivery_service.py",
    # Legacy document service (backed by `documents_legacy` table via
    # the legacy Document model) — not the canonical Document.
    "app/services/document_service.py",
    # Legacy document_r2_service — uses `app.models.document.Document`
    # (legacy), not the canonical. Legacy has r2_key + metadata_json
    # columns that don't exist on canonical. Out of scope for the
    # cross-tenant sharing model.
    "app/services/document_r2_service.py",
    # Public signing routes — read documents via signer_token, which
    # already gates visibility per-party. Not a tenant-scoped read.
    "app/api/routes/signing_public.py",
    "app/api/routes/signing_admin.py",
}


# Pattern: `Document.company_id == something`  OR  `Document.company_id.in_(...)`.
# We flag it only when `Document` is the canonical model. The legacy
# `app.models.document.Document` is a different class; we use the
# alias-based usage as a heuristic.
_DOC_COMPANY_PATTERNS = [
    re.compile(r"\bDocument\.company_id\s*==", re.MULTILINE),
    re.compile(r"\bDocument\.company_id\.in_\s*\(", re.MULTILINE),
]

# Pattern hint that visible_to() IS used in the file (reduces false
# positives when a file legitimately uses both — e.g. a service that
# has both owner-only and cross-tenant methods).
_VISIBLE_TO_PATTERN = re.compile(r"Document\.visible_to\s*\(")


def _scan(app_dir: Path) -> dict[str, list[str]]:
    offenders: dict[str, list[str]] = {}
    for py in app_dir.rglob("*.py"):
        relpath = str(py.relative_to(BACKEND))
        if relpath in PERMANENT_ALLOWLIST:
            continue
        text = py.read_text(encoding="utf-8")
        if _VISIBLE_TO_PATTERN.search(text):
            # File uses visible_to() somewhere — we allow direct
            # company_id filters too (owner-only paths). If we want to
            # be stricter in the future, remove this early-exit.
            continue
        hits: list[str] = []
        for pat in _DOC_COMPANY_PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append(f"{relpath}:{line_no} — {m.group(0)!r}")
        if hits:
            offenders[relpath] = hits
    return offenders


def test_document_reads_go_through_visible_to():
    """Canonical Document reads must route through `Document.visible_to()`
    if they can cross tenants. Direct `Document.company_id == X` filters
    are only valid in files on the PERMANENT_ALLOWLIST (owner-only paths)
    OR in files that also reference `visible_to()` (mixed-use files)."""
    offenders = _scan(APP_DIR)
    assert not offenders, (
        "Canonical-Document cross-tenant reads bypass visible_to():\n"
        + "\n".join(
            f"  {path}:\n    " + "\n    ".join(hits)
            for path, hits in offenders.items()
        )
        + "\n\nEither use `Document.visible_to(company_id)` for the "
          "filter, or add this file to PERMANENT_ALLOWLIST with a "
          "justification (it's an owner-only path that by construction "
          "cannot involve cross-tenant shares)."
    )


def test_allowlist_files_exist():
    missing = [f for f in PERMANENT_ALLOWLIST if not (BACKEND / f).exists()]
    assert not missing, (
        f"PERMANENT_ALLOWLIST contains stale entries: {missing}"
    )

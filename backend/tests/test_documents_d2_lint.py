"""Phase D-2 lint tests — enforce the weasyprint ban outside the
Documents package.

Ruff isn't installed in this project, so the policy is mirrored as a
pytest scanner (same pattern as test_intelligence_phase2c0a_lint.py).

Rule: `weasyprint` imports and `weasyprint.HTML(...)` / `HTML(...)`
instantiations are forbidden anywhere under `backend/app/` EXCEPT the
permanent allowlist below.

When a legacy generator is migrated to route through
`document_renderer`, no allowlist entry is needed — the migration just
needs to stop touching weasyprint directly. Any file that still reaches
for weasyprint after migration = regression.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"

# Permanent allowlist — files authorized to touch weasyprint forever.
PERMANENT_ALLOWLIST = {
    # The managed renderer backbone — everything else routes through here.
    "app/services/documents/document_renderer.py",
    # Diagnostic import-only startup check — logs WeasyPrint availability
    # at process start so missing system deps surface in logs. Never calls
    # HTML(...) / write_pdf().
    "app/main.py",
}

# Transitional allowlist — migrated in a future phase.
#
# D-1 migrated 4 generators (invoice, price_list, statement, disinterment).
# D-2 migrated 3 generators (social_service_cert, legacy_vault_print,
# safety_program) + all email templates. These 3 remain on direct
# WeasyPrint and are called out as follow-ups:
#
#   pdf_generation_service.py::generate_template_preview_pdf — admin
#     template-preview tool (not production output). Migrating requires
#     routing the preview through document_renderer.render_pdf_bytes
#     with a tenant-scoped placeholder company for the DB lookup.
#
#   quote_service.py::generate_quote_pdf — standalone 500-line inline
#     HTML quote generator. Needs its own template_key ("quote.default")
#     + seed migration, out of D-2 scope.
#
#   wilbert_utils.py — Wilbert engraving form PDF. Needs template_key
#     "urn.wilbert_engraving_form".
TRANSITIONAL_ALLOWLIST = {
    "app/services/pdf_generation_service.py",
    "app/services/quote_service.py",
    "app/services/wilbert_utils.py",
}

ALLOWLIST = PERMANENT_ALLOWLIST | TRANSITIONAL_ALLOWLIST


_WEASYPRINT_PATTERNS = [
    re.compile(r"^\s*import\s+weasyprint\b", re.MULTILINE),
    re.compile(r"^\s*from\s+weasyprint\s+import\b", re.MULTILINE),
    # Explicit `weasyprint.HTML(...)` calls.
    re.compile(r"\bweasyprint\.HTML\s*\("),
]


def _scan(app_dir: Path) -> dict[str, list[str]]:
    """Return {relpath: [match_descriptions]} for every file outside the allowlist."""
    offenders: dict[str, list[str]] = {}
    for py in app_dir.rglob("*.py"):
        relpath = str(py.relative_to(BACKEND))
        if relpath in ALLOWLIST:
            continue
        text = py.read_text(encoding="utf-8")
        hits: list[str] = []
        for pat in _WEASYPRINT_PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append(f"{relpath}:{line_no} — {m.group(0).strip()!r}")
        if hits:
            offenders[relpath] = hits
    return offenders


def test_no_direct_weasyprint_outside_documents():
    """WeasyPrint imports/instantiations are forbidden outside
    app/services/documents/**. Migrated services route through
    document_renderer.render() or document_renderer.render_pdf_bytes()."""
    offenders = _scan(APP_DIR)
    assert not offenders, (
        "Direct weasyprint usage detected outside the Documents package:\n"
        + "\n".join(
            f"  {path}:\n    " + "\n    ".join(hits)
            for path, hits in offenders.items()
        )
        + "\n\nEither migrate the caller to document_renderer.render() / "
          "render_pdf_bytes() using a managed template_key, or — if the "
          "caller is queued for a future phase — add it to "
          "TRANSITIONAL_ALLOWLIST with a justification."
    )


def test_allowlist_files_exist():
    """Every file in PERMANENT_ALLOWLIST + TRANSITIONAL_ALLOWLIST must
    still exist — stale entries let regressions hide."""
    missing = [f for f in ALLOWLIST if not (BACKEND / f).exists()]
    assert not missing, (
        f"Allowlist contains stale entries: {missing}. Either add the "
        "files back or remove from ALLOWLIST."
    )


def test_transitional_allowlist_files_still_use_weasyprint():
    """Each transitional-allowlist entry must still actually use weasyprint.
    Once migrated, the entry should be REMOVED — keeping it hides regressions."""
    stale: list[str] = []
    for relpath in TRANSITIONAL_ALLOWLIST:
        text = (BACKEND / relpath).read_text(encoding="utf-8")
        if not any(p.search(text) for p in _WEASYPRINT_PATTERNS):
            stale.append(relpath)
    assert not stale, (
        f"{stale} no longer use weasyprint — remove from TRANSITIONAL_ALLOWLIST."
    )

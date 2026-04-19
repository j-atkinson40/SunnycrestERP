"""Phase 2c-0a lint tests — enforce TID251/TID252 policy in pytest form.

Ruff isn't installed in this project, so we replicate the policy as a pytest
scanner. Two rules:

  TID251 — no `from app.services.ai_service import call_anthropic` (enforced
           already by tests/test_intelligence_phase2a_lint.py for Phase 2a files)

  TID252 — no direct anthropic SDK usage outside the permanent allowlist +
           the Phase 2c temporary allowlist. This test encodes that rule.

As each Phase 2c sub-phase migrates a caller, the corresponding entry must be
REMOVED from TEMPORARY_ALLOWLIST below. The test fails if a file outside both
allowlists instantiates `anthropic.Anthropic` or `anthropic.AsyncAnthropic`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"

# Permanent allowlist — these files are authorized to import/instantiate the SDK.
#
# NOTE: ai_service.py was deleted in Phase 2c-5. If it reappears in the
# codebase, that's a regression — _scan will flag it.
PERMANENT_ALLOWLIST = {
    # The Intelligence backbone (owns the SDK abstraction)
    "app/services/intelligence/__init__.py",
    "app/services/intelligence/chat_service.py",
    "app/services/intelligence/cost_service.py",
    "app/services/intelligence/experiment_service.py",
    "app/services/intelligence/extraction_service.py",
    "app/services/intelligence/intelligence_service.py",
    "app/services/intelligence/model_router.py",
    "app/services/intelligence/prompt_registry.py",
    "app/services/intelligence/prompt_renderer.py",
    # Admin chat preserves streaming UX via AsyncAnthropic but uses managed prompts
    "app/api/routes/admin/chat.py",
}

# Temporary allowlist — Category C callers queued for Phase 2c-1..2c-4.
# Each entry is REMOVED when the corresponding caller migrates.
#
# Phase 2c-1 complete: accounting_analysis_service, agent_service,
#   price_list_analysis_service, sales_service, price_list_extraction_service.
# Phase 2c-2 complete: first_call_extraction_service, website_analysis_service,
#   customer_classification_service, training_content_generation_service,
#   journal_entries, accounting_connection, reports, order_station,
#   financials_board.
#
# Category C is now fully migrated (14/14). Remaining Category B migrations
# (Phase 2c-3 + 2c-4) use ai_service.call_anthropic, which the shim already
# audits — they don't need entries in this allowlist.
TEMPORARY_ALLOWLIST: set[str] = set()

# Retired entries — removed during Phase 2c-2 (kept here as a comment block
# for migration archeology; do NOT re-add):
_RETIRED_2C_1 = {  # noqa: F841 — archive
    "app/services/accounting_analysis_service.py",
    "app/services/agent_service.py",
    "app/services/price_list_analysis_service.py",
    "app/services/sales_service.py",
    "app/services/price_list_extraction_service.py",
}
_RETIRED_2C_2 = {  # noqa: F841 — archive
    "app/services/first_call_extraction_service.py",
    "app/services/training_content_generation_service.py",
    "app/services/website_analysis_service.py",
    "app/services/customer_classification_service.py",
    "app/api/routes/journal_entries.py",
    "app/api/routes/accounting_connection.py",
    "app/api/routes/reports.py",
    "app/api/routes/order_station.py",
    "app/api/routes/financials_board.py",
}

ALLOWLIST = PERMANENT_ALLOWLIST | TEMPORARY_ALLOWLIST


_SDK_PATTERNS = [
    re.compile(r"^\s*import\s+anthropic\b", re.MULTILINE),
    re.compile(r"^\s*from\s+anthropic\s+import\b", re.MULTILINE),
    re.compile(r"\banthropic\.Anthropic\s*\("),
    re.compile(r"\banthropic\.AsyncAnthropic\s*\("),
    re.compile(r"\bAsyncAnthropic\s*\("),
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
        for pat in _SDK_PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append(f"{relpath}:{line_no} — {m.group(0).strip()!r}")
        if hits:
            offenders[relpath] = hits
    return offenders


def test_no_direct_sdk_outside_allowlist():
    """Direct anthropic SDK imports/instantiations are forbidden outside the allowlist."""
    offenders = _scan(APP_DIR)
    assert not offenders, (
        "Direct anthropic SDK usage detected outside the allowlist:\n"
        + "\n".join(
            f"  {path}:\n    " + "\n    ".join(hits) for path, hits in offenders.items()
        )
        + "\n\nEither migrate the caller to intelligence_service.execute() or, "
          "if temporarily unavoidable, add the file to TEMPORARY_ALLOWLIST with a "
          "reason — knowing the allowlist is expected to SHRINK to zero by Phase 2c-5."
    )


def test_temporary_allowlist_files_exist():
    """Every file in TEMPORARY_ALLOWLIST must still exist (stale entries are bugs)."""
    missing = [f for f in TEMPORARY_ALLOWLIST if not (BACKEND / f).exists()]
    assert not missing, (
        f"Temporary allowlist contains stale entries: {missing}. "
        f"If these were migrated, remove them from the allowlist."
    )


def test_config_key_is_uppercase():
    """Phase 2c-0a fix — all config access must use settings.ANTHROPIC_API_KEY."""
    lowercase_hits: list[str] = []
    pattern = re.compile(r"settings\.anthropic_api_key\b")
    for py in APP_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            lowercase_hits.append(f"{py.relative_to(BACKEND)}:{line_no}")
    assert not lowercase_hits, (
        "settings.anthropic_api_key (lowercase) found — use ANTHROPIC_API_KEY:\n  "
        + "\n  ".join(lowercase_hits)
    )


@pytest.mark.parametrize("relpath", sorted(TEMPORARY_ALLOWLIST))
def test_temporary_allowlist_file_has_sdk_use(relpath):
    """Sanity check — each temp-allowlisted file must actually use the SDK
    (otherwise the entry is noise and should be removed)."""
    path = BACKEND / relpath
    text = path.read_text(encoding="utf-8")
    uses_sdk = any(p.search(text) for p in _SDK_PATTERNS)
    assert uses_sdk, (
        f"{relpath} is in TEMPORARY_ALLOWLIST but no longer uses the anthropic "
        f"SDK. Remove it from the allowlist."
    )

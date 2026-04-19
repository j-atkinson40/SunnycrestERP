"""Lint test — enforce Phase 2a migrated callers never reintroduce call_anthropic.

This parallels the ruff TID251 rule in ruff.toml. We do it as a pytest so the
policy is enforced today without adding a ruff dependency. Phase 2b will widen
the "must not call" list as more callers migrate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent

# Files that Phase 2a/2b migrated — if any of these ever re-import or call
# `ai_service.call_anthropic`, this test fails loudly. Phase 2c will extend
# this list as more long-tail callers migrate.
PHASE_2A_MIGRATED_FILES = [
    # Phase 2a
    "app/services/agents/ar_collections_agent.py",
    "app/services/agents/expense_categorization_agent.py",
    "app/services/fh/scribe_service.py",
    "app/services/fh/story_thread_service.py",
    "app/services/briefing_service.py",
    "app/services/safety_program_generation_service.py",
    "app/services/command_bar_extract_service.py",
    "app/api/routes/admin/chat.py",
    # Phase 2b
    "app/services/urn_product_service.py",
]

# Files that are allowed to reference call_anthropic:
#   - ai_service.py itself (the deprecated wrapper)
#   - tests
ALLOWLIST = [
    "app/services/ai_service.py",
    "tests/",
]


_CALL_ANTHROPIC_PATTERNS = [
    re.compile(r"\bai_service\.call_anthropic\b"),
    re.compile(r"\bfrom\s+app\.services\.ai_service\s+import\b"),
    re.compile(r"\bfrom\s+app\.services\s+import\s+ai_service\b"),
    re.compile(r"\bcall_anthropic\("),
]


def _has_violation(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    hits: list[str] = []
    for pat in _CALL_ANTHROPIC_PATTERNS:
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append(f"{path.relative_to(BACKEND)}:{line_no} — {m.group(0)!r}")
    return hits


@pytest.mark.parametrize("relpath", PHASE_2A_MIGRATED_FILES)
def test_phase_2a_file_has_no_call_anthropic_references(relpath):
    """Each Phase 2a migrated file must be free of call_anthropic references."""
    path = BACKEND / relpath
    assert path.exists(), f"Migrated file not found: {relpath}"
    hits = _has_violation(path)
    assert not hits, (
        f"{relpath} still has call_anthropic references:\n  "
        + "\n  ".join(hits)
        + "\nThis file was migrated in Phase 2a — use "
          "`intelligence_service.execute(prompt_key=...)` instead."
    )


def test_ai_service_module_is_deleted():
    """Phase 2c-5 invariant — ai_service.py was deleted. If it reappears,
    that's a regression; the migration is complete and every caller routes
    through intelligence_service.execute with a managed prompt."""
    path = BACKEND / "app/services/ai_service.py"
    assert not path.exists(), (
        "app/services/ai_service.py should have been deleted in Phase 2c-5. "
        "If it has been reintroduced, that's a regression — remove it and "
        "route any callers through app.services.intelligence.intelligence_service.execute()."
    )

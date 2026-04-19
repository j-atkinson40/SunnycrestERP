"""Phase 2c-0a frontend lint — forbid new callers of /api/ai/prompt.

The legacy /api/ai/prompt endpoint is slated for deprecation in Phase 2c-3
(see backend/docs/intelligence_audit_v3.md, Category B, ai.py:ai_prompt). This
test maintains an allowlist of existing callers captured at the Phase 2c-0a
boundary. Any new caller introduced after this build must go through
/api/v1/intelligence or a managed prompt instead.

The allowlist SHRINKS as each existing caller is migrated or deleted in 2c-3.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND_SRC = BACKEND.parent / "frontend" / "src"

# Captured at Phase 2c-0a boundary (2026-04-18). Each entry must be removed
# when the caller is migrated or the file deleted.
#
# Phase 2c-3 status:
#   The backend /ai/prompt endpoint is now deprecated (Deprecation + Sunset
#   headers, log.warning on each call, audit row via legacy shim). The
#   frontend caller below is the last consumer.
#
#   AICommandBar (components/ai-command-bar.tsx) consumes ai-service.sendPrompt
#   and is used on pages/products.tsx for AI product search. Replacing this
#   component with a managed-prompt-backed equivalent is a dedicated cleanup
#   task (requires a new backend endpoint calling intelligence_service.execute
#   with a managed prompt_key for product search, then removing AICommandBar's
#   systemPrompt prop entirely).
#
# Sunset date: 2027-04-18 (documented in backend/app/api/routes/ai.py).
FRONTEND_ALLOWLIST = {
    # services/ai-service.ts wraps /ai/prompt — consumed by AICommandBar on
    # pages/products.tsx. Scheduled for frontend refactor before Sunset.
    ("src/services/ai-service.ts", 23),
}


# Match apiClient.post("/ai/prompt"...) or fetch("/ai/prompt"...) or string
# literal containing /ai/prompt or /api/ai/prompt
_PATTERNS = [
    re.compile(r'["\'`]/ai/prompt["\'`]'),
    re.compile(r'["\'`]/api/ai/prompt["\'`]'),
]


def _scan() -> list[tuple[str, int, str]]:
    """Return list of (relpath, line_no, match) for all /ai/prompt references."""
    hits: list[tuple[str, int, str]] = []
    if not FRONTEND_SRC.exists():
        return hits
    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for path in FRONTEND_SRC.rglob(ext):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for pat in _PATTERNS:
                for m in pat.finditer(text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    rel = str(path.relative_to(FRONTEND_SRC.parent))
                    hits.append((rel, line_no, m.group(0)))
    return hits


def test_no_new_ai_prompt_callers():
    """Every hit must be on the allowlist; no new callers without review."""
    hits = _scan()
    unexpected = [
        (path, line, match)
        for (path, line, match) in hits
        if (path, line) not in FRONTEND_ALLOWLIST
    ]
    assert not unexpected, (
        "New /api/ai/prompt callers detected in frontend — this endpoint is "
        "slated for deprecation in Phase 2c-3. Route new callers through "
        "/api/v1/intelligence with a managed prompt:\n  "
        + "\n  ".join(f"{p}:{ln} — {m}" for (p, ln, m) in unexpected)
    )


def test_frontend_allowlist_entries_still_exist():
    """Sanity check — stale allowlist entries (caller was deleted) indicate
    migration progress that should be reflected by removing the entry."""
    hits = _scan()
    seen = {(p, ln) for (p, ln, _) in hits}
    missing = sorted(FRONTEND_ALLOWLIST - seen)
    assert not missing, (
        f"FRONTEND_ALLOWLIST entries no longer present in the source — "
        f"remove them: {missing}"
    )

"""Phase 2c-5 — final cleanup invariants.

These tests enforce the post-migration state. If any of them fail, the
Intelligence migration has regressed — figure out which layer broke and
restore the invariant.

Invariants enforced:
  1. ai_service.py is deleted
  2. Zero production code references call_anthropic (only the backbone's
     internal _call_anthropic helper remains, and that's inside the
     intelligence package)
  3. Zero production code writes IntelligenceExecution(prompt_id=None, ...)
     (the legacy shim that did this is gone with ai_service.py)
  4. The three Phase 2c-5 prompts are seeded and active:
       extraction.inventory_command, extraction.ap_command, legacy.arbitrary_prompt
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"


def test_ai_service_module_is_deleted():
    """Phase 2c-5 deleted app/services/ai_service.py."""
    assert not (APP_DIR / "services" / "ai_service.py").exists(), (
        "ai_service.py has been reintroduced — this is a regression. "
        "Every caller should route through "
        "app.services.intelligence.intelligence_service.execute()."
    )


def test_no_call_anthropic_in_production_code():
    """After Phase 2c-5, `call_anthropic` appears in exactly one .py file:
    intelligence/intelligence_service.py (the private SDK wrapper)."""
    allowed = {"app/services/intelligence/intelligence_service.py"}
    violations: list[str] = []
    for py in APP_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "call_anthropic" in text:
            relpath = str(py.relative_to(BACKEND))
            if relpath not in allowed:
                violations.append(relpath)
    assert not violations, (
        "Unexpected call_anthropic references after Phase 2c-5:\n  "
        + "\n  ".join(violations)
    )


def test_no_null_prompt_id_writes_in_production_code():
    """No production code path writes IntelligenceExecution with prompt_id=None.

    The legacy shim that produced null-prompt_id audit rows lived in
    `ai_service._log_legacy_execution` — that function was deleted in 2c-5
    when the file was removed. Any new null-prompt_id write path indicates
    a caller that bypasses the Intelligence layer, which is a regression.

    Test mechanism: scan all non-intelligence .py files for patterns that
    construct IntelligenceExecution with a literal prompt_id=None.
    """
    # Files allowed to construct IntelligenceExecution rows — all of them
    # use the managed prompt version lookup, not literal None.
    allowed_dirs = ("app/services/intelligence/", "app/api/routes/intelligence.py")
    pattern = re.compile(
        r"IntelligenceExecution\s*\([^)]*prompt_id\s*=\s*None",
        re.DOTALL,
    )
    violations: list[str] = []
    for py in APP_DIR.rglob("*.py"):
        relpath = str(py.relative_to(BACKEND))
        if any(relpath.startswith(d) for d in allowed_dirs):
            continue
        text = py.read_text(encoding="utf-8")
        if pattern.search(text):
            violations.append(relpath)
    assert not violations, (
        "Production code writes IntelligenceExecution with prompt_id=None:\n  "
        + "\n  ".join(violations)
        + "\nThis bypasses the Intelligence layer's managed prompt registry. "
          "Route through intelligence_service.execute() with a managed prompt_key."
    )


@pytest.mark.parametrize(
    "prompt_key",
    [
        "extraction.inventory_command",
        "extraction.ap_command",
        "legacy.arbitrary_prompt",
    ],
)
def test_phase_2c5_prompts_seeded_via_source(prompt_key):
    """Phase 2c-5 seed script declares each of the 3 new prompts.

    Source-level check (doesn't require live DB) — verifies the seed script
    contains a SPECS entry for each expected prompt_key."""
    seed_path = BACKEND / "scripts" / "seed_intelligence_phase2c5.py"
    assert seed_path.exists(), "Phase 2c-5 seed script missing"
    text = seed_path.read_text(encoding="utf-8")
    assert f'"prompt_key": "{prompt_key}"' in text, (
        f"Seed script missing SPECS entry for {prompt_key}"
    )


def test_ai_routes_use_managed_prompts():
    """api/routes/ai.py — the 3 previously call_anthropic-backed routes
    (ai_prompt, parse_inventory, parse_ap) must now route through
    intelligence_service.execute with the 3 Phase 2c-5 prompts."""
    source = (APP_DIR / "api" / "routes" / "ai.py").read_text(encoding="utf-8")
    expected = {
        "legacy.arbitrary_prompt": "ai.ai_prompt",
        "extraction.inventory_command": "ai.parse_inventory",
        "extraction.ap_command": "ai.parse_ap",
    }
    for prompt_key, caller_module in expected.items():
        assert f'prompt_key="{prompt_key}"' in source, (
            f"ai.py does not invoke managed prompt {prompt_key}"
        )
        assert f'caller_module="{caller_module}"' in source, (
            f"ai.py caller_module={caller_module} missing"
        )


def test_ruff_toml_permanent_allowlist_current():
    """ruff.toml's per-file-ignores reflects the post-deletion state."""
    ruff_path = BACKEND / "ruff.toml"
    text = ruff_path.read_text(encoding="utf-8")
    # ai_service.py entry must be gone (file is deleted)
    assert '"app/services/ai_service.py"' not in text, (
        "ruff.toml still has the deleted ai_service.py in per-file-ignores"
    )
    # Intelligence backbone + admin/chat + tests + scripts must remain
    assert '"app/services/intelligence/**"' in text
    assert '"app/api/routes/admin/chat.py"' in text
    assert '"tests/**"' in text
    assert '"scripts/**"' in text

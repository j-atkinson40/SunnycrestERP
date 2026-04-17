"""Playwright script registry.

Add new scripts here and they automatically become available as
workflow step types. The ``script_name`` in the workflow step config
must match a key in ``PLAYWRIGHT_SCRIPTS``.
"""
from __future__ import annotations

from app.services.playwright_scripts.base import PlaywrightScript, PlaywrightScriptError
from app.services.playwright_scripts.uline_order import UlineOrderScript

PLAYWRIGHT_SCRIPTS: dict[str, type[PlaywrightScript]] = {
    "uline_place_order": UlineOrderScript,
    # Future:
    # "staples_place_order": StaplesOrderScript,
    # "grainger_place_order": GraingerOrderScript,
    # "ss_certificate_submit": SSCertificateScript,
    # "insurance_assignment": InsuranceAssignmentScript,
}


def get_script(name: str) -> PlaywrightScript | None:
    """Return an instantiated script for ``name``, or None."""
    cls = PLAYWRIGHT_SCRIPTS.get(name)
    return cls() if cls else None


def list_scripts() -> list[dict]:
    """Return metadata for all registered scripts (for UI dropdowns)."""
    return [
        {
            "name": cls.name,
            "service_key": cls.service_key,
            "required_inputs": cls.required_inputs,
            "outputs": cls.outputs,
        }
        for cls in PLAYWRIGHT_SCRIPTS.values()
    ]


__all__ = [
    "PlaywrightScript",
    "PlaywrightScriptError",
    "PLAYWRIGHT_SCRIPTS",
    "get_script",
    "list_scripts",
]

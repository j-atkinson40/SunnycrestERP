"""Phase D-7 lint: `resend` imports forbidden outside EmailChannel.

The delivery abstraction is only useful if provider-specific code lives
in exactly one place. Any new code reaching for the Resend SDK directly
undermines the abstraction — it means we have parallel send paths that
DeliveryService doesn't see.

This test scans `app/` for `import resend` / `from resend import` /
`resend.Emails.send(...)` usages. Any occurrence outside the allowlist
is a regression.

When native email replaces Resend, the allowlist switches to the new
channel implementation and the rule stays — we're defending the
architectural boundary, not a specific provider.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"


PERMANENT_ALLOWLIST = {
    # The ONLY place authorized to touch `resend` for SENDING. When
    # native email ships, this entry becomes the new channel file and
    # Resend disappears.
    "app/services/delivery/channels/email_channel.py",
    # Domain verification uses Resend's `Domains.create/get` — this is
    # provider-admin work (adding a tenant's custom sending domain),
    # not message sending. Legitimate Resend-specific API; not in scope
    # of the delivery abstraction. When native email ships, domain
    # verification either moves to the new provider's equivalent or
    # stays separate depending on how native email handles custom
    # sending domains.
    "app/api/routes/legacy_email.py",
}


_RESEND_PATTERNS = [
    # Flag any import of resend — even if downstream usage is domain
    # admin only, routing new code past the lint gate is the wrong
    # default. Files with legitimate provider-specific non-send usage
    # (domain verification, account admin) go on the allowlist.
    re.compile(r"^\s*import\s+resend\b", re.MULTILINE),
    re.compile(r"^\s*from\s+resend\s+import\b", re.MULTILINE),
    re.compile(r"\bresend\.Emails\.send\b"),
]


def _scan(app_dir: Path) -> dict[str, list[str]]:
    offenders: dict[str, list[str]] = {}
    for py in app_dir.rglob("*.py"):
        relpath = str(py.relative_to(BACKEND))
        if relpath in PERMANENT_ALLOWLIST:
            continue
        text = py.read_text(encoding="utf-8")
        hits: list[str] = []
        for pat in _RESEND_PATTERNS:
            for m in pat.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append(f"{relpath}:{line_no} — {m.group(0).strip()!r}")
        if hits:
            offenders[relpath] = hits
    return offenders


def test_no_direct_resend_outside_email_channel():
    offenders = _scan(APP_DIR)
    assert not offenders, (
        "Direct Resend usage detected outside EmailChannel:\n"
        + "\n".join(
            f"  {path}:\n    " + "\n    ".join(hits)
            for path, hits in offenders.items()
        )
        + "\n\nRoute through `delivery_service.send(...)` instead. If "
          "this file genuinely needs provider-specific access (rare), "
          "add it to PERMANENT_ALLOWLIST with justification."
    )


def test_allowlist_files_exist():
    missing = [f for f in PERMANENT_ALLOWLIST if not (BACKEND / f).exists()]
    assert not missing, (
        f"PERMANENT_ALLOWLIST contains stale entries: {missing}"
    )

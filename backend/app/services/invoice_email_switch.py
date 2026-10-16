"""Whether a tenant may email invoices at all.

James's ruling, 2026-10-16 (step 2, item 5): "Sending stays behind a tenant switch that is
OFF for Sunnycrest. Invoices are created but nothing is emailed until James turns it on."

The switch is `invoice_email_enabled` in `Company.settings_json`, **default False**.

⚠️ WHAT IS AND IS NOT WITHHELD. The invoice is still created, still posted to AR, still
reaches the month's statement. Only the per-invoice EMAIL is withheld. A funeral home on
`statement_only` was never going to be emailed anyway (`approve_invoice` sets such an
invoice to `open` and skips the send); this switch covers the case where somebody sets a
customer to `invoice_immediately` before the tenant is ready to have mail leaving.

⚠️ DEFAULT-OFF IS THE WHOLE POINT, AND IT IS THE OPPOSITE OF HOW DEFAULTS HAVE GONE HERE.
`delivery_settings.invoice_generation_mode` defaults to `"end_of_day"` and
`require_driver_status_updates` to `False`, and every production tenant runs both — not by
choosing them but because `get_settings` creates the row with the model's defaults and
nobody ever edited it (`modified_at` is NULL on Sunnycrest's row). A default that sends
mail would be acquired the same way: silently, by a tenant that never opted in. So the
absence of the setting means OFF, and turning it on takes a deliberate write.

⚠️ AND IT IS NOT A KILL SWITCH FOR ALL MAIL. It gates invoice emails specifically.
Statement delivery, approval-gate emails, portal password recovery and the rest route
through their own paths and are untouched — widening this to all outbound mail would be a
much larger decision than the one that was asked for.

How to turn it on, when James wants it on:

    company.set_setting("invoice_email_enabled", True)

There is no UI for it yet, deliberately — a switch with a UI is a switch somebody flips by
accident while exploring settings.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: The settings key. One spelling, imported by the guard and by the tests.
SETTING_KEY = "invoice_email_enabled"

#: ⚠️ `False`. See the module docstring — an absent setting means off.
DEFAULT = False


def invoice_email_allowed(
    db: Session | None, company_id: str | None
) -> tuple[bool, str]:
    """`(allowed, reason)`. The reason is only meaningful when not allowed.

    ⚠️ NO `db` OR NO `company_id` MEANS NOT ALLOWED, AND THAT IS NOT DEFENSIVE PADDING.
    Both are keyword-optional on `send_invoice_email`, so a caller can reach the send
    path without either. Defaulting an unidentifiable tenant to *allowed* would mean the
    one code path that cannot be checked is the one that sends — which is how a switch
    ends up being bypassed by the only caller that mattered. Failing closed makes such a
    caller visible (its mail stops) instead of exempt.

    ⚠️ AN ERROR READING THE SETTING ALSO MEANS NOT ALLOWED. A database hiccup must not
    open the gate.
    """
    if db is None:
        return False, "no database session was passed, so the tenant switch is unreadable"
    if not company_id:
        return False, "no company_id was passed, so the tenant switch is unreadable"

    try:
        from app.models.company import Company

        company = db.query(Company).filter(Company.id == company_id).first()
        if company is None:
            return False, f"company {company_id} not found"
        enabled = company.get_setting(SETTING_KEY, DEFAULT)
    except Exception as exc:  # pragma: no cover - exercised by the failing-read test
        logger.error(
            "invoice-email switch unreadable for company %s (%s); withholding",
            company_id, exc,
        )
        return False, f"the tenant switch could not be read ({exc})"

    # ⚠️ TRUTHINESS IS NOT ENOUGH — `settings_json` is TEXT and a value that went in
    # through a form can come back as the STRING "false", which is truthy. Only an
    # explicit affirmative opens the gate.
    if enabled is True or (isinstance(enabled, str) and enabled.strip().lower() in ("true", "1", "yes")):
        return True, ""
    return (
        False,
        f"{SETTING_KEY} is not enabled for this tenant "
        f"(value: {enabled!r}; default is {DEFAULT})",
    )

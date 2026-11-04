"""The payroll data switch — off by default, and enforced rather than agreed.

⚠️ **[SUPERSEDED 2026-11-04 — THE PREMISE BELOW IS NO LONGER JAMES'S POSITION,
AND THE SWITCH SURVIVES ON A DIFFERENT ONE.]** This docstring argues that "pay
rates and hours should not sit behind a password alone", and on 2026-11-04
James ruled the opposite after weighing it: the same names, hours, rates and
dues already sit behind a single password in Payentry itself, so a second
factor here was protecting a COPY more carefully than the original. Two-step is
now optional for everyone, with three compensating controls named instead — a
long unique password for the accountant, James's own enrolment kept on, and
this switch retained.

**So this switch is no longer "the thing that holds data back until two-step
exists".** It is now the deliberate "may Payentry data be loaded" moment,
admin-only and audited, and that is the whole of its job. The original wording
is kept rather than rewritten, because the argument it makes is sound and was
overruled on a judgement about this data rather than shown to be wrong — and
because a reader who finds only the conclusion cannot tell which.

⚠️ **AND IT DOES NOT GATE READS, WHICH MATTERED MORE UNDER THE OLD RULING THAN
THE NEW ONE.** `assert_payroll_data_enabled` is called in exactly one place,
`payroll_reports.py:195`, the upload endpoint. The four read endpoints do not
call it and neither does the service layer. Under the superseded plan — where
the switch was also to control whether two-step was required — that would have
meant "switch off" implying both "no second step" and "real rows readable with
a password". Measured and reported on 2026-11-04; the strict-read-gating fix
was then dropped with the rest of that plan, so the asymmetry stands
deliberately rather than unnoticed.

James's ruling, 2026-11-03: *"Make 'no payroll data until two-step sign-in'
enforced by the code, not just agreed."*

### Why a switch at all

Payroll 1 ships the way IN — a signed-in, area-limited role — and deliberately
loads no payroll data, because pay rates and hours should not sit behind a
password alone. But that was an AGREEMENT between people, not a property of the
system: all seven payroll endpoints gate on `payroll.view`, and three of them
WRITE (`/weeks/upload`, `/calculate`, `/approve`). So anyone holding
`payroll.view` could import a Payentry export today, before tenant invites and
two-step sign-in exist.

An agreement that only a person can keep is the shape CLAUDE.md names repeatedly:
a rule that holds until the day it matters. This makes the empty state structural.

### The semantics, and why NULL is false here

    absent / NULL   -> DISABLED. Off by default.
    false           -> DISABLED.
    true            -> enabled.

⚠️ **THIS IS THE ONE PLACE IN THIS ARC WHERE ABSENT MEANS SOMETHING RATHER THAN
NOTHING, AND THAT IS DELIBERATE.** Elsewhere — `roles.limited_to_areas` — NULL
means "not established" and must stay distinguishable from a measured value,
because guessing would widen access. Here the safe reading of "nobody has said"
is "not allowed", so absent collapses to false. A switch whose unset state
permitted writing would be a switch that defaults to the thing it exists to
prevent, and every tenant that never heard of it would be loading payroll data.

Stored on `Company.settings_json` via `get_setting` / `set_setting` — the
platform's settings pattern (CLAUDE.md §4). That column is `text`, not JSONB; do
not write JSONB operators against it.
"""
from __future__ import annotations

from fastapi import HTTPException, status

#: The settings key. Single producer — the gate, the reader and the admin
#: endpoint all import this rather than spelling the string again.
PAYROLL_DATA_ENABLED = "payroll_data_enabled"


def is_payroll_data_enabled(company) -> bool:
    """True only when the switch has been explicitly turned on."""
    return company.get_setting(PAYROLL_DATA_ENABLED, False) is True


def assert_payroll_data_enabled(company) -> None:
    """Refuse a payroll data write while the switch is off.

    403 rather than 404: the feature exists and the caller may well hold the
    permission — what is missing is the tenant-level go-ahead, and saying so is
    more useful than pretending the endpoint is absent.
    """
    if is_payroll_data_enabled(company):
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": "payroll_data_disabled",
            "message": (
                "Payroll data loading is turned off for this company. No payroll "
                "export can be imported until an administrator enables it. It "
                "stays off until tenant user invites and two-step sign-in exist "
                "for payroll-limited users — pay rates and hours should not sit "
                "behind a password alone."
            ),
            "setting": PAYROLL_DATA_ENABLED,
        },
    )

"""The tenant's R-115 settings: the deadline, and the header's own facts.

Four values, all stored on `Company.settings_json` (text, not jsonb — see
CLAUDE.md §4), all with **no default**:

    payroll_union_form_due_day    1..31, read in the month after the period
    payroll_union_local           e.g. "14532-17"
    payroll_union_plant           the plant named on the form
    payroll_form_completed_by     who signs it

⚠️ **ABSENT STAYS ABSENT, WHICH IS THE OPPOSITE OF THE DATA SWITCH AND IS
DELIBERATE.** `data_gate` folds a missing value into `False`, because the safe
reading of "nobody has said" is "not allowed". There is no safe default for
any of these: a defaulted deadline is a date nobody agreed to, and a defaulted
local number would print **one licensee's union local on another licensee's
filed form**. That is the `is_manufactured` shape CLAUDE.md §5 names — a
plausible value nobody measured, which reads as data and is invisible.

So each returns `None` when unset and the screens say "Not set". A blank on a
form is a question someone answers; a wrong number is one nobody asks.
"""
from __future__ import annotations

#: Single producers. The reader, the admin endpoint and the UI import these
#: rather than spelling the strings again.
R115_DUE_DAY = "payroll_union_form_due_day"
R115_LOCAL = "payroll_union_local"
R115_PLANT = "payroll_union_plant"
R115_COMPLETED_BY = "payroll_form_completed_by"

#: What the PUT accepts, so the endpoint and the tests agree on one list.
TEXT_SETTINGS: tuple[str, ...] = (R115_LOCAL, R115_PLANT, R115_COMPLETED_BY)

#: Long enough for a local number, a plant name or a person's name; short
#: enough that a settings field cannot become a notes field.
MAX_TEXT = 120


def _text(company, key: str) -> str | None:
    """A trimmed non-empty string, or `None`.

    ⚠️ AN EMPTY STRING IS NOT A VALUE. A field someone cleared by selecting
    the text and deleting it must read the same as one never filled —
    otherwise the form prints an empty box that the code believes is set, and
    "Not set" never appears to prompt anyone.
    """
    raw = company.get_setting(key, None)
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    return trimmed or None


def local(company) -> str | None:
    """The union local this tenant remits to, e.g. "14532-17"."""
    return _text(company, R115_LOCAL)


def plant(company) -> str | None:
    return _text(company, R115_PLANT)


def completed_by(company) -> str | None:
    return _text(company, R115_COMPLETED_BY)


def all_settings(company) -> dict:
    """Every R-115 setting, for the admin screen and the form header."""
    from app.services.payroll.r115_schedule import due_day

    return {
        R115_DUE_DAY: due_day(company),
        R115_LOCAL: local(company),
        R115_PLANT: plant(company),
        R115_COMPLETED_BY: completed_by(company),
    }

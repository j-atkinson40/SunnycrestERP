"""The payroll data switch, set for a test and PUT BACK as it was found.

⚠️ **THIS EXISTS BECAUSE FIVE SUITES SET THE SWITCH AND NONE OF THEM RESTORED
IT.** Each had its own copy of the same `put(value)` closure, and each teardown
either REMOVED the key or wrote `False` — unconditionally, whatever the tenant
held before. So any suite touching payroll left the tenant's switch OFF.

Measured 2026-11-17, and it cost a walk-through: the note went blank mid-walk on
a tenant whose switch had been deliberately turned on, because
`test_payroll_data_switch.py` had run against the same database and removed the
key. Two hypotheses were tested and falsified first — "a backend restart clears
it" and "signing in clears it" — before the suite was found to be the cause
(4/4 runs).

⚠️ **AND THE TEARDOWNS WERE NOT CARELESS; THEY WERE REASONED.** The e2e suite's
says so in terms: *"Return the tenant to the default-off state. A test that
leaves a safety switch ON is a test that disarms the next run."* That is
correct about the DEFAULT and wrong about the TENANT — a test has no business
asserting what a shared database's switch should be, only that it leaves it as
it found it. Restoring the prior state satisfies the real concern (a suite
cannot arm a switch that was off) without the converse harm (a suite disarming
one that was on).

⚠️ **THE ABSENT CASE IS A THIRD STATE, NOT A FALSEY ONE.** `absent`, `False` and
`True` are three distinct things here: `test_absent_setting_means_disabled`
asserts the key is NOT PRESENT, so a restore that wrote `False` would be a
different world that happens to behave the same — until something reads the key
to decide whether the tenant has been configured at all. `ABSENT` is a sentinel
rather than `None`, because `None` is a value a settings blob can legitimately
hold.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from app.models.company import Company
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED


class _Absent:
    """The switch is not present in the settings blob at all."""

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "ABSENT"

    def __bool__(self) -> bool:
        raise AssertionError(
            "ABSENT must not be used as a truth value: absent, False and True "
            "are three distinct states of this switch, and two of them are "
            "falsey. Compare against ABSENT explicitly."
        )


#: The switch is not in `settings_json`. ⚠️ NOT `None`, and not falsey — see
#: the sentinel's `__bool__`, which refuses rather than answering.
ABSENT = _Absent()


def read_switch(company_id: str) -> Any:
    """What the tenant holds for the switch: `ABSENT`, or the stored value."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == company_id).first()
        if co is None:
            return ABSENT
        settings = co.settings
        return (
            settings[PAYROLL_DATA_ENABLED]
            if PAYROLL_DATA_ENABLED in settings
            else ABSENT
        )
    finally:
        db.close()


def write_switch(company_id: str, value: Any) -> None:
    """Set the switch, or remove it when `value is ABSENT`.

    ⚠️ `settings_json` is **text, not jsonb** — see CLAUDE.md §4. Removal
    rewrites the whole blob; there is no JSONB operator to reach for.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == company_id).first()
        if co is None:
            return
        if value is ABSENT:
            settings = co.settings
            settings.pop(PAYROLL_DATA_ENABLED, None)
            co.settings_json = json.dumps(settings)
        else:
            co.set_setting(PAYROLL_DATA_ENABLED, value)
        db.commit()
    finally:
        db.close()


@contextmanager
def payroll_switch(company_id: str, initial: Any) -> Iterator[Callable[[Any], None]]:
    """Set the switch to `initial` for the body, then put it back as found.

    Yields the setter, so a test that needs to move the switch mid-body (the
    switch suite's whole subject) does it through the same path that will be
    undone.

    ⚠️ **THE RESTORE RUNS IN A `finally`.** A failing test is exactly when the
    database is left dirty, and exactly when the next reader is least likely to
    connect their blank note to a suite that errored an hour earlier.

    ⚠️ **CAPTURE BEFORE WRITE, AND ONLY ONCE.** Re-reading the prior state on
    exit would read back whatever the body wrote, which is the shape of a
    tripwire whose condition is satisfied by the damage it detects.
    """
    prior = read_switch(company_id)
    write_switch(company_id, initial)
    try:
        yield lambda value: write_switch(company_id, value)
    finally:
        write_switch(company_id, prior)

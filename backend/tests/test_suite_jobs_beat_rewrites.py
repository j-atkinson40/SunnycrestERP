"""TAX-2 B-1 — the beat-rewrite chain applies, and the tax card is honest.

⚠️ A REWRITE WHOSE `old_text` MATCHES NOTHING IS A SILENT NO-OP THAT LOOKS LIKE
A CHANGE. `_apply_rewrites` (`scripts/seed_suite_jobs.py:335`) updates a beat
only when the stored text BYTE-MATCHES the declared `old_text` — the Option A
idempotent pattern, so operator edits win. The cost of that discipline is that a
typo, a re-wrapped line or an em-dash swapped for a hyphen produces a rewrite
that ships, runs, reports success and changes nothing.

Nothing tested this. `test_suite_map_expression.py` exists, does not mention
`BEAT_REWRITES`, and is not in `ci_gate.txt`.

⚠️ THE INVARIANT IS NOT THE ONE THIS FILE FIRST ASSERTED, and the correction is
the useful part. The first version replayed the chain from `JOBS` and demanded
every `old_text` match the text in force — which failed on all six pre-existing
rewrites. Not a bug in them: `old_text` describes a previously-seeded DATABASE,
while `JOBS` is the FRESH-INSTALL text and already carries their output. The two
are different producers of the same final words, and the real risk is that they
DRIFT — a new database and an upgraded one carding different sentences with
nothing to notice. That is what `TestTheTwoProducersAgree` holds, and B-1 was
caught introducing exactly that divergence.

⚠️ AND THE TAX CARD IS THE REASON THE CHAIN MATTERS HERE. Measured on production
2026-08-19: sunnycrest carries 5 tax rates and 12 correctly-chosen central-NY
counties, and ZERO customers on any tenant carry a ZIP, so
`get_jurisdiction_for_order` returns (None, None) every time and tax computes
0.00 on all 14 production invoices. The card said "TODAY — resolution is real".
True of the code, false of the data, on the one obligation that creates legal
liability rather than inconvenience.

Pure — imports the seed module and reads its declarations. No database, no
tenant, no fixture. Safe on any axis.
"""
from __future__ import annotations

import importlib

seed = importlib.import_module("scripts.seed_suite_jobs")

TAX_JOB = "File sales tax"


def _initial_story() -> dict[tuple[str, str], str]:
    """(job_name, beat_key) → the text the seed first writes."""
    out: dict[tuple[str, str], str] = {}
    for name, _desc, _refs, story, _extra in seed.JOBS:
        for key, text, _link in story:
            out[(name, key)] = text
    return out


def _final_text() -> dict[tuple[str, str], str]:
    """(job_name, beat_key) → the text an UPGRADED database ends up with.

    The last rewrite declared for a beat wins: `_apply_rewrites` walks the list
    in order and each step's output is the next step's input.
    """
    out = dict(_initial_story())
    for job_name, beat_key, _old, new_beat in seed.BEAT_REWRITES:
        out[(job_name, beat_key)] = new_beat["text"]
    return out


class TestTheTwoProducersAgree:
    """⚠️ `JOBS` AND `BEAT_REWRITES` BOTH DECLARE THE FINAL TEXT, AND THEY CAN
    DRIFT. `JOBS` is what a FRESH database is seeded with; `BEAT_REWRITES` is the
    upgrade path for rows seeded before. Two producers of one fact — a new
    install and an existing one can end up carding different words with nothing
    to notice.

    ⚠️ AND THIS CAUGHT TAX-2 B-1 INTRODUCING EXACTLY THAT. The first version of
    this file replayed the chain from `JOBS` and asserted every `old_text`
    matched the text in force. It failed on all six PRE-EXISTING rewrites —
    which is not a bug in them: `old_text` describes a previously-seeded
    DATABASE, not the current source, and `JOBS` already carries their
    post-rewrite text. Getting that model wrong is what surfaced the real
    invariant, and B-1 had genuinely changed one side without the other.
    """

    def test_a_fresh_install_and_an_upgraded_one_card_the_same_words(self):
        initial, final = _initial_story(), _final_text()
        drift = []
        for key in sorted(final):
            if initial.get(key) != final[key]:
                drift.append(
                    f"{key}:\n      JOBS (fresh)     : {initial.get(key, '(absent)')[:88]!r}"
                    f"\n      rewrite (upgrade): {final[key][:88]!r}")
        assert not drift, (
            "fresh-install text and upgrade text disagree:\n  " + "\n  ".join(drift)
        )

    def test_every_rewrite_targets_a_beat_that_exists(self):
        """A rewrite naming a beat `JOBS` does not declare can never fire on a
        fresh database and silently no-ops on an upgraded one."""
        initial = _initial_story()
        missing = [
            f"{jn!r}/{bk!r}" for jn, bk, _o, _n in seed.BEAT_REWRITES
            if (jn, bk) not in initial
        ]
        assert not missing, f"rewrites for non-existent beats: {missing}"

    def test_a_rewrite_keeps_its_own_key(self):
        """`_apply_rewrites` matches on `beat_key` and then REPLACES the whole
        beat dict. A `new_beat` carrying a different key would silently rename
        the beat and orphan the next rewrite in the chain."""
        for job_name, beat_key, _old, new_beat in seed.BEAT_REWRITES:
            assert new_beat.get("key") == beat_key, (
                f"{job_name!r}/{beat_key!r} rewrites to key "
                f"{new_beat.get('key')!r} — the chain breaks here"
            )


class TestTheTaxCardNamesItsPrecondition:
    """⚠️ THE MECHANISM IS REAL AND THE OUTCOME IS ABSENT, and the beat has to
    say which it is describing. Resolution needs a delivery county or a customer
    ZIP; production has neither, so it charges nothing — which is not exempt."""

    def test_the_resolution_beat_names_what_it_resolves_against(self):
        text = _final_text()[(TAX_JOB, "today-resolve")]
        assert "ZIP" in text or "zip" in text, (
            "the resolution beat does not say what resolution needs, so an "
            "operator with no addresses reads it as 'handled'"
        )
        assert "county" in text.lower()

    def test_it_says_charging_nothing_is_not_the_same_as_exempt(self):
        """The distinction that carries the liability. Zero tax because nothing
        resolved and zero tax because a certificate applies are the same number
        and different obligations."""
        text = _final_text()[(TAX_JOB, "today-resolve")]
        assert "not the same as" in text.lower() and "exempt" in text.lower()

    def test_the_accumulate_beat_names_the_unclassified_bucket(self):
        text = _final_text()[(TAX_JOB, "coming-accumulate")]
        assert "unclassified" in text.lower()
        assert "gap" in text.lower(), "the gaps the accumulator writes are unmentioned"

    def test_the_filing_beat_says_a_gappy_return_is_not_finished(self):
        text = _final_text()[(TAX_JOB, "coming-filing")]
        assert "not a finished return" in text.lower()
        assert "no exemption source" in text.lower()

    def test_no_tax_beat_claims_an_outcome_without_a_condition(self):
        """⚠️ THE REGRESSION GUARD. Every tax beat begins "TODAY —", which is
        true of the mechanism. What made the card mislead was claiming that
        WITHOUT naming what the mechanism needs. If a future rewrite drops the
        condition, this fails."""
        resolved = _final_text()
        conditions = {
            "today-resolve": ("zip", "county"),
            "coming-accumulate": ("unclassified",),
            "coming-filing": ("gaps",),
        }
        for key, needles in conditions.items():
            text = resolved[(TAX_JOB, key)].lower()
            assert any(n in text for n in needles), (
                f"tax beat {key!r} claims an outcome with no precondition named"
            )


class TestTheLinksGoSomewhereActionable:
    def test_the_resolution_beat_links_to_where_the_fix_is(self):
        """It linked to /settings/tax — where the RATES are, which are already
        correct. The missing thing is customer addresses, so the link follows
        the defect rather than the topic."""
        beat = next(
            nb for jn, bk, _o, nb in seed.BEAT_REWRITES
            if jn == TAX_JOB and bk == "today-resolve"
        )
        # `next` takes the FIRST match; the chain's LAST entry is the one in
        # force, so resolve it the same way the seed does.
        last = [nb for jn, bk, _o, nb in seed.BEAT_REWRITES
                if jn == TAX_JOB and bk == "today-resolve"][-1]
        assert last["link"]["href"] == "/customers", (
            f"links to {last['link']['href']!r} — the rates are already right; "
            f"the addresses are not"
        )
        assert beat is not None


class TestTheComingCheckerIsCodeCapabilityOnly:
    """⚠️ RECORDED, NOT FIXED — B-1 reports this rather than building it.

    `_tax_filing_arc_landed` (`maps_of_content/jobs.py:184`) returns True when
    `app.services.tax_filing_service` IMPORTS. That is a code-existence probe
    standing in for a capability claim, so the card renders REAL on a tenant
    where resolution produces nothing.

    `GLANCE_SOURCES` receives `tenant_id` (`jobs.py:826`); `COMING_CHECKERS`
    does not (`jobs.py:827`) — two lines apart. A tenant-aware answer is
    therefore one signature away, but a THIRD card state is a design ruling and
    is not taken here.
    """

    def test_the_checker_still_takes_no_tenant(self):
        """Pins the limitation so the report's claim stays true, and fails
        loudly if someone adds tenant scope without revisiting the card state."""
        import inspect

        from app.services.maps_of_content import jobs as jobs_svc

        sig = inspect.signature(jobs_svc._tax_filing_arc_landed)
        assert list(sig.parameters) == ["db"], (
            "the coming-checker now takes more than a Session — a tenant-aware "
            "checker needs the third card state ruled on first"
        )

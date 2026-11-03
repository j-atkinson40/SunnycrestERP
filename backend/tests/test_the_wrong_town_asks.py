'''A town where that cemetery is not raises the question. Slice 2, case 3.

James's ruling of 2026-10-29 has three cases for a town after a cemetery name:

    1. a MATCHING town is absorbed          "st marys in skaneateles" -> settled
    2. a SHARED name is disambiguated       two St Mary's -> the town picks one
    3. a town where that cemetery ISN'T     -> Opas ASKS

⚠️ CASE 3 WAS ALREADY IMPLEMENTED FOR THE EXPLICIT `in <town>` FORM AND DEFERRED FOR THE
BARE FORM, which is measured here rather than assumed. `towns.towns_for_name`'s docstring
sets out the deferral and its reason: a bare town that conflicts would turn the cemetery
row from filled into a question as the director types the next word, which is exactly
what `test_NO_PREFIX_EVER_LOSES_A_FIELD_IT_HAD` exists to catch.

⚠️ AND FINDING THAT OUT FOUND A CRASH. Measuring the explicit form against a town the
tenant holds no record of raised `NameError: name 'NOISE_WORDS' is not defined` from
`towns.narrow_town` — a real HTTP 500 on "st marys in buffalo". The module referenced
that list at one line and in two comments and imported it nowhere. The bare form calls
with `strict=True` and returns two lines earlier, so every test of the bare form passed
over a line that could not run.
'''
import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture(scope="module")
def db():
    _local_only()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db):
    tid = db.execute(sql("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    if not tid:
        pytest.skip("no testco tenant")
    return tid


@pytest.fixture(scope="module")
def towns(db, tenant):
    """The cemeteries this tenant holds, so the cases below name real data.

    ⚠️ READ RATHER THAN HARD-CODED, because the whole point of case 3 is a town the
    tenant has NO record of, and "no record of" is a fact about this database. A
    hard-coded "syracuse" would silently become a RIGHT town the day someone seeds a
    cemetery there, and the test would keep passing while asserting the opposite case.
    """
    rows = db.execute(
        sql("SELECT name, city FROM cemeteries WHERE company_id = :t"), {"t": tenant}
    ).fetchall()
    by_city = {(c or "").strip().casefold() for _n, c in rows}
    marys = [c for n, c in rows if "mary" in (n or "").lower()]
    if not marys:
        pytest.skip("no St Mary's cemetery on this tenant")
    return {
        "right": marys[0],
        # a town the tenant DOES hold, but not for this cemetery — case 3's own shape
        "wrong": next(
            (c for _n, c in rows if (c or "").strip().casefold() not in
             {(marys[0] or "").strip().casefold()}),
            None,
        ),
        "unknown": next(
            t for t in ("Buffalo", "Rochester", "Albany", "Utica")
            if t.casefold() not in by_city
        ),
    }


def _read(db, tenant, text):
    ex = extract_text(db, tenant_id=tenant, text=text)
    return {
        "cemetery": ex.values.get("cemetery"),
        "city": ex.values.get("cemetery_city"),
        "picks": [(p.field_id, len(p.options)) for p in ex.picks],
    }


class TestTheExplicitInTownForm:
    """`"st marys in <town>"` — the director wrote a word that says a town follows."""

    def test_case_1_a_MATCHING_town_is_absorbed(self, db, tenant, towns):
        got = _read(db, tenant, f"st marys in {towns['right']} thursday")
        assert got["cemetery"] and "Mary" in got["cemetery"]
        assert got["city"] == towns["right"]
        # ⚠️ AND NOTHING IS ASKED. A matching town is confirmation, not a question.
        assert got["picks"] == []

    def test_case_3_a_town_the_cemetery_IS_NOT_IN_asks(self, db, tenant, towns):
        """⚠️ THE RULING'S THIRD CASE, AND IT ALREADY WORKED HERE. The conflict becomes a
        PICK by the ruling of 2026-10-12, which is how Opas asks."""
        if towns["wrong"] is None:
            pytest.skip("this tenant holds only one cemetery town")
        got = _read(db, tenant, f"st marys in {towns['wrong']} thursday")
        assert ("cemetery", 1) in [(f, n) for f, n in got["picks"]] or got["picks"]
        # ⚠️ AND THE VALUE IS WITHHELD WHILE THE QUESTION STANDS, rather than Opas
        # picking one and being quietly wrong about which St Mary's.
        assert got["cemetery"] is None

    def test_a_town_the_tenant_HOLDS_NO_RECORD_OF_asks_rather_than_CRASHING(
        self, db, tenant, towns
    ):
        """⚠️ THE CRASH REGRESSION, AND IT IS A 500 NOT A WRONG ANSWER.

        Before the fix this raised `NameError: name 'NOISE_WORDS' is not defined` out of
        `towns.narrow_town`, because that module used the list and imported it nowhere.
        Reachable only through the explicit form with an unknown town — the bare form
        returns `strict=True` two lines earlier — so no existing test executed the line.

        It is asserted as "does not raise" AND "asks", because a fix that swallowed the
        error into a silent no-town would pass the first half alone.
        """
        got = _read(db, tenant, f"st marys in {towns['unknown']} thursday")
        assert got["picks"], "an unknown town should still raise the conflict"
        assert got["cemetery"] is None

    def test_the_import_is_the_one_the_ratchet_allows(self):
        """⚠️ `noise` IS THE LEAF MODULE BOTH SIDES MAY TAKE IT FROM, and importing it
        from `typed_extraction` instead would trip
        `test_only_the_typed_path_imports_the_extractor` — the E6 guarantee that the
        mention policy stays isolated to the typed path. `held._is_label_word` records
        the same lesson after making the same mistake."""
        src = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "app" / "services" / "capture" / "towns.py"
        ).read_text()
        assert "from app.services.capture.noise import NOISE_WORDS" in src
        assert "from app.services.capture.typed_extraction import" not in src


class TestTheBareAdjacentForm:
    """`"st marys <town>"` with no "in" — narrowed, and case 3 deliberately deferred."""

    def test_case_1_a_MATCHING_bare_town_is_absorbed(self, db, tenant, towns):
        got = _read(db, tenant, f"st marys {towns['right']} thursday")
        assert got["cemetery"] and "Mary" in got["cemetery"]
        assert got["city"] == towns["right"]
        assert got["picks"] == []

    def test_a_WRONG_bare_town_is_IGNORED_rather_than_asked_about(
        self, db, tenant, towns
    ):
        """⚠️ THIS PINS A DELIBERATE DEFERRAL, NOT A BUG, and it is written as a
        statement of current behaviour so that changing it is a decision rather than a
        surprise.

        `towns_for_name` narrows the bare form to towns consistent with the NAME, which
        implements cases 1 and 2 and leaves case 3 alone. Its reason: a bare conflicting
        town would make the cemetery row go from filled to a question as the next word
        lands — the "a field that appears and then vanishes" defect James watched happen.

        ⚠️ ITS OWN DOCSTRING SAYS THE DEFERRAL ENDS WHEN CLAUSE 1 LANDS — *"a term that
        leaves the bar becomes a durable resolution, and resolutions outrank the text …
        The deferral is until then, not forever."* Clause 1 landed 2026-11-03. Lifting
        this is therefore a live question and NOT taken unilaterally: the safety argument
        rests on the cemetery already being a RESOLUTION when the town is read, and
        whether it is depends on client timing that the server cannot guarantee. Owed to
        James as a ruling.
        """
        if towns["wrong"] is None:
            pytest.skip("this tenant holds only one cemetery town")
        got = _read(db, tenant, f"st marys {towns['wrong']} thursday")
        # the cemetery survives, which is the property the deferral protects
        assert got["cemetery"] and "Mary" in got["cemetery"]
        assert got["city"] == towns["right"]
        assert got["picks"] == []

    def test_an_UNKNOWN_bare_word_is_not_treated_as_a_town(self, db, tenant, towns):
        """⚠️ THE REASON THE BARE FORM IS STRICT AT ALL. `towns.narrow_town`'s comment:
        run through the forgiving path, `"st marys tent only"` would read "tent" as a
        town, conflict with the record, and raise a spurious "which St Mary's?" while
        eating the equipment."""
        got = _read(db, tenant, "st marys tent only")
        assert got["cemetery"] and "Mary" in got["cemetery"]
        assert got["picks"] == []

"""The licensee spec sheet's DATA REGION is byte-identical to James's upload.

⚠️ WHAT THIS PROTECTS, AND WHY IT IS A TEST RATHER THAN A COMMAND.

`docs/catalog/2026-10-02-sunnycrest-product-specs.csv` is Sunnycrest's own
product spec sheet. It is not reference material: migration `r193` reads it as
AUTHORITY and loads its figures onto 15 platform products, and a licensee's
catalog is what a driver reads at a graveside. A silent edit to the data region
is a silent edit to the catalog, and nothing else in the repository would notice.

The file is committed with a COMMENT PRELUDE before the payload, because the
rulings made from it on 2026-10-02 were otherwise uncheckable by anyone but its
owner. That prelude is the reason a whole-file digest cannot be the check:

    md5 <file>                  1157ff1cee4778fbc561036976e6a4e1   (prelude + payload)
    md5 of the payload          ab25952750488f826c4738aab9744b18   (what was uploaded)

⚠️ AND A BYTE OFFSET IS NOT THE FIX EITHER. `tail -c +1347 <file> | md5`
reproduces the upload digest today and rots the moment anyone edits a comment
line — which the prelude exists to invite. The offset is a fact about the current
prelude, not about the payload.

So the check finds the payload by its OWN marker. The upload opens with a UTF-8
BOM; the prelude is plain ASCII `#` lines and contains none. Locating the BOM
locates the payload wherever the prelude ends, so comments may be freely edited,
reflowed, added to or removed and this test still measures exactly the bytes
James sent.

⚠️ THE DIGEST IS MD5 BECAUSE MD5 IS THE DIGEST OF RECORD for this file — it is
the figure quoted in r189, r191, r193 and three investigation documents. It is
not chosen for collision resistance, and this test is a drift tripwire rather
than a security boundary. A sha256 over the same region is asserted alongside it
so the pin does not rest on md5 alone; that value was derived from the committed
file, not supplied.

IF THIS TEST FAILS, the data region changed. That is either a deliberate
correction — in which case update both digests here IN THE SAME COMMIT as the CSV
edit, and say in the commit body what figure changed and on whose authority — or
it is an accident, and the catalog is now loading figures nobody approved.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

#: Repo root from this file: backend/tests/ -> backend/ -> root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_SHEET = REPO_ROOT / "docs" / "catalog" / "2026-10-02-sunnycrest-product-specs.csv"

#: UTF-8 byte-order mark. Opens the upload; absent from the ASCII prelude.
BOM = b"\xef\xbb\xbf"

#: James's upload, 2026-10-02. Quoted in r189, r191, r193 and the investigation
#: documents as this sheet's identity.
EXPECTED_MD5 = "ab25952750488f826c4738aab9744b18"

#: Derived from the committed file, not supplied with it. Pins the same region
#: without resting on md5.
EXPECTED_SHA256 = "9d3dc2f27e77551d84c8d52ffebbaea20d5528f61a2bcfdfd1be7e1f87ecbc25"

#: The payload's shape, as a control: a digest match over an EMPTY region would
#: otherwise be indistinguishable from a digest match over the real one.
EXPECTED_DATA_ROWS = 31
EXPECTED_COLUMNS = 6


def _payload() -> bytes:
    raw = SPEC_SHEET.read_bytes()
    assert raw, f"{SPEC_SHEET} is empty"
    i = raw.find(BOM)
    assert i != -1, (
        f"no UTF-8 BOM in {SPEC_SHEET.name}. The payload is located BY its BOM, "
        f"so either the upload's first bytes were altered or the file was "
        f"re-encoded. Either way the data region can no longer be identified and "
        f"the provenance claim is void."
    )
    assert raw.count(BOM) == 1, (
        f"{raw.count(BOM)} BOMs found; the payload boundary is ambiguous"
    )
    return raw[i:]


class TestTheDataRegionIsTheUpload:
    def test_the_payload_digest_matches_the_upload(self):
        assert hashlib.md5(_payload()).hexdigest() == EXPECTED_MD5

    def test_the_payload_digest_matches_on_a_second_algorithm(self):
        assert hashlib.sha256(_payload()).hexdigest() == EXPECTED_SHA256

    def test_the_prelude_is_excluded_and_may_change_freely(self):
        """⚠️ THE POINT OF SLICING AT THE BOM. The whole file hashes differently
        from the payload; that difference is the prelude and is not protected.
        If this ever fails, the prelude vanished and the digests above became a
        whole-file check by accident."""
        raw = SPEC_SHEET.read_bytes()
        payload = _payload()
        assert len(payload) < len(raw), (
            "payload is the whole file — the comment prelude is gone, so this "
            "test silently became a whole-file digest check"
        )
        prelude = raw[: raw.find(BOM)]
        assert prelude.strip(), "prelude present but empty"
        assert all(
            line.startswith(b"#")
            for line in prelude.splitlines()
            if line.strip()
        ), "the prelude contains a non-comment line, so it is not all prelude"


class TestThePayloadIsStructurallyWhatR193Reads:
    """⚠️ CONTROLS ON THE DIGEST TESTS, not independent coverage. A digest match
    proves the bytes; these prove the bytes are a spec sheet, so a match over
    something degenerate cannot read as success."""

    def test_it_has_the_expected_row_and_column_count(self):
        import csv
        import io

        text = _payload().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        assert len(rows) == EXPECTED_DATA_ROWS
        assert len(rows[0]) == EXPECTED_COLUMNS

    def test_r193_can_still_find_every_product_it_maps(self):
        """The sheet and the migration agree on the rows the migration cites. A
        digest change would fail above; this fails if the migration's line
        citations drift off the sheet while both are individually valid."""
        import csv
        import importlib.util
        import io
        import sys

        text = _payload().decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))

        path = REPO_ROOT / "backend" / "alembic" / "versions" / "r193_load_licensee_specs.py"
        spec = importlib.util.spec_from_file_location("_r193_prov", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_r193_prov"] = mod
        spec.loader.exec_module(mod)

        assert mod.SPEC_ROWS, "r193 carries no rows — positive control"
        for row in mod.SPEC_ROWS:
            # payload line number: header is line 1, so data row i is line i+2
            sheet = rows[row.line - 2]
            assert sheet["Product"] == row.sheet_name, (
                f"r193 line {row.line} cites {row.sheet_name!r}; the sheet has "
                f"{sheet['Product']!r} there"
            )

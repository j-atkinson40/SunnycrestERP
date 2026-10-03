"""The Feb 1 2026 price list is byte-identical to James's upload.

⚠️ WHAT THIS PROTECTS. As of 2026-10-03 the price list is AUTHORITATIVE FOR
CATALOG MEMBERSHIP AND ORGANIZATION — what exists, what it is called, and how it
groups. The spec sheet is authoritative for dimensions only; where the two
disagree about whether something exists, the price list wins. So a silent edit to
this file is a silent edit to what the platform believes Sunnycrest sells, and
nothing else in the repository would notice.

⚠️ WHOLE-FILE DIGEST, UNLIKE THE SPEC SHEET. That file carries a comment prelude
before its payload, so its test has to slice at the BOM. A PDF cannot carry a
prelude — there is nothing to exclude — so the digest is over the whole file and
there is no offset to rot. The difference is deliberate and is the reason these
are two tests rather than one parameterised one.

NAMED BY EFFECTIVE DATE, NOT RECEIPT DATE. `2026-02-01-...` is the date the prices
take effect. A price list gets reissued, so the effective date is the version key
and two issues can sit side by side. The spec sheet had no such date and fell back
to the date it arrived.

IF THIS FAILS, the price list changed. Either a new issue arrived — in which case
it is a NEW FILE under its own effective date, not an edit to this one — or
something modified the bytes. Do not update the digests to make this pass unless
you are deliberately replacing the February 1 2026 issue in place, which should
essentially never be the right move.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_LIST = (
    REPO_ROOT / "docs" / "catalog" / "2026-02-01-sunnycrest-funeral-price-list.pdf"
)

#: James's upload, supplied with the file and verified at the target path.
EXPECTED_MD5 = "ab3fb519423c09fd766b0a265f288cee"
EXPECTED_SHA256 = (
    "b5f679c37a8efb40f4f833be811ac57cf3601c138352d2003ad701c122efde41"
)
EXPECTED_SIZE = 298155

#: Structural controls. A digest match over a truncated or replaced file would
#: fail anyway, but these make a failure say WHICH thing went wrong.
EXPECTED_PAGES = 2


def _raw() -> bytes:
    assert PRICE_LIST.exists(), (
        f"{PRICE_LIST} is missing. The price list is authoritative for catalog "
        f"membership; without it no reconciliation is auditable."
    )
    return PRICE_LIST.read_bytes()


class TestThePriceListIsTheUpload:
    def test_size(self):
        assert len(_raw()) == EXPECTED_SIZE

    def test_md5(self):
        assert hashlib.md5(_raw()).hexdigest() == EXPECTED_MD5

    def test_sha256(self):
        assert hashlib.sha256(_raw()).hexdigest() == EXPECTED_SHA256


class TestItIsStillTheDocumentWeRead:
    """⚠️ CONTROLS ON THE DIGESTS, not independent coverage. They make a failure
    legible: a digest mismatch alone does not say whether the file was truncated,
    replaced with a different document, or re-saved by a viewer."""

    def test_it_is_a_pdf(self):
        assert _raw()[:5] == b"%PDF-", "not a PDF — the file was replaced"

    def test_page_count(self):
        import fitz

        with fitz.open(PRICE_LIST) as doc:
            assert doc.page_count == EXPECTED_PAGES

    def test_the_effective_date_is_on_page_one(self):
        """The filename claims an effective date. This checks the DOCUMENT agrees,
        so a file renamed to a new effective date without new content fails."""
        import fitz

        with fitz.open(PRICE_LIST) as doc:
            text = doc[0].get_text()
        assert "FEBRUARY 1, 2026" in text.upper(), (
            "page 1 does not carry the effective date the filename claims"
        )

    def test_a_known_price_is_present(self):
        """⚠️ A POSITIVE CONTROL ON THE EXTRACTION PATH, not on the digest. If
        text extraction silently returned nothing, the test above would still
        pass on an empty string containing no date — it would fail, but for a
        confusing reason. This asserts the reader can see content at all."""
        import fitz

        with fitz.open(PRICE_LIST) as doc:
            text = doc[0].get_text() + doc[1].get_text()
        assert text.strip(), "extracted no text at all — reader is blind"
        for token in ("$13,452", "$2,570", "Graveliner", "URN VAULTS"):
            assert token in text, f"{token!r} missing — not the document we read"

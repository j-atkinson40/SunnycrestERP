"""Unit tests — NL Creation structured parsers.

Pure-function tests; no DB, no network. Exercises every parser's
happy path + common edge cases.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.nl_creation.structured_parsers import (
    parse_currency,
    parse_date,
    parse_datetime,
    parse_email,
    parse_name,
    parse_phone,
    parse_quantity,
    parse_time,
)


# Fixed reference date — Monday, April 20, 2026.
TODAY = date(2026, 4, 20)


class TestParseDate:
    def test_iso(self):
        r = parse_date("service on 2026-04-23", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"
        assert r["confidence"] > 0.95

    def test_us_slashed_full_year(self):
        r = parse_date("4/23/2026", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"

    def test_us_slashed_two_digit_year(self):
        r = parse_date("4/23/26", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"

    def test_us_slashed_no_year_uses_current_year(self):
        r = parse_date("4/23", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"

    def test_written_month(self):
        r = parse_date("April 23, 2026", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"

    def test_tonight_is_today(self):
        r = parse_date("DOD tonight", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-20"
        assert "Tonight" in r["display"]

    def test_tomorrow(self):
        r = parse_date("deliver tomorrow", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-21"
        assert "Tomorrow" in r["display"]

    def test_yesterday(self):
        r = parse_date("yesterday", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-19"

    def test_weekday_thursday(self):
        # Monday 4/20; Thursday is 4/23.
        r = parse_date("wants Thursday service", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-23"

    def test_weekday_monday_today(self):
        # Query "Monday" on a Monday should resolve to today.
        r = parse_date("Monday", today=TODAY)
        assert r is not None
        assert r["value"] == "2026-04-20"

    def test_no_date_returns_none(self):
        assert parse_date("just words no date", today=TODAY) is None

    def test_empty_string(self):
        assert parse_date("", today=TODAY) is None


class TestParseTime:
    def test_12_hour_pm(self):
        r = parse_time("at 2pm")
        assert r is not None
        assert r["value"] == "14:00"

    def test_12_hour_am(self):
        r = parse_time("9am")
        assert r is not None
        assert r["value"] == "09:00"

    def test_12_hour_with_minutes(self):
        r = parse_time("10:30 AM")
        assert r is not None
        assert r["value"] == "10:30"

    def test_24_hour(self):
        r = parse_time("start at 14:45")
        assert r is not None
        assert r["value"] == "14:45"

    def test_noon(self):
        r = parse_time("at noon")
        assert r is not None
        assert r["value"] == "12:00"

    def test_midnight(self):
        r = parse_time("midnight service")
        assert r is not None
        assert r["value"] == "00:00"

    def test_morning_lower_confidence(self):
        r = parse_time("sometime in the morning")
        assert r is not None
        assert r["confidence"] < 0.8  # ambiguous

    def test_no_time_returns_none(self):
        assert parse_time("just text") is None


class TestParseDatetime:
    def test_date_plus_time(self):
        r = parse_datetime("Thursday at 2pm", today=TODAY)
        assert r is not None
        assert r["value"].startswith("2026-04-23T14:00")

    def test_date_only_returns_midnight(self):
        r = parse_datetime("Thursday", today=TODAY)
        assert r is not None
        assert r["value"].startswith("2026-04-23T00:00")

    def test_time_only_returns_none(self):
        # Time without a date is ambiguous for a datetime field.
        assert parse_datetime("at 2pm", today=TODAY) is None


class TestParsePhone:
    def test_dashed(self):
        r = parse_phone("call 555-123-4567")
        assert r is not None
        assert r["value"] == "+15551234567"
        assert r["display"] == "(555) 123-4567"

    def test_parens(self):
        r = parse_phone("(555) 123-4567")
        assert r is not None
        assert r["value"] == "+15551234567"

    def test_country_code(self):
        r = parse_phone("+1 555 123 4567")
        assert r is not None
        assert r["value"] == "+15551234567"

    def test_dotted(self):
        r = parse_phone("555.123.4567")
        assert r is not None
        assert r["value"] == "+15551234567"

    def test_no_phone(self):
        assert parse_phone("no number here") is None


class TestParseEmail:
    def test_basic(self):
        r = parse_email("bob@acme.com")
        assert r is not None
        assert r["value"] == "bob@acme.com"

    def test_mixed_case_normalizes(self):
        r = parse_email("Bob@Acme.COM")
        assert r is not None
        assert r["value"] == "bob@acme.com"

    def test_embedded_in_text(self):
        r = parse_email("email bob@acme.com with the details")
        assert r is not None
        assert r["value"] == "bob@acme.com"

    def test_no_email(self):
        assert parse_email("no at sign") is None


class TestParseCurrency:
    def test_with_dollar_sign(self):
        r = parse_currency("price $5,000")
        assert r is not None
        assert r["value"] == "5000"

    def test_with_usd(self):
        r = parse_currency("5000 USD")
        assert r is not None
        assert r["value"] == "5000"

    def test_with_decimal(self):
        r = parse_currency("$49.99")
        assert r is not None
        assert r["value"] == "49.99"

    def test_named_thousand(self):
        r = parse_currency("$5 thousand")
        assert r is not None
        # 5 * 1000 = 5000
        assert r["value"] == "5000"

    def test_plain_number_rejected(self):
        # No $ / USD / dollars → don't confuse with quantity.
        assert parse_currency("5000") is None

    def test_phone_number_not_currency(self):
        # Quirky: "call 555-1234" has no $-flag → None.
        assert parse_currency("555-1234") is None


class TestParseQuantity:
    def test_with_unit(self):
        r = parse_quantity("order 24 cases")
        assert r is not None
        assert r["value"]["value"] == 24
        assert r["value"]["unit"] == "case"

    def test_plain_number(self):
        r = parse_quantity("12 widgets")
        # No known unit → confidence low but still matches
        assert r is not None
        assert r["value"]["value"] == 12

    def test_four_digit_alone_rejected(self):
        # Year / phone fragment — not a quantity.
        assert parse_quantity("2024") is None

    def test_currency_skipped(self):
        # If $ present → let currency parser handle.
        assert parse_quantity("$500") is None


class TestParseName:
    def test_first_last(self):
        r = parse_name("John Smith")
        assert r is not None
        assert r["value"] == {"first_name": "John", "last_name": "Smith"}

    def test_first_middle_last(self):
        r = parse_name("John Q Smith")
        assert r is not None
        assert r["value"] == {
            "first_name": "John",
            "middle_name": "Q",
            "last_name": "Smith",
        }

    def test_prefix_stripped(self):
        r = parse_name("Dr. Mary Johnson")
        assert r is not None
        assert r["value"] == {"first_name": "Mary", "last_name": "Johnson"}

    def test_suffix_stripped(self):
        r = parse_name("John Smith Jr")
        assert r is not None
        assert r["value"] == {"first_name": "John", "last_name": "Smith"}

    def test_single_word(self):
        r = parse_name("Cher")
        assert r is not None
        assert r["value"] == {"first_name": "Cher"}
        assert r["confidence"] < 0.8  # ambiguous

    def test_empty(self):
        assert parse_name("") is None


# ── Performance guard ───────────────────────────────────────────────
# Each parser should return in well under 5ms. Not a strict CI gate,
# but a sanity check. Run with `pytest -k parser_fast`.


@pytest.mark.parametrize(
    "parser,sample",
    [
        (parse_date, "Thursday 2026-04-23"),
        (parse_time, "2:30 PM"),
        (parse_phone, "(555) 123-4567"),
        (parse_email, "test@example.com"),
        (parse_name, "John Q Smith Jr"),
    ],
)
def test_parser_fast(parser, sample):
    import time as _time

    # Warm up
    for _ in range(5):
        parser(sample)
    t0 = _time.perf_counter()
    for _ in range(100):
        parser(sample)
    elapsed_ms = (_time.perf_counter() - t0) * 1000
    avg_ms = elapsed_ms / 100
    # Well under 5ms — no regression threshold, just a readable
    # assertion that something hasn't gone quadratic.
    assert avg_ms < 5.0, f"{parser.__name__} avg {avg_ms:.3f}ms > 5ms"

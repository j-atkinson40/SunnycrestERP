"""Structured parsers — deterministic, <5ms each.

These run BEFORE any AI call during NL extraction. They handle the
boring but common cases (dates, times, phone numbers, emails,
currency, quantity, names) so the AI only fills genuine gaps.

Contract for each parser:
  (text: str) -> dict | None
  dict shape: {"value": <typed>, "display": <str>, "confidence": <float>}
  None = no parse. Callers iterate extractors in order; first hit wins.

Performance: all parsers are pure string operations. No regex backtracking
hazards; no network; no DB. Each <5ms on a modern laptop (most <1ms).

Tests in `backend/tests/test_nl_structured_parsers.py` exercise every
parser with edge cases.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

# ── Date parser ──────────────────────────────────────────────────────

_MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_WEEKDAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Precompiled patterns
_ISO_DATE_RX = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_US_DATE_RX = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_MONTH_DAY_RX = re.compile(
    r"\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|"
    r"august|aug|september|sep|sept|october|oct|november|nov|december|dec)\b"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
    re.IGNORECASE,
)
_RELATIVE_WORDS = {
    "today": 0,
    "tonight": 0,
    "yesterday": -1,
    "tomorrow": 1,
}


def _today(today_override: date | None) -> date:
    return today_override or date.today()


def parse_date(text: str, *, today: date | None = None) -> dict[str, Any] | None:
    """Parse a date reference from text.

    Returns `{"value": iso_date_str, "display": human_str, "confidence": f}`
    or None. When multiple dates appear in text, returns the FIRST one —
    callers scan text again after stripping the matched substring if they
    want multiple dates.

    Supported shapes (in priority order):
      - Exact ISO: `2026-04-20`
      - US slashed: `4/20/2026`, `4/20/26`, `4-20-2026`
      - Written month: `April 20`, `Apr 20, 2026`, `20 April 2026` (partial)
      - Weekday: `Thursday` → next Thursday (or today if today IS Thursday)
      - Relative: `today`, `tonight`, `tomorrow`, `yesterday`, `next week`
    """
    if not text:
        return None
    t = text.strip().lower()
    ref = _today(today)

    # 1. ISO
    m = _ISO_DATE_RX.search(t)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return _date_result(d, 0.99, ref)
        except ValueError:
            pass

    # 2. US slashed
    m = _US_DATE_RX.search(t)
    if m:
        mo = int(m.group(1))
        dy = int(m.group(2))
        yr_s = m.group(3)
        yr = int(yr_s) if yr_s else ref.year
        if yr < 100:
            yr += 2000
        try:
            d = date(yr, mo, dy)
            return _date_result(d, 0.92, ref)
        except ValueError:
            pass

    # 3. Written month + day
    m = _MONTH_DAY_RX.search(t)
    if m:
        mo = _MONTH_NAMES.get(m.group(1).lower())
        dy = int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else ref.year
        if mo:
            try:
                d = date(yr, mo, dy)
                # If no year given and the date is well in the past,
                # assume next year (common for "birthday = March 15"
                # kinds of expressions).
                if not m.group(3) and d < ref - timedelta(days=180):
                    d = date(yr + 1, mo, dy)
                return _date_result(d, 0.9, ref)
            except ValueError:
                pass

    # 4. Relative words (tonight / tomorrow / yesterday / today)
    for word, delta in _RELATIVE_WORDS.items():
        if re.search(rf"\b{word}\b", t):
            d = ref + timedelta(days=delta)
            return _date_result(d, 0.95, ref, force_display=word.capitalize())

    # 5. "next week"
    if re.search(r"\bnext week\b", t):
        d = ref + timedelta(days=7)
        return _date_result(d, 0.7, ref, force_display="Next week")

    # 6. Weekday name — return the NEXT occurrence of that weekday
    #    (including today if today matches).
    for wd_name, wd_index in _WEEKDAY_NAMES.items():
        if re.search(rf"\b{wd_name}\b", t):
            delta = (wd_index - ref.weekday()) % 7
            # "Friday" when today is Friday typically means "today"
            # if the speaker's tone is near-term, but next week if
            # scheduling. We err on next-week to avoid off-by-one
            # for scheduling contexts (the demo uses "Thursday"
            # meaning "this coming Thursday").
            if delta == 0:
                delta = 0  # keep as today — ambiguous; confidence reflects
            d = ref + timedelta(days=delta)
            return _date_result(d, 0.85, ref)

    return None


def _date_result(
    d: date,
    confidence: float,
    ref: date,
    force_display: str | None = None,
) -> dict[str, Any]:
    if force_display:
        display = f"{force_display} ({d.isoformat()})"
    elif d == ref:
        display = f"Today ({d.isoformat()})"
    elif d == ref + timedelta(days=1):
        display = f"Tomorrow ({d.isoformat()})"
    elif d == ref - timedelta(days=1):
        display = f"Yesterday ({d.isoformat()})"
    elif abs((d - ref).days) < 7:
        display = f"{d.strftime('%A')} ({d.isoformat()})"
    else:
        display = d.strftime("%B %-d, %Y")
    return {
        "value": d.isoformat(),
        "display": display,
        "confidence": confidence,
    }


# ── Time parser ──────────────────────────────────────────────────────

_TIME_AMPM_RX = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b",
    re.IGNORECASE,
)
_TIME_24H_RX = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)(?![ap]m)\b", re.IGNORECASE)


def parse_time(text: str) -> dict[str, Any] | None:
    """Parse a time of day."""
    if not text:
        return None
    t = text.lower()

    # 12-hour with AM/PM
    m = _TIME_AMPM_RX.search(t)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        period = m.group(3).replace(".", "").lower()
        if period == "pm" and hh < 12:
            hh += 12
        elif period == "am" and hh == 12:
            hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return _time_result(time(hh, mm), 0.95)

    # 24-hour
    m = _TIME_24H_RX.search(t)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        return _time_result(time(hh, mm), 0.92)

    # Named times
    if re.search(r"\bnoon\b", t):
        return _time_result(time(12, 0), 0.95, "Noon")
    if re.search(r"\bmidnight\b", t):
        return _time_result(time(0, 0), 0.95, "Midnight")
    if re.search(r"\bmorning\b", t):
        return _time_result(time(9, 0), 0.5, "Morning (9:00)")
    if re.search(r"\bafternoon\b", t):
        return _time_result(time(14, 0), 0.5, "Afternoon (14:00)")
    if re.search(r"\bevening\b", t):
        return _time_result(time(18, 0), 0.5, "Evening (18:00)")

    return None


def _time_result(
    t: time,
    confidence: float,
    force_display: str | None = None,
) -> dict[str, Any]:
    hh_12 = t.hour % 12 or 12
    period = "AM" if t.hour < 12 else "PM"
    display = (
        force_display
        or f"{hh_12}:{t.minute:02d} {period}"
    )
    return {
        "value": t.strftime("%H:%M"),
        "display": display,
        "confidence": confidence,
    }


# ── Datetime parser ──────────────────────────────────────────────────


def parse_datetime(
    text: str, *, today: date | None = None
) -> dict[str, Any] | None:
    """Combine a date + time extraction into a single ISO datetime.

    If only a date is found, returns start-of-day; if only a time,
    returns None (time without date is ambiguous for datetime fields).
    """
    d = parse_date(text, today=today)
    tm = parse_time(text)
    if d is None and tm is None:
        return None
    if d is None:
        return None  # time-only isn't a datetime
    d_val = date.fromisoformat(d["value"])
    t_val = time.fromisoformat(tm["value"]) if tm else time(0, 0)
    dt = datetime.combine(d_val, t_val, tzinfo=timezone.utc)
    confidence = min(d["confidence"], tm["confidence"]) if tm else d["confidence"] * 0.8
    display = (
        f"{d['display'].split(' (')[0]} "
        f"{tm['display'] if tm else '(start of day)'}"
    )
    return {
        "value": dt.isoformat(),
        "display": display.strip(),
        "confidence": confidence,
    }


# ── Phone parser ─────────────────────────────────────────────────────
# E.164-style US phones. Strips formatting; normalizes to +1XXXXXXXXXX.

_PHONE_RX = re.compile(
    r"""(?x)
    (?:\+?1[\s.-]?)?
    \(?(\d{3})\)?[\s.-]?
    (\d{3})[\s.-]?
    (\d{4})
    """
)


def parse_phone(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = _PHONE_RX.search(text)
    if not m:
        return None
    digits = f"+1{m.group(1)}{m.group(2)}{m.group(3)}"
    display = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
    return {"value": digits, "display": display, "confidence": 0.95}


# ── Email parser ─────────────────────────────────────────────────────

_EMAIL_RX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def parse_email(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = _EMAIL_RX.search(text)
    if not m:
        return None
    addr = m.group(0).lower()
    return {"value": addr, "display": addr, "confidence": 0.99}


# ── Currency parser ──────────────────────────────────────────────────

_CURRENCY_RX = re.compile(
    r"""(?x)
    (?:\$|\bUSD\s+)?
    (\d+(?:,\d{3})*(?:\.\d{1,2})?)
    (?:\s*(?:USD|dollars?))?
    """,
    re.IGNORECASE,
)
_CURRENCY_NAMED_WORDS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "hundred": 100,
}


def parse_currency(text: str) -> dict[str, Any] | None:
    """Parse a currency value. Only fires when there's a $-sign, USD
    unit, or the word 'dollars' nearby — avoids false positives on
    phone numbers or quantities."""
    if not text:
        return None
    t = text.lower()
    if "$" not in t and "usd" not in t and "dollar" not in t:
        return None
    m = _CURRENCY_RX.search(t)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        val = Decimal(raw)
    except InvalidOperation:
        return None
    # Handle "five thousand dollars" lightly — if a magnitude word
    # follows, multiply.
    for word, mul in _CURRENCY_NAMED_WORDS.items():
        if word in t[m.end():m.end() + 20]:
            val = val * Decimal(mul)
            break
    display = f"${val:,.2f}"
    return {"value": str(val), "display": display, "confidence": 0.85}


# ── Quantity parser ──────────────────────────────────────────────────

_QTY_RX = re.compile(
    r"""(?x)
    \b(\d+(?:\.\d+)?)\s*
    (pieces?|pcs|units?|ea|each|cases?|boxes?|pallets?|skid)?\b
    """,
    re.IGNORECASE,
)


def parse_quantity(text: str) -> dict[str, Any] | None:
    """Numeric quantity + optional unit. Skipped if text is
    currency-flavored (avoid double-parse with currency)."""
    if not text:
        return None
    t = text.lower()
    if "$" in t:
        return None
    m = _QTY_RX.search(t)
    if not m:
        return None
    raw_num = m.group(1)
    unit = m.group(2)
    try:
        val_num = float(raw_num)
    except ValueError:
        return None
    # Don't capture 4-digit numbers alone — those are usually years or
    # phone fragments, not quantities.
    if unit is None and val_num >= 1000:
        return None
    unit_norm = _normalize_qty_unit(unit)
    display = f"{val_num:g}" + (f" {unit_norm}" if unit_norm else "")
    return {
        "value": {"value": val_num, "unit": unit_norm},
        "display": display,
        "confidence": 0.9 if unit else 0.6,
    }


def _normalize_qty_unit(u: str | None) -> str | None:
    if u is None:
        return None
    u = u.lower().rstrip("s")
    return {
        "piece": "each",
        "pc": "each",
        "ea": "each",
        "each": "each",
        "unit": "each",
        "case": "case",
        "box": "box",
        "pallet": "pallet",
        "skid": "pallet",
    }.get(u, u)


# ── Name parser ──────────────────────────────────────────────────────
# Heuristic first/middle/last split. Prefix ("Mr", "Mrs", "Dr")
# handled. Designed to run on a SEGMENT of the NL input that the
# caller has isolated as "the person's name" — not the whole sentence.

_PREFIXES = {"mr", "mrs", "ms", "miss", "mx", "dr", "rev", "fr", "sr"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def parse_name(text: str) -> dict[str, Any] | None:
    """Split a name into first/middle/last components.

    Input is expected to be JUST the person's name (e.g. "John Q Smith",
    "Dr Mary Johnson III"). Returns a dict with any of `first_name`,
    `middle_name`, `last_name` populated, plus a `display` concatenation.

    Callers feeding whole sentences should chunk first or rely on the
    AI extractor.
    """
    if not text:
        return None
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    if not tokens:
        return None

    # Strip leading prefix
    if tokens[0].lower().rstrip(".") in _PREFIXES:
        tokens = tokens[1:]
    # Strip trailing suffix
    if tokens and tokens[-1].lower().rstrip(".,") in _SUFFIXES:
        tokens = tokens[:-1]

    if not tokens:
        return None

    first = tokens[0]
    last = tokens[-1] if len(tokens) > 1 else None
    middle = " ".join(tokens[1:-1]) if len(tokens) > 2 else None

    parts: dict[str, Any] = {"first_name": first}
    if middle:
        parts["middle_name"] = middle
    if last:
        parts["last_name"] = last

    display = " ".join(
        [first] + ([middle] if middle else []) + ([last] if last else [])
    )
    return {
        "value": parts,
        "display": display,
        "confidence": 0.88 if last else 0.6,
    }


# ── Public index ─────────────────────────────────────────────────────

__all__ = [
    "parse_date",
    "parse_time",
    "parse_datetime",
    "parse_phone",
    "parse_email",
    "parse_currency",
    "parse_quantity",
    "parse_name",
]

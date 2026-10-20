"""Score the request set against the SHIPPED rules. Reports its denominator.

⚠️ IT SCORES THE REAL PREDICATES, NOT A COPY OF THEM. `extract_text`, `interpret` and
`product_name_resolver.resolve` are the functions the server runs. The `opener` rows are
NOT scored here — that predicate is TypeScript and scoring it in Python would be a
second implementation of the rule, which is the defect the whole abbreviation slice was
written to avoid. `opas-request-score.test.ts` reads the same JSONL and scores those.

⚠️ IT REPORTS A DENOMINATOR PER SCORER, because "95%" over a set whose membership nobody
states is the shape CLAUDE.md §11 calls a gate without a denominator.

Run:  PYTHONPATH=. DATABASE_URL=... .venv/bin/python scripts/score_opas_requests.py
      SLUG=sunnycrest RO=1 ... for production, read-only
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text as sql  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

SET = pathlib.Path(__file__).resolve().parent.parent / "tests/data/opas_requests.jsonl"


def _session():
    url = os.environ["DATABASE_URL"]
    kw = {"connect_args": {"options": "-c default_transaction_read_only=on"}} \
        if os.environ.get("RO") == "1" else {}
    return sessionmaker(bind=create_engine(url, **kw))()


def _score_extractor(db, tid, r) -> tuple[bool, str]:
    from app.services.capture.typed_extraction import extract_text

    ex = extract_text(db, tenant_id=tid, text=r["text"])
    want = r["want"]
    for field, expected in (want.get("values") or {}).items():
        got = ex.values.get(field)
        if got is None:
            return False, f"{field} missing"
        if expected == "*":
            continue
        if expected == "weekday":
            if not (isinstance(got, str) and got.count("-") == 2):
                return False, f"{field}={got!r} is not a date"
            continue
        if got != expected:
            return False, f"{field}={got!r} wanted {expected!r}"
    if "values" in want and not want["values"]:
        if ex.values:
            return False, f"expected nothing, got {sorted(ex.values)}"
    for field in want.get("picks") or []:
        if field not in {p.field_id for p in ex.picks}:
            return False, f"no pick for {field}"
    if "unrecognized" in want:
        exp = want["unrecognized"]
        joined = " ".join(ex.unrecognized).casefold()
        if exp == []:
            if ex.unrecognized:
                return False, f"unrecognized={ex.unrecognized}"
        else:
            for w in exp:
                if w != "*" and w.casefold() not in joined:
                    return False, f"{w!r} not reported unrecognized ({ex.unrecognized})"
            if exp and not ex.unrecognized:
                return False, "nothing reported unrecognized"
    return True, ""


def _score_catalog(db, tid, r) -> tuple[bool, str]:
    from app.services.product_name_resolver import build_index, resolve

    res = resolve(build_index(db), r["text"])
    n = len(res.candidates)
    want = r["want"]["candidates"]
    if want == "many":
        return (n > 1, f"{n} candidates")
    if want == 1:
        return (n == 1 and bool(res.variant_template_id), f"{n} candidates")
    return (n == int(want), f"{n} candidates")


def _score_order_list(db, tid, r) -> tuple[bool, str]:
    from datetime import date

    from app.services.order_list.question import interpret

    got = interpret(r["text"], today=date.today())
    want = r["want"]["kind"]
    # ⚠️ `interpret` ALWAYS RETURNS AN `Interpretation`; "unrecognized" is a PROPERTY of
    # it, not a None. Measured rather than assumed — my first version tested `is None`
    # and would have scored every order-list row as a miss.
    recognized = bool(getattr(got, "question", None) or getattr(got, "number_query", None))
    if want == "question":
        return (recognized, f"not recognized: {got!r}")
    return (not recognized, f"recognized as {got!r}")


SCORERS = {"extractor": _score_extractor, "catalog": _score_catalog,
           "order_list": _score_order_list}


def main() -> int:
    rows = [json.loads(line) for line in SET.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    db = _session()
    slug = os.environ.get("SLUG", "testco")
    tid = db.execute(sql("SELECT id FROM companies WHERE slug=:s"), {"s": slug}).scalar()
    if not tid:
        print(f"no tenant {slug!r}")
        return 2
    where = os.environ.get("DATABASE_URL", "")
    from urllib.parse import urlparse
    host = urlparse(where).hostname
    print(f"tenant={slug} host={host} rows={len(rows)}\n")

    per = Counter()
    tot = Counter()
    misses = []
    for r in rows:
        fn = SCORERS.get(r["scored_by"])
        if fn is None:
            tot["skipped:" + r["scored_by"]] += 1
            continue
        tot[r["scored_by"]] += 1
        ok, why = fn(db, tid, r)
        if ok:
            per[r["scored_by"]] += 1
        else:
            misses.append((r["id"], r["scored_by"], r["text"], why))

    scored = sum(tot[k] for k in SCORERS if k in tot)
    right = sum(per.values())
    print(f"SCORED {right}/{scored} "
          f"({100 * right // scored if scored else 0}%) of {len(rows)} rows in the set")
    for k in SCORERS:
        if k in tot:
            print(f"  {k:12} {per[k]}/{tot[k]}")
    for k, v in tot.items():
        if k.startswith("skipped:"):
            print(f"  {k:12} {v}  (scored by the frontend suite, not here)")
    if misses:
        print("\nnot resolved:")
        for i, s, t, why in misses:
            print(f"  {i:5} {s:11} {t!r}\n        {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

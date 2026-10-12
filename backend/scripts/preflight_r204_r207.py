"""READ-ONLY pre-flight for r204-r207, plus the cemetery report.

⚠️ READ-ONLY AT THE CONNECTION LEVEL, not by convention. The engine is opened with
`default_transaction_read_only=on`, so a stray write raises rather than landing.

⚠️ NEVER PRINTS A CREDENTIAL. The URL is parsed and only host/port/database are
shown. CLAUDE.md §7: no credential value passes through a session, in either
direction.

Run against production:

    railway run --project ad95792e-6625-4bf5-ad61-ead9c291bdf9 \
      --environment production --service SunnycrestERP \
      -- .venv/bin/python scripts/preflight_r204_r207.py

⚠️ WHY A PRE-FLIGHT AT ALL, when r204/r205/r206/r207 each assert their own
preconditions and abort. Because an aborted `alembic upgrade head` fails the whole
deploy and leaves the site on the previous version — which is the designed, accepted
behaviour and still a red deploy nobody wanted. Reading first turns "the deploy will
stop itself" into "the deploy will succeed", or names the row that is missing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, text


def _load(rev: str):
    p = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions" / rev
    spec = importlib.util.spec_from_file_location(rev, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    # ⚠️ TWO MODES, ONE SCRIPT, BECAUSE THE SAME FACTS ARE WANTED ON BOTH SIDES OF
    # THE DEPLOY AND THE EXPECTATIONS INVERT. Pre-flight wants the availability
    # table ABSENT; the post-deploy report wants it present with 40 rows. Keeping
    # them in one file means the queries cannot drift apart between the two
    # readings, which is how a "before" and an "after" stop being comparable.
    post = "--post" in sys.argv
    print(f"MODE:   {'POST-DEPLOY REPORT' if post else 'PRE-FLIGHT'}")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set in this environment")
        return 2
    u = urlparse(url)
    print(f"TARGET: host={u.hostname} port={u.port} db={(u.path or '').lstrip('/')}")
    print("MODE:   read-only at the connection level\n")

    engine = create_engine(
        url, connect_args={"options": "-c default_transaction_read_only=on"}
    )
    ok = True
    with engine.connect() as c:
        # ── controls first ───────────────────────────────────────────────
        tables = {r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))}
        print(f"[control] tables visible: {len(tables)}")
        if len(tables) <= 100:
            print("  FAIL the reader is blind; every absence below is meaningless")
            return 1

        head = c.execute(text(
            "SELECT version_num FROM alembic_version"
        )).scalar()
        # ⚠️ NOT LABELLED "production". This script runs against whatever
        # DATABASE_URL names, and a hardcoded label would make a dev reading look
        # like a production one in a transcript. The TARGET line above says which.
        print(f"[head] alembic head: {head}")
        srv = c.execute(text("SHOW server_version_num")).scalar()
        print(f"[r205] server_version_num: {srv} (needs >= 150000)")
        ok &= int(srv) >= 150000

        # ── catalog ──────────────────────────────────────────────────────
        by_sku = {s: i for s, i in c.execute(text(
            "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
        ))}
        print(f"[catalog] active variant templates: {len(by_sku)} (needs > 40)")
        ok &= len(by_sku) > 40

        r204 = _load("r204_platform_availability.py")
        miss204 = sorted(set(r204.AVAILABILITY_BY_SKU) - set(by_sku))
        print(f"[r204] rows it will write: {len(r204.AVAILABILITY_BY_SKU)}")
        print(f"[r204] SKUs absent (must be none): {miss204 or 'none'}")
        ok &= not miss204
        avail_present = "platform_personalization_availability" in tables
        if post:
            n_avail = c.execute(text(
                "SELECT count(*) FROM platform_personalization_availability"
            )).scalar() if avail_present else None
            print(f"[r204] platform_personalization_availability present: {avail_present}")
            print(f"[r204] rows in it: {n_avail} (expect {len(r204.AVAILABILITY_BY_SKU)})")
            ok &= avail_present and n_avail == len(r204.AVAILABILITY_BY_SKU)
            distinct_q = c.execute(text(
                "SELECT count(DISTINCT question_id) FROM platform_personalization_availability"
            )).scalar()
            print(f"[r204] distinct question_ids: {distinct_q} (expect 1: personalization)")
        else:
            print(f"[r204] platform_personalization_availability already exists: "
                  f"{avail_present}")
            ok &= not avail_present

        r206 = _load("r206_oversized_class_aliases.py")
        planned206 = r206._planned()
        miss206 = sorted({s for _, s in planned206} - set(by_sku))
        print(f"[r206] rows it will write: {len(planned206)}")
        print(f"[r206] SKUs absent (must be none): {miss206 or 'none'}")
        ok &= not miss206

        r207 = _load("r207_form_counterpart_aliases.py")
        miss207 = sorted({s for _, s in r207._ROWS} - set(by_sku))
        print(f"[r207] rows it will write: {len(r207._ROWS)}")
        print(f"[r207] urn SKUs absent (must be none): {miss207 or 'none'}")
        ok &= not miss207

        # ⚠️ r207's own positive control, read here so a failure is a line of output
        # rather than an aborted deploy: each alias must ALREADY reach its burial
        # variant, or the insert would INVERT the alias instead of widening it.
        if "platform_product_aliases" in tables:
            n_alias = c.execute(text(
                "SELECT count(*) FROM platform_product_aliases"
            )).scalar()
            print(f"[alias] platform_product_aliases rows now: {n_alias}")
            if post:
                # ⚠️ COUNTED BY THE NOTE PREFIX EACH MIGRATION WRITES, so the
                # attribution comes from the rows themselves rather than from
                # arithmetic over a total nobody recorded beforehand.
                n206 = c.execute(text(
                    "SELECT count(*) FROM platform_product_aliases "
                    "WHERE note LIKE 'Class alias.%'"
                )).scalar()
                n207 = c.execute(text(
                    "SELECT count(*) FROM platform_product_aliases "
                    "WHERE note LIKE 'Form counterpart.%'"
                )).scalar()
                print(f"[r206] alias rows attributable to r206: {n206} (expect 48)")
                print(f"[r207] alias rows attributable to r207: {n207} (expect 3)")
                ok &= n206 == 48 and n207 == 3
            for alias_text, sku in r207._EXPECTED_EXISTING:
                got = c.execute(text(
                    "SELECT count(*) FROM platform_product_aliases a "
                    "JOIN product_variant_templates v ON v.id = a.variant_template_id "
                    "WHERE a.alias_text_normalized = :n AND v.sku = :s "
                    "AND a.is_confirmed IS TRUE"
                ), {"n": r207._fold(alias_text), "s": sku}).scalar()
                print(f"[r207] existing {alias_text!r} -> {sku}: {got} (needs exactly 1)")
                ok &= got == 1
        else:
            print("[alias] platform_product_aliases is ABSENT — r206/r207 would fail")
            ok = False

        # ── r205: the constraint and the duplicates it would trip on ─────
        cons = {n: d for n, d in c.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'cemeteries'::regclass AND contype = 'u'"
        ))}
        print(f"[r205] unique constraints on cemeteries now: {json.dumps(cons, indent=2)}")
        dupes = c.execute(text(
            "SELECT company_id, name, count(*) FROM cemeteries "
            "WHERE city IS NULL OR city = '' "
            "GROUP BY company_id, name HAVING count(*) > 1"
        )).all()
        print(f"[r205] NULL/empty-city duplicates (must be none): "
              f"{[tuple(d) for d in dupes] or 'none'}")
        ok &= not dupes
        if post:
            want = "uq_cemetery_company_name_city"
            print(f"[r205] {want} present: {want in cons}")
            ok &= want in cons
            if want in cons:
                d = cons[want]
                print(f"[r205] its definition: {d}")
                ok &= "NULLS NOT DISTINCT" in d and "company_id, name, city" in d
            print(f"[r205] old uq_cemetery_company_name gone: "
                  f"{'uq_cemetery_company_name' not in cons}")
            ok &= "uq_cemetery_company_name" not in cons

        # ── the cemetery report James asked for ──────────────────────────
        total = c.execute(text("SELECT count(*) FROM cemeteries")).scalar()
        nullcity = c.execute(text(
            "SELECT count(*) FROM cemeteries WHERE city IS NULL OR city = ''"
        )).scalar()
        print(f"\n[cemetery report] total rows: {total}")
        print(f"[cemetery report] rows with NULL or empty city: {nullcity}")
        # ⚠️ "LOOKS MANUALLY DISAMBIGUATED BY TOWN" IS A PATTERN GUESS, NOT A FACT.
        # The forms searched for are listed so the reader can see what was looked for
        # and what therefore was NOT: a parenthesis, a dash, or a comma followed by
        # something, in the NAME column, where a town belongs in `city`.
        suspects = c.execute(text(
            "SELECT id, name, city FROM cemeteries "
            "WHERE name ~ '[(]' OR name ~ ' - ' OR name ~ ',' OR name ~ ' in ' "
            "ORDER BY name"
        )).all()
        print(f"[cemetery report] names matching a disambiguation pattern "
              f"( '(' | ' - ' | ',' | ' in ' ): {len(suspects)}")
        for s in suspects:
            print(f"    name={s.name!r}  city={s.city!r}")
        shared = c.execute(text(
            "SELECT name, count(*) AS n, count(DISTINCT coalesce(city,'')) AS towns "
            "FROM cemeteries GROUP BY name HAVING count(*) > 1 ORDER BY n DESC"
        )).all()
        print(f"[cemetery report] names held by more than one row: {len(shared)}")
        for s in shared:
            print(f"    name={s.name!r}  rows={s.n}  distinct towns={s.towns}")

    label = "POST-DEPLOY" if post else "PRE-FLIGHT"
    verdict = ("PASS" if ok else "FAIL — see the lines above")
    extra = "" if post else (" — the deploy should apply all four" if ok else "")
    print(f"\n{label}: {verdict}{extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

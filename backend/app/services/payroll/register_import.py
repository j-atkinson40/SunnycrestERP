"""Import a parsed Payroll Register into `payroll_checks`.

Payroll 4, Phase 1. The parse is `register_parser`; this is the part that
writes rows, and the part that has to be safe to run twice.

⚠️ **IDEMPOTENT ON (tenant, check number, check date, employee id), ENFORCED
BY A UNIQUE CONSTRAINT AND NOT BY A LOOKUP ALONE.** The natural way to use
this is to pull a fresh year from Payentry and upload it, so overlapping
uploads are the normal case rather than the exception. A duplicate check is
counted and skipped, never updated: the register is a historical document, and
a second upload of the same week that CHANGED a stored check would mean either
the parse or Payentry had changed its mind, and both need a person.

⚠️ **A CHECK THAT FAILED VALIDATION IS NOT IMPORTED.** `validate_check` has
already compared each check's lines against its own printed totals. A check
that does not add up means the PARSE is wrong — Payentry's totals are the
authority — and importing it would understate somebody's dues by exactly the
lines that went missing, with nothing downstream to notice. Failures are
returned in the report so a person sees them.

⚠️ **NOTHING IS WRITTEN TO DISK AND THE PDF IS NOT STORED.** It carries names,
pay rates, child support and garnishment lines. Only the parsed rows and the
filename survive the request.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payroll_report import (
    PayrollCheck,
    PayrollCheckLine,
    PayrollRegisterImport,
)
from app.services.payroll.register_parser import (
    RegisterParseError,
    parse_register,
    union_salary_anomalies,
)


@dataclass
class ImportResult:
    import_id: str
    pages: int
    checks_parsed: int
    checks_inserted: int
    checks_duplicate: int
    checks_failed: int
    summary_blocks_skipped: int
    report: dict


def _report(result, inserted_keys, duplicate_keys) -> dict:
    """What a person needs to look at after an import.

    ⚠️ Stored on the import row, not only returned. These are the findings that
    need a human — an unknown code, an employee id with two names, a check
    carrying both salary and union dues — and a finding that only ever existed
    in a response body is a finding nobody can audit later.
    """
    return {
        "unknown_codes": dict(result.unknown_codes),
        "unsplit_glued_tokens": result.unsplit_glued_tokens,
        # Reported, never merged: a second name is either a parse fault or a
        # real name change, and only a person can tell which.
        "ambiguous_names": {
            emp_id: candidates for emp_id, candidates in result.ambiguous_names.items()
        },
        # Union members are hourly. Both on one check is a contradiction to
        # resolve in Payentry, not in code.
        "union_salary_anomalies": [
            {"emp_id": c.emp_id, "check_number": c.check_number,
             "check_date": c.check_date.isoformat() if c.check_date else None}
            for c in union_salary_anomalies(result.checks)
        ],
        "failed_checks": [
            {"emp_id": c.emp_id, "check_number": c.check_number,
             "page": c.page, "why": why}
            for c, why in result.failed
        ],
        "duplicate_checks": [
            {"check_number": n, "check_date": d.isoformat() if d else None, "emp_id": e}
            for n, d, e in duplicate_keys
        ],
        "inserted": len(inserted_keys),
    }


def import_register(
    db: Session,
    *,
    tenant_id: str,
    content: bytes,
    filename: str,
    uploaded_by_user_id: str | None,
) -> ImportResult:
    """Parse `content` and insert every check that validates.

    Raises `RegisterParseError` if the bytes are not a readable register.
    """
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            result = parse_register(pdf)
    except RegisterParseError:
        raise
    except Exception as exc:                     # pdfplumber raises broadly
        raise RegisterParseError(f"could not read the register: {exc}") from exc

    # ⚠️ A register with no checks AT ALL is a refusal, not an empty success.
    # It means the file is not a Payroll Register, or its layout changed — and
    # "imported 0 checks" reads as "nothing new this week" to whoever ran it.
    if not result.checks and not result.failed:
        raise RegisterParseError(
            "no checks found — is this a Payentry Payroll Register? "
            f"({result.pages} pages read, {result.summary_blocks} total blocks skipped)"
        )

    existing = {
        (number, check_date, emp_id)
        for number, check_date, emp_id in db.execute(
            select(PayrollCheck.check_number, PayrollCheck.check_date,
                   PayrollCheck.emp_id)
            .where(PayrollCheck.tenant_id == tenant_id)
        ).all()
    }

    record = PayrollRegisterImport(
        tenant_id=tenant_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        pages=result.pages,
        checks_parsed=len(result.checks),
        checks_failed=len(result.failed),
        summary_blocks_skipped=result.summary_blocks,
        report={},
    )
    db.add(record)
    db.flush()

    inserted_keys: list[tuple] = []
    duplicate_keys: list[tuple] = []
    seen_in_this_file: set[tuple] = set()

    for chk in result.checks:
        key = chk.idempotency_key
        # ⚠️ Checked against this file too, not only the database. A register
        # that printed the same check twice must not insert it twice, and the
        # unique constraint would abort the whole transaction rather than skip.
        if key in existing or key in seen_in_this_file:
            duplicate_keys.append(key)
            continue
        seen_in_this_file.add(key)

        row = PayrollCheck(
            tenant_id=tenant_id,
            import_id=record.id,
            emp_id=chk.emp_id,
            # The display name resolved by frequency across the whole register,
            # not the name on this one block.
            person=result.display_names.get(chk.emp_id, chk.person),
            check_number=chk.check_number or "",
            check_date=chk.check_date,
            check_type=chk.check_type,
            batch=chk.batch,
            net=chk.net,
            base_rate=chk.base_rate,
            printed_total_earnings=chk.printed_total_earnings,
            printed_total_hours=chk.printed_total_hours,
            printed_total_deductions=chk.printed_total_deductions,
            source_page=chk.page,
        )
        db.add(row)
        db.flush()
        for line in chk.lines:
            db.add(PayrollCheckLine(
                tenant_id=tenant_id,
                check_id=row.id,
                kind=line.kind,
                code=line.code,
                description=line.description,
                hours=line.hours,
                rate=line.rate,
                # Stored with its sign. A reimbursement is a negative
                # deduction; abs() would overstate the deduction total by
                # twice the amount.
                amount=line.amount,
            ))
        inserted_keys.append(key)

    record.checks_inserted = len(inserted_keys)
    record.checks_duplicate = len(duplicate_keys)
    record.report = _report(result, inserted_keys, duplicate_keys)
    db.flush()

    return ImportResult(
        import_id=record.id,
        pages=result.pages,
        checks_parsed=len(result.checks),
        checks_inserted=len(inserted_keys),
        checks_duplicate=len(duplicate_keys),
        checks_failed=len(result.failed),
        summary_blocks_skipped=result.summary_blocks,
        report=record.report,
    )

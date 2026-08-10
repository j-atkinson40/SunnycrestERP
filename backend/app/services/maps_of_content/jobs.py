"""JOBS (displayed **Task**) — the entity service + the polymorphic
reference spine (Reframe R-1).

WRITE-BOUNDARY HONESTY (the named-people precedent): a ref is
existence-checked per kind AT WRITE — a stored ref can never rot silently
to nothing from day one. READ-SIDE: resolution SKIPS dead refs (plainer,
never stale — a ref whose target has since died renders nothing to
viewers) while `dead_refs` rides the payload so EDIT surfaces show them
reclaimable (the orphaned-caption grammar, at the ref tier).

REF_CHECKERS / REF_RESOLVERS — the house dispatch-dict pattern (BUILDERS /
_DIRECT_QUERIES / PEEK_BUILDERS precedents). Adding a ref kind = one
checker + one resolver + the CHECK constraint; capability/document kinds
slot in by exactly that shape.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Sequence

from sqlalchemy.orm import Session

from app.models.moc_job import MoCJob, MoCJobRef

logger = logging.getLogger(__name__)

# ⚠️ THE `focus` REF KIND IS REMOVED (FR-1). THE `focus` BEAT KIND IS NOT —
# two vocabularies shared a word in this module and only the first is gone.
#
#   REMOVED  `MoCJobRef.ref_kind == "focus"` — a job ref naming a Focus. It
#            resolved ONLY against `focus_templates.template_slug`, and
#            `registerFocus()` has no field that can name a template_slug, so
#            the kind could not point at any Focus the runtime renders. Zero
#            rows ever existed on production or dev, and the six accounting
#            jobs reach their surfaces through `triage_queue` refs instead.
#
#   KEPT     the BEAT kind `"focus"` — `platform_map.py:98` builds
#            `{"key": "exhibit", "kind": "focus"}` by querying FocusTemplate
#            directly and calling `focus_miniature`, never touching MoCJobRef.
#            The exhibit grammar is untouched.
#
# ⚠️ THE DATABASE STILL PERMITS IT. `ck_moc_job_ref_kind` (this model's
# `__table_args__`, created by `r132_moc_job.py:69`) still reads
# `ref_kind IN ('automation', 'triage_queue', 'focus')`. Tightening it is a
# migration and was deliberately NOT taken here — reported, not decided. Until
# it lands the service refuses a focus ref and the database would accept one
# written around the service.
REF_KINDS = ("automation", "triage_queue")


class JobValidationError(ValueError):
    """A rejected job/ref write — HTTP 400 (404 on not-found)."""


# ── Existence checkers (the WRITE boundary) ─────────────────────────────


def _check_automation(db: Session, key: str) -> bool:
    from app.models.moc_task_catalog import MoCTaskCatalog

    row = db.get(MoCTaskCatalog, key)
    return row is not None and row.is_active


def _check_triage_queue(db: Session, key: str) -> bool:
    from app.services.triage.registry import platform_queue_ids

    return key in platform_queue_ids()


REF_CHECKERS: dict[str, Callable[[Session, str], bool]] = {
    "automation": _check_automation,
    "triage_queue": _check_triage_queue,
}


# ── Resolvers (the READ side — skip-dead, never stale) ──────────────────


def _resolve_automation(db: Session, key: str) -> dict[str, Any] | None:
    from app.models.moc_task_catalog import MoCTaskCatalog
    from app.services.maps_of_content.task_catalog import resolve_task

    row = db.get(MoCTaskCatalog, key)
    if row is None or not row.is_active:
        return None
    resolved = resolve_task(db, row)
    return {
        "kind": "automation",
        "key": key,
        "label": row.name,
        "automation": resolved,
    }


def _resolve_triage_queue(db: Session, key: str) -> dict[str, Any] | None:
    from app.services.triage.registry import platform_queue_config

    cfg = platform_queue_config(key)
    if cfg is None:
        return None
    return {
        "kind": "triage_queue",
        "key": key,
        "label": cfg.queue_name,
        "icon": getattr(cfg, "icon", None),
        "href": f"/triage/{key}",
    }


REF_RESOLVERS: dict[str, Callable[[Session, str], dict[str, Any] | None]] = {
    "automation": _resolve_automation,
    "triage_queue": _resolve_triage_queue,
}


# ── CRUD (caller commits, the house pattern) ────────────────────────────



# ── Suite map expression (2026-07-20) — glance sources + never-faces ────
#
# GLANCE SOURCES: a job may declare `ponder.glance_source` — a key into
# this dispatch dict (the house pattern). The resolver computes a small
# LIVE line for the card (e.g. Watch the cash carries the real position).
# Honest absence: a source that can't stand behind a number returns the
# teach-face text instead, never a fake zero.


def _glance_cash_position(db: Session, tenant_id: str | None) -> dict[str, Any] | None:
    if not tenant_id:
        return None
    try:
        from app.models.plaid import BankAccount, PlaidItem
        rows = (
            db.query(BankAccount)
            .join(PlaidItem, PlaidItem.id == BankAccount.plaid_item_id)
            .filter(BankAccount.tenant_id == tenant_id,
                    BankAccount.is_active.is_(True),
                    PlaidItem.is_active.is_(True),
                    BankAccount.account_type == "depository",
                    BankAccount.current_balance.isnot(None))
            .all()
        )
        if not rows:
            return {"kind": "teach", "text": "Connect a bank to see cash here"}
        cash = sum(float(a.current_balance) for a in rows)
        as_ofs = [a.balance_as_of for a in rows if a.balance_as_of]
        return {
            "kind": "live",
            "text": f"${cash:,.0f} on hand",
            "as_of": min(as_ofs).isoformat() if as_ofs else None,
        }
    except Exception:
        return None


GLANCE_SOURCES: dict[str, Callable[[Session, str | None], dict[str, Any] | None]] = {
    "cash_position": _glance_cash_position,
}


# NEVER-FACE COMPLETION-BY-REALITY: a coming job declares
# `ponder.coming = {"checker": <key>, ...}`. The checker READS REALITY —
# a code-capability probe, never a flag — so the arc landing flips the
# card real with zero manual steps.


def _exceptions_arc_landed(db: Session) -> bool:
    """Real when the exceptions arc ships its verbs: a credit-memo model
    OR a write-off verb on the sales service."""
    try:
        import app.services.sales_service as ss
        if hasattr(ss, "write_off_invoice"):
            return True
        import importlib
        importlib.import_module("app.models.credit_memo")
        return True
    except Exception:
        return False


def _tax_filing_arc_landed(db: Session) -> bool:
    """Real when sales-tax accumulation ships: a tax-filing service module
    or a tax_periods table."""
    try:
        import importlib
        importlib.import_module("app.services.tax_filing_service")
        return True
    except Exception:
        pass
    try:
        from sqlalchemy import inspect as sa_inspect
        return "tax_periods" in sa_inspect(db.get_bind()).get_table_names()
    except Exception:
        return False


COMING_CHECKERS: dict[str, Callable[[Session], bool]] = {
    "exceptions_arc": _exceptions_arc_landed,
    "tax_filing_arc": _tax_filing_arc_landed,
}


def coming_state(db: Session, job: MoCJob) -> dict[str, Any] | None:
    """None for a normal job; {"is_coming": bool} for a declared
    never-face — is_coming flips FALSE the moment reality says the arc
    landed (the card renders real from that boot onward)."""
    cfg = (job.ponder or {}).get("coming")
    if not cfg:
        return None
    checker = COMING_CHECKERS.get(cfg.get("checker", ""))
    landed = bool(checker and checker(db))
    return {"is_coming": not landed, "checker": cfg.get("checker")}


def create_job(
    db: Session,
    *,
    name: str,
    scope: str = "vertical_default",
    vertical: str | None = None,
    icon: str | None = None,
    description: str | None = None,
    task_type: str | None = None,
    display_order: int = 0,
) -> MoCJob:
    if scope == "platform_default":
        if vertical is not None:
            raise JobValidationError("a platform_default job is vertical-less")
    elif scope == "vertical_default":
        if vertical is None:
            raise JobValidationError("a vertical_default job requires its vertical")
    else:
        raise JobValidationError(f"scope {scope!r} is not a job tier (option A)")
    dup = (
        db.query(MoCJob)
        .filter(
            MoCJob.scope == scope, MoCJob.vertical == vertical,
            MoCJob.name == name, MoCJob.is_active.is_(True),
        )
        .first()
    )
    if dup is not None:
        raise JobValidationError(f"a job named {name!r} already exists in this scope")
    job = MoCJob(
        id=str(uuid.uuid4()), scope=scope, vertical=vertical, name=name,
        icon=icon, description=description, task_type=task_type,
        display_order=display_order,
    )
    db.add(job)
    db.flush()
    return job


def add_ref(
    db: Session, *, job_id: str, ref_kind: str, ref_key: str,
    label: str | None = None, display_order: int = 0,
) -> MoCJobRef:
    """THE WRITE BOUNDARY — the ref must exist NOW, per kind. A dangling
    write is refused loudly; decay after the fact is the read side's
    skip-and-reclaim problem."""
    job = db.get(MoCJob, job_id)
    if job is None or not job.is_active:
        raise JobValidationError("job not found")
    if ref_kind not in REF_KINDS:
        raise JobValidationError(f"ref_kind must be one of {REF_KINDS}")
    if not REF_CHECKERS[ref_kind](db, ref_key):
        raise JobValidationError(
            f"{ref_kind} {ref_key!r} does not resolve — refusing to store a "
            "dead reference"
        )
    ref = MoCJobRef(
        id=str(uuid.uuid4()), job_id=job_id, ref_kind=ref_kind,
        ref_key=ref_key, label=label, display_order=display_order,
    )
    db.add(ref)
    db.flush()
    return ref


def remove_ref(db: Session, *, ref_id: str) -> bool:
    ref = db.get(MoCJobRef, ref_id)
    if ref is None:
        return False
    db.delete(ref)
    db.flush()
    return True


def list_jobs(
    db: Session, *, vertical: str | None, include_platform: bool = True
) -> list[MoCJob]:
    q = db.query(MoCJob).filter(MoCJob.is_active.is_(True))
    if include_platform:
        q = q.filter(
            (
                (MoCJob.scope == "vertical_default") & (MoCJob.vertical == vertical)
            )
            | (MoCJob.scope == "platform_default")
        )
    else:
        q = q.filter(MoCJob.scope == "vertical_default", MoCJob.vertical == vertical)
    return q.order_by(MoCJob.display_order, MoCJob.name).all()


def resolve_job(db: Session, job: MoCJob) -> dict[str, Any]:
    """The job + its refs resolved per kind. DEAD REFS SKIP the resolved
    list (viewers see the plainer truth) and surface in `dead_refs`
    (the edit surface's reclaim list — id + kind + key, enough to remove
    or repoint)."""
    resolved: list[dict[str, Any]] = []
    dead: list[dict[str, Any]] = []
    for ref in job.refs:
        payload = REF_RESOLVERS[ref.ref_kind](db, ref.ref_key)
        if payload is None:
            dead.append({"id": ref.id, "kind": ref.ref_kind, "key": ref.ref_key})
            continue
        if ref.label:
            payload["label"] = ref.label  # authored label wins
        payload["ref_id"] = ref.id
        resolved.append(payload)
    return {
        "id": job.id,
        "scope": job.scope,
        "vertical": job.vertical,
        "name": job.name,
        "icon": job.icon,
        "description": job.description,
        "task_type": job.task_type,
        "display_order": job.display_order,
        "refs": resolved,
        "dead_refs": dead,
    }


# ── THE JOB PONDER (Reframe R-2) — the whole job's story ─────────────────
#
# A feeder on the landed composition-deriver contract (the same overlay,
# the same script shape): AUTHORED FRAMING (derived-honest placeholder
# until the operator's R-3 voice; captions on job.ponder JSONB, the
# caption-editor pattern) → AUTOMATION beats from the refs (essence +
# honest WHEN with T-0 authority truth + a ponder deep-link to the
# automation's full walkthrough) → HUMAN-WORK beats (the QUEUE beat with
# the permission-aware live pending count + the /triage deep link; the
# FOCUS beat via focus_miniature — the exhibit grammar) → closing (the
# area page). Dead refs skip plainer (R-1's read semantics).


def _first_sentence(text: str | None, limit: int = 140) -> str | None:
    if not text:
        return None
    head = text.strip().split(". ")[0].strip().rstrip(".")
    if not head:
        return None
    if len(head) > limit:
        head = head[: limit - 1].rstrip() + "…"
    return head


# ── The accounting-config beat (MAP-2) ─────────────────────────────────────


_KEYWORD_LABELS = {
    "bank_fee": "bank fee",
    "payroll": "payroll draw",
    "nsf": "returned item",
}


def _accounting_config_beats(db: Session, company_id: str) -> list[tuple[str, str]]:
    """The tenant's OWN accounting configuration, read live.

    "Two settings decide whether payments post; yours are unset" is truer than
    any sentence anyone can write into a description, because it is read rather
    than asserted — and it corrects itself the moment someone configures them.

    THE STATE VOCABULARY IS THE POINT, AND IT IS FOUR STATES, NOT THREE.
    `_accounting_gl_payload`'s docstring says "Three states, per L-2.1c" and the
    code produces FOUR — `mapped`, `intentional`, `unmapped`, `dangling`. Each
    earns its own sentence because each implies a DIFFERENT ACTION:

      mapped      nothing to do; say what it means, not that a box is ticked.
      intentional a settled DECISION, never a gap. `payroll` and `nsf` are both
                  intentional on the production chart and both CORRECT — no
                  single account is the right answer for either. Copy that
                  implied something was missing would tell an operator to fix
                  what they deliberately chose, which is the exact bug
                  `_keyword_gl_payload`'s docstring records the configure script
                  having shipped.
      unmapped    nobody has decided; name what it blocks and where it is set.
      dangling    SOMETHING BROKE. The only one of the four that is evidence of
                  a problem rather than a decision — an account was chosen and
                  no longer resolves. Folding it into `unmapped` would tell an
                  operator to configure what they already configured, and would
                  hide the one state that means an account went away.

    Reads through the PANEL payloads rather than the posting resolvers.
    `resolve_ar_account` raises identically for unset and deliberately-unmapped
    (`if not ar_id` — `null` is falsy), which is right for a poster (both mean
    "cannot post") and wrong for a teaching surface, where the two must never
    read the same.

    Returns `[(beat_key, text)]`, empty when there is nothing honest to say.
    ~5 queries; the caller gates before invoking.
    """
    from app.api.routes.reconciliation import (
        _accounting_gl_payload, _keyword_gl_payload, _payment_bank_payload,
    )
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        return []                                   # honest absence

    try:
        ar = next(
            (p for p in _accounting_gl_payload(db, company)["purposes"]
             if p["purpose"] == "ar"), None,
        )
        bank = _payment_bank_payload(db, company)
        keywords = _keyword_gl_payload(db, company)["classifications"]
    except Exception:
        # A RESOLVER RAISING IS ABSENCE, NOT CONTENT. The feed beat's rule —
        # omitted, never faked. A half-rendered configuration claim is worse
        # than no claim, because the half that rendered looks complete.
        logger.warning(
            "[map] accounting-config beat omitted for tenant %s — a resolver "
            "raised; the beat renders nothing rather than a partial truth.",
            company_id, exc_info=True,
        )
        return []

    beats: list[tuple[str, str]] = []

    # ── The posting pair ───────────────────────────────────────────────────
    # TWO SETTINGS IN TWO PLACES, and reporting only one sends an operator away
    # thinking they are done — the `_payment_bank_payload` lesson. `state` means
    # CHOSEN; `can_post` means READY, and they differ exactly when the chosen
    # account has no GL account of its own.
    ar_state = (ar or {}).get("state", "unmapped")
    ar_name = (ar or {}).get("account_name")
    bank_chosen = bank.get("state") == "mapped"
    bank_ready = bool(bank.get("can_post"))
    bank_name = bank.get("account_name")
    # THE DEBITED LEG IS A GL ACCOUNT, NOT THE BANK. `account_name` is the
    # FinancialAccount ("Operating"); `gl_account_name` is what the entry debits
    # ("CASH CHECKING"). The posting sentence names ledger legs, so it must use
    # the GL name — naming the bank there teaches the wrong vocabulary, and the
    # operator reading the ledger would not find "Operating" on it.
    cash_name = bank.get("gl_account_name") or bank_name

    if ar_state == "dangling":
        beats.append((
            "config:ar",
            "The accounts-receivable account was set but no longer resolves — "
            "it may have been deactivated. Customer payments stay recorded-only "
            "until it is re-picked.",
        ))
    elif ar_state == "intentional":
        beats.append((
            "config:ar",
            "You have chosen not to map an accounts-receivable account, so "
            "customer payments stay recorded-only.",
        ))
    elif ar_state == "mapped" and bank_ready:
        beats.append((
            "config:posting",
            f"Customer payments post as they are received — debited to "
            f"{cash_name}, credited to {ar_name} — so a matched deposit clears "
            f"against an entry that already exists.",
        ))
    elif ar_state == "mapped" and bank_chosen and not bank_ready:
        beats.append((
            "config:posting",
            f"{bank_name} is chosen to receive customer payments, but it has "
            f"no GL account of its own, so nothing posts yet. That one is set "
            f"on the account itself.",
        ))
    elif ar_state == "mapped":
        beats.append((
            "config:posting",
            f"{ar_name} is set for receivables, but no bank account is chosen "
            f"to receive customer payments, so nothing posts yet.",
        ))
    else:
        # Production's current state, and the beat's most valuable one.
        # "Nothing is configured" is a FACT ABOUT THIS TENANT, not an absence of
        # data — so it renders, where a failed read would not.
        beats.append((
            "config:posting",
            "Customer payments are recorded but not posted: no receivables "
            "account is set, and no bank account is chosen to receive them. "
            "Both live in Settings, under Financial accounts. Until they are "
            "set, every payment is recorded and reported as unposted — nothing "
            "is lost, but the ledger does not yet show the cash.",
        ))

    # ── The keyword map ────────────────────────────────────────────────────
    for k in keywords:
        label = _KEYWORD_LABELS.get(k["classification"], k["classification"])
        state = k["state"]
        if state == "mapped":
            text = (f"A line reading like a {label} books straight to "
                    f"{k['account_name']}.")
        elif state == "intentional":
            text = (f"{label.capitalize()} lines are deliberately left for a "
                    f"person — no single account is the right answer, so they "
                    f"wait in Books Review instead of booking automatically.")
        elif state == "dangling":
            text = (f"The {label} account no longer resolves — it may have been "
                    f"deactivated. Re-pick it and those lines book again.")
        else:
            text = (f"{label.capitalize()} lines have no account yet, so they "
                    f"cannot book. Set one in the keyword map, or leave it "
                    f"unset deliberately.")
        beats.append((f"config:keyword:{k['classification']}", text))

    # ── The structural frame ───────────────────────────────────────────────
    # PHRASED AS THE DESIGN, NOT THE STATE. "clears against a payment already on
    # the books" would be FALSE in production today, because whether a payment is
    # on the books depends on the very configuration this beat just reported.
    # "when one exists" is the narrow true thing in every state.
    beats.append((
        "config:frame",
        "A line you classify or code books its journal entry before it clears; "
        "a line matched to a payment clears against that payment's own entry, "
        "when one exists.",
    ))
    return beats


def build_job_ponder_script(
    db: Session, *, job_id: str, company_id: str | None = None, user=None,
) -> dict[str, Any]:
    """The job's staged walkthrough. `user` (the tenant read) scopes the
    queue counts permission-aware — no access, no count, never a lie."""
    job = db.get(MoCJob, job_id)
    if job is None or not job.is_active:
        raise JobValidationError("job not found")
    resolved = resolve_job(db, job)
    captions: dict = dict((job.ponder or {}).get("captions") or {})

    autos = [r for r in resolved["refs"] if r["kind"] == "automation"]
    queues = [r for r in resolved["refs"] if r["kind"] == "triage_queue"]
    # No `focuses` list — the `focus` REF kind is gone (FR-1). This was the
    # bridge that turned job refs into focus BEATS; the beat kind itself
    # survives and is still emitted by `platform_map.py` from a FocusTemplate
    # read, with no ref involved.

    beats: list[dict] = []

    def _beat(key: str, kind: str, derived: str, **extra) -> None:
        authored = captions.get(key)
        beats.append({
            "key": key, "kind": kind,
            "text": authored or derived,
            "derived_text": derived,
            "authored": bool(authored),
            **extra,
        })

    # THE FRAMING — the operator's voice in R-3; a derived-honest
    # placeholder meanwhile (the description + the composition summary).
    pieces = []
    if job.description:
        pieces.append(job.description.rstrip("."))
    counts = []
    if autos:
        counts.append(f"{len(autos)} automation{'s' if len(autos) != 1 else ''}")
    if queues:
        counts.append(
            f"{len(queues)} review surface{'s' if len(queues) != 1 else ''}"
        )
    if counts:
        pieces.append(f"{' and '.join(counts)} work this job")
    _beat("opening", "opening", (". ".join(pieces) + ".") if pieces else job.name)

    # THE FEED BEAT (Plaid B-3 — the map's full story): when this job's
    # automations include the bank pull, the story opens with the feed's
    # live state — connection, accounts, and the honest uncategorized
    # count. Tenant-scoped; HONEST ABSENCE when no tenant context or no
    # connection (the setup card is the deep link either way).
    if company_id and any(
        (r["automation"].get("name") == "Pull Bank Transactions")
        for r in autos
    ):
        from app.models.plaid import BankTransaction, PlaidItem
        item = (
            db.query(PlaidItem)
            .filter(PlaidItem.tenant_id == company_id,
                    PlaidItem.is_active.is_(True))
            .first()
        )
        if item is not None and item.status == "active":
            n_accounts = len(item.accounts)
            uncat = (
                db.query(BankTransaction)
                .filter(BankTransaction.tenant_id == company_id,
                        BankTransaction.expense_category.is_(None),
                        BankTransaction.removed_at.is_(None))
                .count()
            )
            live = (
                db.query(BankTransaction)
                .filter(BankTransaction.tenant_id == company_id,
                        BankTransaction.removed_at.is_(None))
                .count()
            )
            cat_clause = (
                f" {live - uncat} of {live} categorized; "
                f"{uncat} awaiting a category." if live else ""
            )
            _beat(
                "feed", "setup",
                f"The feed: {item.institution_name or 'your bank'} connected "
                f"— {n_accounts} account{'s' if n_accounts != 1 else ''} "
                f"feeding.{cat_clause}",
                link={"href": "/bridgeable-map/Accounting",
                      "label": "Open the connection card"},
            )
        elif item is not None:  # degraded — active-but-unhealthy status
            # THE DEGRADED FACE — the honest warning; healing lives on the
            # Integrations card (the re-connect path).
            _beat(
                "feed", "setup",
                f"{item.institution_name or 'The bank'} needs re-connecting "
                "— the feed is paused until an administrator re-authorizes "
                "it on the Integrations page.",
                link={"href": "/bridgeable-map/Integrations",
                      "label": "Re-connect on Integrations"},
            )
        else:
            # THE NEVER-CONNECTED FACE — the beat TEACHES what the
            # connection is and routes to onboarding: the job's story
            # complete and true before the machinery exists.
            _beat(
                "feed", "setup",
                "This job runs on a live bank feed — transactions pull in "
                "on a schedule and land ready to match. Nothing is "
                "connected yet; the setup walk starts in onboarding.",
                ponder_ref={"overlay_id": "onboarding:connect-your-bank",
                            "label": "Walk the setup"},
            )

    # THE ACCOUNTING-CONFIG BEAT (MAP-2): whether this tenant's books
    # actually tie is a question about CONFIGURATION, and configuration is
    # state — so it is READ, never written into a description. The feed
    # beat above is the precedent: live, tenant-scoped, honest absence.
    #
    # ⚠️ GATED ON A REF, NOT ON THE JOB'S NAME. r157 renamed and split the
    # accounting cards, which is exactly how a name-match silently stops
    # matching; a job that teaches Books Review is the job whose story needs
    # to know whether Books Review can book. Data-driven, so a future rename
    # cannot orphan it.
    #
    # ⚠️ AND GATED BEFORE THE RESOLVERS RUN. `_accounting_config_beats` costs
    # ~5 queries; computing it for eleven cards and discarding nine would be
    # forty-five queries to render the Accounting area. The `any(...)` below
    # short-circuits on a list already in memory, so the nine pay nothing.
    if company_id and any(
        r["key"] == "reconciliation_review_triage" for r in queues
    ):
        for key, text in _accounting_config_beats(db, company_id):
            _beat(key, "setup", text)

    # THE STORY BEATS (D-11 U-4 — the capability-ponder grammar): a job
    # may carry an authored sequence in `ponder.story` — a list of
    # {key, text, link?} entries seeded derived-honest (the operator's
    # voice overrides per-beat via the same captions mechanism). Born for
    # "Enter an order"'s entry-path walk; generic for any job whose story
    # is bigger than its refs.
    for entry in (job.ponder or {}).get("story") or []:
        key = entry.get("key")
        text = entry.get("text")
        if not key or not text:
            continue  # malformed seed content — skip honestly
        extra = {}
        if entry.get("link"):
            extra["link"] = entry["link"]
        if entry.get("ponder_ref"):
            extra["ponder_ref"] = entry["ponder_ref"]
        _beat(f"story:{key}", "story", text, **extra)

    # THE AUTOMATION BEATS — the means, each deep-linking its full ponder.
    for r in autos:
        a = r["automation"]
        essence = _first_sentence(a.get("description"))
        when = a.get("runtime_schedule_summary") if (
            a.get("schedule_authority") == "runtime_scheduler"
        ) else (a.get("derived_frequency") or a.get("frequency"))
        parts = [a["name"]]
        if essence:
            parts.append(essence)
        if when:
            parts.append(str(when).rstrip("."))
        _beat(
            f"automation:{r['key']}", "task", ". ".join(parts) + ".",
            ponder_ref={
                "overlay_id": r["key"],
                "label": f"Walk {a['name']}",
            },
        )

    # THE QUEUE BEATS — where the exceptions land; the count is the truth
    # of NOW, permission-aware (no access → no number, never a lie).
    for r in queues:
        count = None
        if user is not None:
            from app.services.triage.engine import queue_count

            try:
                count = queue_count(db, user=user, queue_id=r["key"])
            except Exception:
                count = None  # no access / no queue → honest absence
        derived = (
            f"{r['label']} — where the exceptions land for a person to decide."
        )
        if count is not None:
            derived += (
                f" {count} waiting now." if count else " Nothing waiting now."
            )
        _beat(
            f"queue:{r['key']}", "downstream", derived,
            queue_id=r["key"], queue_label=r["label"],
            link={"href": r["href"], "label": f"Open {r['label']}"},
        )

    # THE FOCUS BEATS ARE GONE FROM THE JOB SCRIPT (FR-1) — a job can no longer
    # carry a `focus` ref, so there is nothing here to turn into one. The
    # `focus_miniature` exhibit grammar is NOT removed: `platform_map.py:88-102`
    # still builds a `kind: "focus"` beat from a direct FocusTemplate read. What
    # went is the bridge, not the destination.

    # THE CLOSING — home is the area page.
    area = job.task_type or "General"
    _beat(
        "closing", "closing",
        f"This task lives in {area} — its automations and the rest of the "
        "area are one click away.",
        link={"href": f"/bridgeable-map/{area}", "label": f"Open the {area} page"},
    )

    live_keys = {b["key"] for b in beats}
    orphaned = {k: v for k, v in captions.items() if k not in live_keys}

    return {
        "task_id": f"job:{job.id}",
        "task_name": job.name,
        "workflow_name": "",
        "beats": beats,
        "orphaned_captions": orphaned,
        "mirror_drift": [],
        "is_live": False,
        "vertical": job.vertical,
        "workflow_id": None,
        "fires": None,
        "task_scope": "platform_default",
        "owned": False,
        "schedule_authority": "moc",
    }


def save_job_caption(
    db: Session, *, job_id: str, beat_key: str, text: str | None
) -> dict[str, str]:
    """Author (or clear) a framing caption — platform pedagogy on the job
    row's ponder JSONB (the task-ponder semantics verbatim). Admin only."""
    job = db.get(MoCJob, job_id)
    if job is None:
        raise JobValidationError("job not found")
    block = dict(job.ponder or {})
    captions = dict(block.get("captions") or {})
    if text is None or not text.strip():
        captions.pop(beat_key, None)
    else:
        captions[beat_key] = text.strip()
    block["captions"] = captions
    job.ponder = block  # reassign — JSONB change detection
    db.commit()
    return captions


def job_card_payload(
    db: Session, job: MoCJob, *, user=None
) -> dict[str, Any]:
    """The area page's job CARD shape — resolve_job + the honest composition
    glance: automation count, live rollup, and the queue's live pending
    count where linked (permission-aware via `user`; no access → None,
    rendered as honest absence)."""
    resolved = resolve_job(db, job)
    autos = [r for r in resolved["refs"] if r["kind"] == "automation"]
    live = sum(
        1 for r in autos
        if any(
            t.get("is_live") and t.get("is_active") is not False
            for t in (r["automation"].get("triggers") or [])
        )
    )
    pending = None
    if user is not None:
        from app.services.triage.engine import queue_count

        total = 0
        counted = False
        for r in resolved["refs"]:
            if r["kind"] != "triage_queue":
                continue
            try:
                total += queue_count(db, user=user, queue_id=r["key"])
                counted = True
            except Exception:
                continue  # no access → this queue contributes no number
        pending = total if counted else None
    resolved["glance"] = {
        "automation_count": len(autos),
        "live_count": live,
        "queue_pending": pending,
    }
    # Suite map expression: the declared glance source's live line +
    # the never-face coming state.
    src = (job.ponder or {}).get("glance_source")
    if src and src in GLANCE_SOURCES:
        tenant_id = getattr(user, "company_id", None) if user is not None else None
        resolved["glance_live"] = GLANCE_SOURCES[src](db, tenant_id)
    resolved["coming"] = coming_state(db, job)
    return resolved

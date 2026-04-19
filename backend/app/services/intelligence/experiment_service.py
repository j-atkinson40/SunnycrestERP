"""A/B experiment assignment and conclusion.

Assignment is deterministic by input_hash so the same input always lands in the
same variant across replays. Traffic split controls how much traffic goes to
variant B (0–100).

Phase 3c — status vocabulary:
  "draft"      Created, not yet receiving traffic
  "running"    Actively routing traffic (written as "active" in legacy rows
               from Phase 1; treated as equivalent on read)
  "completed"  Stopped or promoted. May or may not have a winner_version_id.
"""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.intelligence import IntelligenceExecution, IntelligenceExperiment


# Legacy rows written by Phase 1 use `"active"`; Phase 3c normalizes to
# `"running"`. All read paths accept either.
_RUNNING_STATUSES = ("running", "active")


# Salt keeps experiments from colliding with anything else that might hash
# an input_hash for its own bucketing.
_ASSIGN_SALT = "bridgeable-intelligence-ab-v1"


def get_active_experiment(
    db: Session,
    prompt_id: str,
    company_id: str | None,
) -> IntelligenceExperiment | None:
    """Return the running experiment for (prompt, company), if any.

    Tenant-scoped experiments win over platform-global ones. Accepts both
    the Phase 3c "running" and legacy "active" status values.
    """
    if company_id:
        tenant_exp = (
            db.query(IntelligenceExperiment)
            .filter(
                IntelligenceExperiment.prompt_id == prompt_id,
                IntelligenceExperiment.company_id == company_id,
                IntelligenceExperiment.status.in_(_RUNNING_STATUSES),
            )
            .first()
        )
        if tenant_exp is not None:
            return tenant_exp

    return (
        db.query(IntelligenceExperiment)
        .filter(
            IntelligenceExperiment.prompt_id == prompt_id,
            IntelligenceExperiment.company_id.is_(None),
            IntelligenceExperiment.status.in_(_RUNNING_STATUSES),
        )
        .first()
    )


def find_running_for_prompt(
    db: Session, prompt_id: str, company_id: str | None
) -> IntelligenceExperiment | None:
    """Like get_active_experiment but returns ANY running experiment at this
    scope — useful for enforcing "only one running per prompt" on create."""
    return (
        db.query(IntelligenceExperiment)
        .filter(
            IntelligenceExperiment.prompt_id == prompt_id,
            IntelligenceExperiment.company_id == company_id,
            IntelligenceExperiment.status.in_(_RUNNING_STATUSES),
        )
        .first()
    )


def assign_variant(experiment: IntelligenceExperiment, input_hash: str) -> str:
    """Deterministically assign 'a' or 'b' from experiment + input_hash.

    The same (experiment_id, input_hash) always yields the same variant across
    calls and processes. Traffic split defines what percent goes to B.
    """
    digest = hashlib.sha256(
        f"{_ASSIGN_SALT}:{experiment.id}:{input_hash}".encode("utf-8")
    ).hexdigest()
    # Interpret first 8 hex chars as int, mod 100 → 0–99 bucket
    bucket = int(digest[:8], 16) % 100
    # traffic_split of 50 means buckets 0..49 → 'b', 50..99 → 'a'? No — convention:
    # buckets [0, traffic_split) go to variant B; remainder go to A.
    return "b" if bucket < (experiment.traffic_split or 0) else "a"


def version_for_variant(experiment: IntelligenceExperiment, variant: str) -> str:
    """Return the version_id for the given variant."""
    if variant == "b":
        return experiment.version_b_id
    return experiment.version_a_id


def is_ready_to_conclude(db: Session, experiment_id: str) -> bool:
    """True if the experiment has reached its min_sample_size on BOTH variants."""
    experiment = (
        db.query(IntelligenceExperiment).filter_by(id=experiment_id).first()
    )
    if experiment is None:
        return False

    counts = (
        db.query(
            IntelligenceExecution.experiment_variant,
            func.count(IntelligenceExecution.id),
        )
        .filter(IntelligenceExecution.experiment_id == experiment_id)
        .group_by(IntelligenceExecution.experiment_variant)
        .all()
    )
    by_variant = {variant: n for variant, n in counts}
    return (
        by_variant.get("a", 0) >= experiment.min_sample_size
        and by_variant.get("b", 0) >= experiment.min_sample_size
    )


def conclude(
    db: Session,
    experiment_id: str,
    winner_version_id: str,
    conclusion_notes: str | None = None,
) -> IntelligenceExperiment:
    """Mark experiment completed, set winner, activate winner as prompt's active version."""
    from app.services.intelligence.prompt_registry import activate_version

    experiment = (
        db.query(IntelligenceExperiment).filter_by(id=experiment_id).first()
    )
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")
    if winner_version_id not in (experiment.version_a_id, experiment.version_b_id):
        raise ValueError(
            f"winner_version_id must be one of the experiment's two versions"
        )

    experiment.status = "completed"
    experiment.winner_version_id = winner_version_id
    experiment.conclusion_notes = conclusion_notes
    experiment.concluded_at = datetime.now(timezone.utc)
    db.flush()

    # Activate the winner as the prompt's new active version (retires prior active)
    activate_version(db, winner_version_id)
    db.refresh(experiment)
    return experiment


def start(db: Session, experiment_id: str) -> IntelligenceExperiment:
    """Transition a draft experiment to running. Enforces "one running at a
    time" per (prompt_id, company_id)."""
    exp = db.query(IntelligenceExperiment).filter_by(id=experiment_id).first()
    if exp is None:
        raise ValueError(f"Experiment not found: {experiment_id}")
    if exp.status != "draft":
        raise ValueError(
            f"Can only start a draft experiment; this one is {exp.status!r}"
        )
    conflict = find_running_for_prompt(db, exp.prompt_id, exp.company_id)
    if conflict is not None and conflict.id != exp.id:
        raise ValueError(
            f"Another experiment ({conflict.id}) is already running for this "
            f"prompt at this scope. Stop it before starting a new one."
        )
    exp.status = "running"
    exp.started_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(exp)
    return exp


def stop(
    db: Session, experiment_id: str, reason: str | None = None
) -> IntelligenceExperiment:
    """End a running experiment without picking a winner."""
    exp = db.query(IntelligenceExperiment).filter_by(id=experiment_id).first()
    if exp is None:
        raise ValueError(f"Experiment not found: {experiment_id}")
    if exp.status not in _RUNNING_STATUSES:
        raise ValueError(
            f"Can only stop a running experiment; this one is {exp.status!r}"
        )
    exp.status = "completed"
    exp.conclusion_notes = reason
    exp.concluded_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(exp)
    return exp


def collect_daily_breakdown(
    db: Session, experiment_id: str
) -> list[dict]:
    """Per-day per-variant execution counts + cost, for visualization."""
    date_col = func.date(IntelligenceExecution.created_at).label("day")
    rows = (
        db.query(
            date_col,
            IntelligenceExecution.experiment_variant,
            func.count(IntelligenceExecution.id).label("n"),
            func.sum(IntelligenceExecution.cost_usd).label("cost"),
        )
        .filter(IntelligenceExecution.experiment_id == experiment_id)
        .group_by(date_col, IntelligenceExecution.experiment_variant)
        .order_by(date_col)
        .all()
    )
    # Pack as list of {date, variant_a_count, variant_b_count, variant_a_cost, variant_b_cost}
    by_date: dict[str, dict] = {}
    for row in rows:
        key = (
            row.day.isoformat()
            if hasattr(row.day, "isoformat")
            else str(row.day)
        )
        bucket = by_date.setdefault(
            key,
            {
                "date": key,
                "variant_a_count": 0,
                "variant_b_count": 0,
                "variant_a_cost_usd": 0,
                "variant_b_cost_usd": 0,
            },
        )
        variant = row.experiment_variant
        if variant == "a":
            bucket["variant_a_count"] = int(row.n or 0)
            bucket["variant_a_cost_usd"] = float(row.cost or 0)
        elif variant == "b":
            bucket["variant_b_count"] = int(row.n or 0)
            bucket["variant_b_cost_usd"] = float(row.cost or 0)
    return list(by_date.values())


def collect_p95_per_variant(
    db: Session, experiment_id: str
) -> dict[str, int | None]:
    """Cheap-n-cheerful p95 — sort the variant's latencies and index."""
    out: dict[str, int | None] = {"a": None, "b": None}
    for variant in ("a", "b"):
        rows = [
            r[0]
            for r in db.query(IntelligenceExecution.latency_ms)
            .filter(
                IntelligenceExecution.experiment_id == experiment_id,
                IntelligenceExecution.experiment_variant == variant,
                IntelligenceExecution.latency_ms.isnot(None),
            )
            .order_by(IntelligenceExecution.latency_ms)
            .all()
        ]
        if rows:
            idx = int(0.95 * (len(rows) - 1))
            out[variant] = int(rows[idx])
    return out


def collect_variant_stats(
    db: Session,
    experiment_id: str,
) -> dict[str, dict]:
    """Per-variant stats for results dashboard (sample_count, success_rate, cost, latency)."""
    stats: dict[str, dict] = {}
    for variant in ("a", "b"):
        base = db.query(IntelligenceExecution).filter(
            and_(
                IntelligenceExecution.experiment_id == experiment_id,
                IntelligenceExecution.experiment_variant == variant,
            )
        )
        total = base.count()
        successes = base.filter(IntelligenceExecution.status == "success").count()
        errors = total - successes
        agg = (
            db.query(
                func.avg(IntelligenceExecution.latency_ms),
                func.avg(IntelligenceExecution.input_tokens),
                func.avg(IntelligenceExecution.output_tokens),
                func.sum(IntelligenceExecution.cost_usd),
            )
            .filter(
                IntelligenceExecution.experiment_id == experiment_id,
                IntelligenceExecution.experiment_variant == variant,
            )
            .one()
        )
        avg_latency, avg_in, avg_out, total_cost = agg
        stats[variant] = {
            "sample_count": total,
            "success_count": successes,
            "error_count": errors,
            "avg_latency_ms": float(avg_latency) if avg_latency is not None else None,
            "avg_input_tokens": float(avg_in) if avg_in is not None else None,
            "avg_output_tokens": float(avg_out) if avg_out is not None else None,
            "total_cost_usd": total_cost if total_cost is not None else 0,
            "success_rate": (successes / total) if total else 0.0,
        }
    return stats

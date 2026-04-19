"""Seed Bridgeable Intelligence dev executions — fake traffic for Admin UI.

Populates ~300 executions spread across the last 30 days, with realistic
token counts, latencies, costs, and linkage columns so Phase 3a admin pages
(PromptLibrary, PromptDetail, ExecutionLog, ExecutionDetail) have something
interesting to show.

Also creates ~2 experiments (one active, one concluded) for the
Experiments UI coming in Phase 3c.

Idempotent: safe to re-run. Existing dev executions (tagged with the
`caller_entity_type == "dev_seed"` sentinel) are cleared and regenerated.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python scripts/seed_intelligence_dev_executions.py

Prerequisites:
    - Run scripts/seed_intelligence.py first to create prompts + routes
    - At least one company row exists (uses the first as fake tenant)
"""

from __future__ import annotations

import hashlib
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.intelligence import (  # noqa: E402
    IntelligenceExecution,
    IntelligenceExperiment,
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)


# Sentinel used to find + wipe prior dev-seed rows so re-runs are idempotent
DEV_SEED_SENTINEL = "dev_seed"
TARGET_EXECUTIONS = 300
TARGET_EXPERIMENTS = 2


def _pick_prompts(db: Session, n: int = 12) -> list[IntelligencePrompt]:
    """Pick a mix of platform-global prompts across different domains.

    Phase 3a-polish: always include any vision-capable prompts (check_image,
    pdf extract, etc.) so the UI's VisionContentBlock renders something.
    """
    prompts = (
        db.query(IntelligencePrompt)
        .filter(IntelligencePrompt.company_id.is_(None))
        .all()
    )
    if len(prompts) <= n:
        return prompts

    # Ensure vision-capable prompts are present
    must_include = [p for p in prompts if _is_vision_prompt(p.prompt_key)]

    # Spread across domains for diverse UI data
    by_domain: dict[str, list[IntelligencePrompt]] = {}
    for p in prompts:
        if p in must_include:
            continue
        by_domain.setdefault(p.domain, []).append(p)
    picked: list[IntelligencePrompt] = list(must_include)
    domains = list(by_domain.keys())
    i = 0
    while len(picked) < n and any(by_domain.values()):
        d = domains[i % len(domains)]
        bucket = by_domain[d]
        if bucket:
            picked.append(bucket.pop(0))
        i += 1
    return picked[:n]


def _is_vision_prompt(prompt_key: str) -> bool:
    """Heuristic match for vision-capable prompt keys."""
    return any(
        tok in prompt_key
        for tok in ("check_image", "pdf", "price_list_pdf", "scan", "document")
    )


def _pick_active_version(
    db: Session, prompt_id: str
) -> IntelligencePromptVersion | None:
    return (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt_id,
            IntelligencePromptVersion.status == "active",
        )
        .first()
    )


def _pick_route(
    db: Session, key: str
) -> IntelligenceModelRoute | None:
    return (
        db.query(IntelligenceModelRoute)
        .filter(IntelligenceModelRoute.route_key == key)
        .first()
    )


# Caller-module mix — mirrors real traffic patterns from Phase 2c
CALLER_MODULES = [
    "scribe.generate_arrangement",
    "scribe.extract_lifeline",
    "briefing.generate_admin_briefing",
    "briefing.generate_plant_manager_briefing",
    "accounting.analyze_coa",
    "accounting.classify_expense",
    "agents.ar_collections",
    "call_extraction_service.extract_order_from_transcript",
    "urn_intake_agent.process_intake_email",
    "command_bar.interpret",
    "kb_retrieval.synthesize",
    "workflows.interpret_transcript",
]

# Entity type samples for linkage
ENTITY_TYPE_SAMPLES = [
    ("fh_case", "caller_fh_case_id"),
    ("agent_job", "caller_agent_job_id"),
    ("ringcentral_call_log", "caller_ringcentral_call_log_id"),
    ("kb_document", "caller_kb_document_id"),
    ("price_list_import", "caller_price_list_import_id"),
    ("user", None),
    (None, None),
    (None, None),  # many executions have no specific entity
]

ERROR_MESSAGES = [
    "Request timed out after 60s",
    "Model returned malformed JSON: Expecting property name at line 3",
    "response_schema validation failed: required field 'deceased_name' missing",
    "Anthropic API rate limit exceeded (RateLimitError)",
    "Upstream provider overloaded",
]


def _business_hour_timestamp(days_ago: int) -> datetime:
    """Most executions cluster during business hours (9am–6pm local)."""
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    # Prefer business hours with a long tail of off-hours
    if random.random() < 0.7:
        hour = random.randint(13, 23)  # 9am–7pm Eastern in UTC
    else:
        hour = random.randint(0, 23)
    return base.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )


def _compute_cost(
    route: IntelligenceModelRoute | None,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    if route is None:
        # Fallback pricing — Haiku-ish
        in_cost = Decimal("1.00")
        out_cost = Decimal("5.00")
    else:
        in_cost = route.input_cost_per_million
        out_cost = route.output_cost_per_million
    cost = (
        Decimal(input_tokens) * in_cost / Decimal(1_000_000)
        + Decimal(output_tokens) * out_cost / Decimal(1_000_000)
    )
    return cost.quantize(Decimal("0.000001"))


def _fake_rendered_prompt(key: str, variables: dict) -> tuple[str, str]:
    system = (
        f"You are the {key.split('.')[0]} assistant for Bridgeable.\n"
        "Respond ONLY with valid JSON."
    )
    user = "Input context: " + ", ".join(
        f"{k}={v}" for k, v in variables.items()
    )
    return system, user


def _fake_vision_rendered_prompt(
    key: str, variables: dict
) -> tuple[str, str]:
    """Mimic `_redact_user_for_storage` output for a vision execution.

    Returns a JSON-serialized list of redacted content blocks so the admin
    UI's VisionContentBlock component can parse it. Two block types are
    generated: one image/document block + one text block. Fake sha256
    hashes and plausible byte lengths so the UI has something real-looking
    to display.
    """
    import json

    system = (
        f"You are the {key.split('.')[0]} vision extractor for Bridgeable.\n"
        "Given the attached document, extract the requested fields as JSON."
    )
    # Pick block type from the prompt_key convention
    is_pdf = "pdf" in key or "price_list" in key
    block_type = "document" if is_pdf else "image"
    media_type = "application/pdf" if is_pdf else "image/jpeg"
    bytes_len = random.randint(45_000, 2_500_000)
    # Plausible sha256 — hex chars, 64 long
    sha = "".join(random.choices("0123456789abcdef", k=64))
    blocks = [
        {
            "type": block_type,
            "media_type": media_type,
            "bytes_len": bytes_len,
            "data_sha256": sha,
        },
        {
            "type": "text",
            "text": (
                "Extract fields for "
                + ", ".join(f"{k}={v}" for k, v in variables.items())
            ),
        },
    ]
    return system, json.dumps(blocks, ensure_ascii=False)


def _fake_response(status: str, variables: dict) -> tuple[str, dict | None]:
    if status != "success":
        return ("", None)
    parsed = {"ok": True, "extracted": variables, "confidence": round(random.uniform(0.6, 0.99), 2)}
    import json

    return json.dumps(parsed), parsed


def seed_executions(db: Session, company: Company) -> int:
    prompts = _pick_prompts(db, n=12)
    if not prompts:
        print("No platform prompts found. Run seed_intelligence.py first.")
        return 0

    # Wipe prior dev-seed rows
    deleted = (
        db.query(IntelligenceExecution)
        .filter(IntelligenceExecution.caller_entity_type == DEV_SEED_SENTINEL)
        .delete(synchronize_session=False)
    )
    if deleted:
        print(f"Cleared {deleted} prior dev-seed execution rows")

    # Also wipe our dev experiments (same sentinel on name)
    deleted_exp = (
        db.query(IntelligenceExperiment)
        .filter(IntelligenceExperiment.name.like("dev seed %"))
        .delete(synchronize_session=False)
    )
    if deleted_exp:
        print(f"Cleared {deleted_exp} prior dev-seed experiment rows")

    db.flush()

    created = 0
    random.seed(42)  # deterministic runs

    for _ in range(TARGET_EXECUTIONS):
        prompt = random.choice(prompts)
        version = _pick_active_version(db, prompt.id)
        model_pref = version.model_preference if version else "simple"
        route = _pick_route(db, model_pref) if model_pref else None

        # Success/error mix — ~93% success
        status = "success" if random.random() < 0.93 else "error"
        # Company — ~70% tenant, 30% platform (no tenant)
        company_id = company.id if random.random() < 0.7 else None

        # Token distributions — larger for extraction prompts
        if model_pref == "extraction":
            input_tokens = random.randint(800, 4000)
            output_tokens = random.randint(200, 1500)
        else:
            input_tokens = random.randint(200, 1200)
            output_tokens = random.randint(50, 600)

        latency_ms = (
            random.randint(80, 600)
            if model_pref == "simple"
            else random.randint(400, 3000)
        )
        if status == "error":
            # Errors often fail faster (timeout/validation) or slower (timeout)
            latency_ms = random.choice([random.randint(50, 300), random.randint(30000, 60000)])

        cost = _compute_cost(route, input_tokens, output_tokens)

        days_ago = random.randint(0, 29)
        created_at = _business_hour_timestamp(days_ago)

        entity_type, linkage_field = random.choice(ENTITY_TYPE_SAMPLES)
        variables = {
            "context": random.choice(["order", "case", "invoice", "transcript"]),
            "size": random.randint(100, 2000),
        }

        # Generate vision-style rendered_user_prompt when the prompt is
        # vision-capable. Always on for those prompts so the UI has real
        # fixture data to exercise VisionContentBlock.
        is_vision = _is_vision_prompt(prompt.prompt_key)
        if is_vision:
            rendered_system, rendered_user = _fake_vision_rendered_prompt(
                prompt.prompt_key, variables
            )
        else:
            rendered_system, rendered_user = _fake_rendered_prompt(
                prompt.prompt_key, variables
            )
        response_text, response_parsed = _fake_response(status, variables)
        error_message = random.choice(ERROR_MESSAGES) if status == "error" else None

        input_hash = hashlib.sha256(
            (rendered_system + rendered_user).encode("utf-8")
        ).hexdigest()

        caller_module = random.choice(CALLER_MODULES)

        # Either tag with the sentinel entity type (for identifiable dev rows)
        # or use a realistic entity_type (~50/50 for UI variety)
        if random.random() < 0.5:
            exec_entity_type = DEV_SEED_SENTINEL
            exec_entity_id = str(uuid.uuid4())
            linkage_kwargs: dict = {}
        else:
            exec_entity_type = entity_type
            exec_entity_id = str(uuid.uuid4()) if entity_type else None
            linkage_kwargs = {}
            if linkage_field and exec_entity_id:
                linkage_kwargs[linkage_field] = exec_entity_id
            # Always flag it as a dev row via the sentinel on caller_entity_type
            # — we do this on the _remainder_ only if entity_type is None, so
            # we can identify them for cleanup. If entity_type is set we rely
            # on input_hash / caller_module to cluster; next run ALSO wipes
            # rows with DEV_SEED_SENTINEL entity_type.
            if exec_entity_type is None:
                exec_entity_type = DEV_SEED_SENTINEL

        e = IntelligenceExecution(
            id=str(uuid.uuid4()),
            company_id=company_id,
            prompt_id=prompt.id,
            prompt_version_id=version.id if version else None,
            model_preference=model_pref,
            model_used=(route.primary_model if route else "claude-haiku-4-5-20251001"),
            input_hash=input_hash,
            input_variables=variables,
            rendered_system_prompt=rendered_system,
            rendered_user_prompt=rendered_user,
            response_text=response_text,
            response_parsed=response_parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            status=status,
            error_message=error_message,
            caller_module=caller_module,
            caller_entity_type=exec_entity_type,
            caller_entity_id=exec_entity_id,
            created_at=created_at,
            **linkage_kwargs,
        )
        db.add(e)
        created += 1

    db.commit()
    print(f"Created {created} dev executions across {len(prompts)} prompts")
    return created


def seed_experiments(db: Session, company: Company) -> int:
    """Create ~2 fake experiments for Phase 3c UI testing."""
    prompts_with_multiple_versions = []
    for p in db.query(IntelligencePrompt).filter(IntelligencePrompt.company_id.is_(None)).all():
        versions = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.prompt_id == p.id)
            .order_by(IntelligencePromptVersion.version_number)
            .all()
        )
        if len(versions) >= 2:
            prompts_with_multiple_versions.append((p, versions))

    # If no prompt has >=2 versions, create a v2 draft on the first two picked prompts
    created = 0
    picks = prompts_with_multiple_versions
    if len(picks) < TARGET_EXPERIMENTS:
        # Fall back: use two separate prompts; run an "experiment" between
        # the same prompt's only version vs itself. Skip in that case.
        print(
            f"Skipping experiment seed — only {len(picks)} prompts have >=2 versions. "
            f"(Create additional versions to light up experiment UI.)"
        )
        return 0

    # Active experiment
    p1, v1s = picks[0]
    exp1 = IntelligenceExperiment(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_id=p1.id,
        name=f"dev seed active — {p1.prompt_key}",
        hypothesis="v2 should reduce hallucination rate by 20%",
        version_a_id=v1s[0].id,
        version_b_id=v1s[1].id,
        traffic_split=50,
        min_sample_size=100,
        status="active",
        started_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    db.add(exp1)
    created += 1

    # Concluded experiment
    p2, v2s = picks[1] if len(picks) > 1 else picks[0]
    exp2 = IntelligenceExperiment(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_id=p2.id,
        name=f"dev seed concluded — {p2.prompt_key}",
        hypothesis="v2 should cut output tokens by 30%",
        version_a_id=v2s[0].id,
        version_b_id=v2s[1].id,
        traffic_split=50,
        min_sample_size=100,
        status="concluded",
        winner_version_id=v2s[1].id,
        conclusion_notes="v2 cut output tokens by 28% with no quality regression.",
        started_at=datetime.now(timezone.utc) - timedelta(days=20),
        concluded_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    db.add(exp2)
    created += 1

    db.commit()
    print(f"Created {created} dev experiments")
    return created


def main() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.is_active == True).first()
        if company is None:
            print("No active company found. Create one first.")
            return

        print(f"Seeding dev intelligence executions into tenant: {company.name} ({company.id})")
        n = seed_executions(db, company)
        e = seed_experiments(db, company)
        print(f"Done. {n} executions + {e} experiments.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""Phase 2b — verbatim content for the next batch of migrated prompts.

Phase 2b scope (context-limited):
  urn.semantic_search       ← urn_product_service.py::search_products
  accounting.coa_classify   ← accounting_analysis_service.py::run_ai_analysis

Remaining long-tail (~25 callers that still use ai_service.call_anthropic) is
already covered by the legacy audit shim — intelligence_executions rows are
written with prompt_id=null and caller_module="legacy" so regulatory coverage
is 100% today. Full migration of those callers queues up as Phase 2c.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


URN_SEARCH_SYSTEM = """You expand natural-language burial urn search queries into a JSON array of search terms.

Given a user's search query, return a JSON array of strings covering:
- the original query terms
- common synonyms (e.g. "bronze" → "brass", "metal")
- related material/style descriptors

Match against product name, style, material, colors.

Return ONLY a JSON array of strings. No preamble, no markdown, no code fences."""

URN_SEARCH_USER = "Query: {{ query }}"


COA_CLASSIFY_SYSTEM = """You are a chart of accounts classification assistant for a precast concrete / burial vault manufacturer.

Given a GL account name and a small sample of transaction memos posted against it, classify the account into one of these platform categories and return a JSON object with:
- category: one of the provided platform categories
- confidence: 0.0-1.0
- reasoning: one short sentence

Return ONLY valid JSON. No markdown, no code fences, no extra prose."""

COA_CLASSIFY_USER = """Account name: {{ account_name }}
Sample transactions:
{{ sample_transactions }}

Platform categories:
{{ platform_categories }}

Classify this account."""


UPDATES: list[dict] = [
    {
        "prompt_key": "urn.semantic_search",
        "system_prompt": URN_SEARCH_SYSTEM,
        "user_template": URN_SEARCH_USER,
        "variable_schema": {
            "query": {
                "type": "string",
                "required": True,
                "description": "User's natural-language urn search query.",
            },
        },
        "response_schema": None,  # returns a JSON array (not object), caller handles
        "model_preference": "simple",
        "temperature": 0.3,
        "max_tokens": 200,
        "force_json": True,
        "changelog": "Phase 2b migration — verbatim from urn_product_service.search_products.",
    },
    {
        "prompt_key": "accounting.coa_classify",
        "system_prompt": COA_CLASSIFY_SYSTEM,
        "user_template": COA_CLASSIFY_USER,
        "variable_schema": {
            "account_name": {"type": "string", "required": True},
            "sample_transactions": {
                "type": "string",
                "required": True,
                "description": "Pre-formatted bullet list of sample transaction memos.",
            },
            "platform_categories": {
                "type": "string",
                "required": True,
                "description": "Pre-formatted list of valid category enum values.",
            },
        },
        "response_schema": {"required": ["category", "confidence"]},
        "model_preference": "simple",
        "temperature": 0.1,
        "max_tokens": 512,
        "force_json": True,
        "changelog": "Phase 2b migration — verbatim from accounting_analysis_service.",
    },
]


def apply_updates(db: Session) -> int:
    touched = 0
    for spec in UPDATES:
        prompt = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == spec["prompt_key"],
            )
            .first()
        )
        if prompt is None:
            # Phase 1 seeded all keys in the spec; defensive create if missing
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=spec["prompt_key"],
                display_name=spec["prompt_key"],
                domain=spec["prompt_key"].split(".", 1)[0],
            )
            db.add(prompt)
            db.flush()

        v1 = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.version_number == 1,
            )
            .first()
        )
        if v1 is None:
            v1 = IntelligencePromptVersion(
                prompt_id=prompt.id,
                version_number=1,
                status="active",
                activated_at=datetime.now(timezone.utc),
                system_prompt="",
                user_template="",
                model_preference=spec["model_preference"],
            )
            db.add(v1)
            db.flush()

        v1.system_prompt = spec["system_prompt"]
        v1.user_template = spec["user_template"]
        v1.variable_schema = spec["variable_schema"]
        v1.response_schema = spec.get("response_schema")
        v1.model_preference = spec["model_preference"]
        v1.temperature = spec.get("temperature", 0.3)
        v1.max_tokens = spec.get("max_tokens", 1024)
        v1.force_json = spec.get("force_json", False)
        v1.changelog = spec["changelog"]
        if v1.status != "active":
            v1.status = "active"
            v1.activated_at = datetime.now(timezone.utc)
        touched += 1
    db.commit()
    return touched


def main() -> None:
    db = SessionLocal()
    try:
        n = apply_updates(db)
        phase2_total = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.changelog.ilike("Phase 2%"))
            .count()
        )
        print(f"Phase 2b touched: {n}")
        print(f"Phase-2-migrated versions (cumulative): {phase2_total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""Customer classification service.

Two-stage classification pipeline:
  1. Name-based rule engine (fast, no API cost)
  2. AI batch classification via Claude (for unresolved customers)

Usage:
    results = CustomerClassificationService.classify_customers(parsed_customers)
    # returns: {classifications, summary, needs_review}
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypedDict


from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class ClassificationResult(TypedDict):
    customer_type: str          # 'funeral_home' | 'contractor' | 'cemetery' | 'individual' | 'unknown'
    confidence: float           # 0.0 – 1.0
    matched_pattern: str | None # the pattern that triggered the rule, or None
    method: str                 # 'name_rules' | 'ai' | 'unknown'
    reasoning: str | None       # short explanation


# ---------------------------------------------------------------------------
# Pattern sets
# ---------------------------------------------------------------------------

# ── Funeral home patterns ─────────────────────────────────────────────────────
_FUNERAL_STRONG: list[str] = [
    r"\bfuneral\b",
    r"\bmortuary\b",
    r"\bcremation\b",
    r"\bcrematorium\b",
    r"\bcrematory\b",
    r"\bfunerary\b",
    r"\bchapel of rest\b",
    r"\bmemorial chapel\b",
    r"\bmemorial home\b",
    r"\bmemorial service\b",
    r"\bburial service\b",
    r"\bburial chapel\b",
    r"\bfh\b",           # common abbreviation in Sage exports
]

_FUNERAL_WEAK: list[str] = [
    r"\bchapel\b",
    r"\binterment\b",
    r"\bbereavement\b",
    r"\blife celebration\b",
    r"\bcelebration of life\b",
    r"\brest in peace\b",
    r"\bfarewell\b",
    r"\bmemorial\b",    # weak — could be park
]

# ── Cemetery patterns ─────────────────────────────────────────────────────────
_CEMETERY_STRONG: list[str] = [
    r"\bcemetery\b",
    r"\bcemeteries\b",
    r"\bcemetary\b",        # common misspelling
    r"\bmausoleum\b",
    r"\bcolumbarium\b",
    r"\bburial ground\b",
    r"\bburial park\b",
    r"\bmemorial park\b",
    r"\bgarden of memories\b",
    r"\bgarden of peace\b",
    r"\brest haven\b",
    r"\bcalvary\b",
    r"\bgate of heaven\b",
    r"\bresurrection\b",
    r"\bassumption\b",
    r"\bholy cross\b",
    r"\bholy name\b",
    r"\bholy trinity\b",
    r"\bholy sepulchre\b",
    r"\bst\.\s*mary\b",
    r"\bst\s+mary\b",
    r"\bst\.\s*joseph\b",
    r"\bst\s+joseph\b",
    r"\bst\.\s*peter\b",
    r"\bst\s+peter\b",
    r"\bsacred heart\b",
]

_CEMETERY_WEAK: list[str] = [
    r"\bmemorial gardens\b",
    r"\borderof\b",
    r"\boak (hill|grove|lawn|park)\b",
    r"\bpine (grove|hill|lawn)\b",
    r"\belm (grove|lawn)\b",
    r"\bevergreen\b",
    r"\blawn\b",        # very weak
]

# ── Contractor patterns ───────────────────────────────────────────────────────
_CONTRACTOR_STRONG: list[str] = [
    r"\bexcavat",
    r"\bconstruct",
    r"\bcontract",
    r"\bcontracting\b",
    r"\bcontractor\b",
    r"\blandscap",
    r"\bseptic\b",
    r"\bsewer\b",
    r"\bdrainag",
    r"\bwell (drilling|drill)\b",
    r"\bplumb",
    r"\bmasonry\b",
    r"\bconcrete\b",
    r"\bgrading\b",
    r"\bsite (work|dev|development)\b",
    r"\bcivil (eng|construct)\b",
    r"\belectr(ic|ical)\b",
    r"\butilities\b",
    r"\bbuilder\b",
    r"\bgreenhouse\b",
    r"\btractor\b",
    r"\bequipment\b",
    r"\bproperty (maintenance|mgmt|management)\b",
    r"\bsnow (removal|plow)",
    r"\bpond\b",
    r"\birrigation\b",
    r"\bpiping\b",
    r"\bmechanical\b",
    r"\binstallation\b",
    r"\bwaterproof",
    r"\bbasement\b",
    r"\benvironmental\b",
    r"\bearthwork\b",
    r"\bpaving\b",
    r"\basphalt\b",
    r"\broofing\b",
    r"\bhvac\b",
    r"\bplumbing\b",
    r"\belectric\b",
    r"\bdemo(lition)?\b",
    r"\bwaste(water|water)\b",
    r"\bseptic (system|service|tank)\b",
    r"\bdrain field\b",
    r"\bleach field\b",
    r"\bprecast\b",
    r"\bsupply (co|company|inc)\b",
    r"\bmaterials\b",
    r"\brunning\b",
    r"\bplowing\b",
    r"\bmowing\b",
    r"\bdirtwork\b",
]

_CONTRACTOR_WEAK: list[str] = [
    r"\bservices\b",
    r"\bindustri",
    r"\bcommercial\b",
    r"\binc\b",
    r"\bllc\b",
    r"\bco\b",
    r"\bcorp\b",
]

# ── Individual patterns ───────────────────────────────────────────────────────
_INDIVIDUAL_PATTERNS: list[str] = [
    r"^(mr\.?|mrs\.?|ms\.?|dr\.?|rev\.?)\s+\w+",   # title + name
    r"^\w+,\s+\w+$",                                  # "Last, First"
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_RE_FUNERAL_STRONG = _compile(_FUNERAL_STRONG)
_RE_FUNERAL_WEAK = _compile(_FUNERAL_WEAK)
_RE_CEMETERY_STRONG = _compile(_CEMETERY_STRONG)
_RE_CEMETERY_WEAK = _compile(_CEMETERY_WEAK)
_RE_CONTRACTOR_STRONG = _compile(_CONTRACTOR_STRONG)
_RE_CONTRACTOR_WEAK = _compile(_CONTRACTOR_WEAK)
_RE_INDIVIDUAL = _compile(_INDIVIDUAL_PATTERNS)


def _first_match(name: str, patterns: list[re.Pattern]) -> str | None:
    for p in patterns:
        m = p.search(name)
        if m:
            return m.group(0)
    return None


# ---------------------------------------------------------------------------
# Part 1: Name-based rule engine
# ---------------------------------------------------------------------------


def classify_by_name(name: str) -> ClassificationResult:
    """Run the customer name through all pattern sets.

    Returns:
        {customer_type, confidence, matched_pattern, method, reasoning}
    """
    if not name or not name.strip():
        return ClassificationResult(
            customer_type="unknown",
            confidence=0.0,
            matched_pattern=None,
            method="name_rules",
            reasoning="Empty name",
        )

    # ── Funeral home — strong ────────────────────────────────────────────────
    pat = _first_match(name, _RE_FUNERAL_STRONG)
    if pat:
        return ClassificationResult(
            customer_type="funeral_home",
            confidence=0.95,
            matched_pattern=pat,
            method="name_rules",
            reasoning=f"Name contains strong funeral home indicator '{pat}'",
        )

    # ── Cemetery — strong ────────────────────────────────────────────────────
    pat = _first_match(name, _RE_CEMETERY_STRONG)
    if pat:
        return ClassificationResult(
            customer_type="cemetery",
            confidence=0.95,
            matched_pattern=pat,
            method="name_rules",
            reasoning=f"Name contains strong cemetery indicator '{pat}'",
        )

    # ── Contractor — strong ──────────────────────────────────────────────────
    pat = _first_match(name, _RE_CONTRACTOR_STRONG)
    if pat:
        return ClassificationResult(
            customer_type="contractor",
            confidence=0.90,
            matched_pattern=pat,
            method="name_rules",
            reasoning=f"Name contains contractor indicator '{pat}'",
        )

    # ── Funeral home — weak ──────────────────────────────────────────────────
    pat = _first_match(name, _RE_FUNERAL_WEAK)
    if pat:
        return ClassificationResult(
            customer_type="funeral_home",
            confidence=0.75,
            matched_pattern=pat,
            method="name_rules",
            reasoning=f"Name contains weak funeral home indicator '{pat}'",
        )

    # ── Cemetery — weak ──────────────────────────────────────────────────────
    pat = _first_match(name, _RE_CEMETERY_WEAK)
    if pat:
        return ClassificationResult(
            customer_type="cemetery",
            confidence=0.72,
            matched_pattern=pat,
            method="name_rules",
            reasoning=f"Name contains weak cemetery indicator '{pat}'",
        )

    # ── Individual ───────────────────────────────────────────────────────────
    pat = _first_match(name, _RE_INDIVIDUAL)
    if pat:
        return ClassificationResult(
            customer_type="individual",
            confidence=0.80,
            matched_pattern=pat,
            method="name_rules",
            reasoning="Name matches personal name pattern",
        )

    # ── No match ─────────────────────────────────────────────────────────────
    return ClassificationResult(
        customer_type="unknown",
        confidence=0.0,
        matched_pattern=None,
        method="name_rules",
        reasoning="No pattern matched",
    )


# ---------------------------------------------------------------------------
# Part 2: AI batch classification
# ---------------------------------------------------------------------------

# System prompt + user template now live in the managed
# `onboarding.classify_customer_batch` prompt (Phase 2c-2 migration). The
# former _AI_SYSTEM_PROMPT constant is deleted — see seed_intelligence_phase2c.py
# for the verbatim content and variable schema.


def _classify_batch_with_ai(
    unclassified: list[dict],  # [{index, name, city, state}]
    *,
    db=None,
    company_id: str | None = None,
    tenant_name: str = "the Wilbert licensee",
) -> list[ClassificationResult]:
    """Send a batch of up to 50 customers to the Intelligence layer for classification.

    Phase 2c-2 migration — routes through `onboarding.classify_customer_batch`.
    tenant_name is passed into the managed prompt (Phase 2c-2 parameterized
    what used to be a hardcoded 'Sunnycrest Precast' reference).
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — skipping AI classification")
        return [
            ClassificationResult(
                customer_type="unknown",
                confidence=0.0,
                matched_pattern=None,
                method="ai",
                reasoning="AI service not configured",
            )
            for _ in unclassified
        ]

    if db is None:
        # Short-lived session for callers that don't thread one through.
        from app.database import SessionLocal

        local_db = SessionLocal()
        try:
            return _classify_batch_with_ai(
                unclassified, db=local_db, company_id=company_id, tenant_name=tenant_name
            )
        finally:
            local_db.close()

    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="onboarding.classify_customer_batch",
            variables={
                "tenant_name": tenant_name,
                "unclassified": json.dumps(unclassified),
            },
            company_id=company_id,
            caller_module="customer_classification_service._classify_batch_with_ai",
            caller_entity_type=None,  # pre-persistence staging
            caller_entity_id=None,
        )

        if result.status != "success":
            raise RuntimeError(f"Intelligence status={result.status}: {result.error_message}")

        # Response is a JSON array — parsed or raw text
        if isinstance(result.response_parsed, list):
            ai_results: list[dict] = result.response_parsed
        else:
            raw = (result.response_text or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            ai_results = json.loads(raw)

        by_index: dict[int, dict] = {r["index"]: r for r in ai_results}
        results: list[ClassificationResult] = []
        for item in unclassified:
            ai = by_index.get(item["index"])
            if ai:
                results.append(
                    ClassificationResult(
                        customer_type=ai.get("customer_type", "unknown"),
                        confidence=float(ai.get("confidence", 0.0)),
                        matched_pattern=None,
                        method="ai",
                        reasoning=ai.get("reasoning"),
                    )
                )
            else:
                results.append(
                    ClassificationResult(
                        customer_type="unknown",
                        confidence=0.0,
                        matched_pattern=None,
                        method="ai",
                        reasoning="AI did not return a result for this customer",
                    )
                )
        return results

    except (json.JSONDecodeError, KeyError, RuntimeError) as e:
        logger.error(f"AI classification batch failed: {e}")
        return [
            ClassificationResult(
                customer_type="unknown",
                confidence=0.0,
                matched_pattern=None,
                method="ai",
                reasoning=f"AI classification failed: {type(e).__name__}",
            )
            for _ in unclassified
        ]


# ---------------------------------------------------------------------------
# Part 2 (cont.): Full orchestration
# ---------------------------------------------------------------------------

# Thresholds
_RULE_CONFIDENCE_THRESHOLD = 0.85   # use rule result without AI
_AI_CONFIDENCE_THRESHOLD = 0.75     # AI result accepted above this
_NEEDS_REVIEW_THRESHOLD = 0.75      # anything below this goes to needs_review


def classify_customers(
    parsed_customers: list[dict],
    *,
    db=None,
    company_id: str | None = None,
    tenant_name: str = "the Wilbert licensee",
) -> dict:
    """Classify all parsed customers using rules + AI.

    Args:
        parsed_customers: List of dicts from DataMigrationService.parse_customers().
            Each must have at least a 'name' key; 'city' and 'state' are optional.

    Returns:
        {
          "classifications": [ClassificationResult, ...],  # same index as input
          "summary": {
              "total": int,
              "by_type": {"funeral_home": int, "contractor": int, ...},
              "needs_review_count": int,
              "rule_classified": int,
              "ai_classified": int,
          },
          "needs_review": [
              {"index": int, "name": str, "current_type": str, "confidence": float, "reasoning": str}
          ]
        }
    """
    classifications: list[ClassificationResult] = [None] * len(parsed_customers)  # type: ignore[list-item]
    needs_ai: list[dict] = []  # {index, name, city, state}

    # ── Stage 1: Name rules ───────────────────────────────────────────────────
    for i, customer in enumerate(parsed_customers):
        name = customer.get("name") or customer.get("customer_name") or ""
        result = classify_by_name(name)
        if result["confidence"] >= _RULE_CONFIDENCE_THRESHOLD:
            classifications[i] = result
        else:
            # Queue for AI — rules weren't confident enough
            needs_ai.append({
                "index": i,
                "name": name,
                "city": customer.get("city"),
                "state": customer.get("state"),
            })

    # ── Stage 2: AI batches of 50 ────────────────────────────────────────────
    rule_classified = len(parsed_customers) - len(needs_ai)
    ai_classified = 0

    BATCH_SIZE = 50
    for batch_start in range(0, len(needs_ai), BATCH_SIZE):
        batch = needs_ai[batch_start : batch_start + BATCH_SIZE]
        ai_results = _classify_batch_with_ai(
            batch, db=db, company_id=company_id, tenant_name=tenant_name
        )

        for item, ai_result in zip(batch, ai_results):
            idx = item["index"]
            rule_result = classify_by_name(item["name"])  # recompute for merge

            # Choose between rule and AI
            if ai_result["confidence"] >= _AI_CONFIDENCE_THRESHOLD:
                if rule_result["confidence"] > 0 and rule_result["customer_type"] != ai_result["customer_type"]:
                    # Conflict: take whichever is more confident
                    if rule_result["confidence"] >= ai_result["confidence"]:
                        classifications[idx] = rule_result
                    else:
                        classifications[idx] = ai_result
                else:
                    classifications[idx] = ai_result
                ai_classified += 1
            elif rule_result["confidence"] > 0:
                # AI wasn't confident but rules gave something
                classifications[idx] = rule_result
                if rule_result["confidence"] >= _RULE_CONFIDENCE_THRESHOLD:
                    ai_classified += 0
                    rule_classified += 1
                else:
                    classifications[idx] = rule_result
            else:
                # Neither confident — mark unknown, needs review
                classifications[idx] = ClassificationResult(
                    customer_type="unknown",
                    confidence=0.0,
                    matched_pattern=None,
                    method="ai",
                    reasoning="Could not classify — needs manual review",
                )

    # ── Summary ───────────────────────────────────────────────────────────────
    by_type: dict[str, int] = {}
    needs_review: list[dict] = []

    for i, (customer, result) in enumerate(zip(parsed_customers, classifications)):
        if result is None:
            result = ClassificationResult(
                customer_type="unknown", confidence=0.0,
                matched_pattern=None, method="name_rules",
                reasoning="Classification error",
            )
            classifications[i] = result

        ct = result["customer_type"]
        by_type[ct] = by_type.get(ct, 0) + 1

        if result["confidence"] < _NEEDS_REVIEW_THRESHOLD:
            needs_review.append({
                "index": i,
                "name": customer.get("name") or customer.get("customer_name") or "",
                "city": customer.get("city"),
                "state": customer.get("state"),
                "current_type": ct,
                "confidence": result["confidence"],
                "reasoning": result.get("reasoning"),
                "matched_pattern": result.get("matched_pattern"),
            })

    summary = {
        "total": len(parsed_customers),
        "by_type": by_type,
        "needs_review_count": len(needs_review),
        "rule_classified": rule_classified,
        "ai_classified": ai_classified,
    }

    return {
        "classifications": classifications,
        "summary": summary,
        "needs_review": needs_review,
    }


# ---------------------------------------------------------------------------
# Convenience: classify a single customer name (for the /classify endpoint)
# ---------------------------------------------------------------------------

def classify_single(
    name: str,
    city: str | None = None,
    state: str | None = None,
    *,
    db=None,
    company_id: str | None = None,
    tenant_name: str = "the Wilbert licensee",
) -> ClassificationResult:
    """Classify one customer — rules first, AI fallback if confidence too low."""
    result = classify_by_name(name)
    if result["confidence"] >= _RULE_CONFIDENCE_THRESHOLD:
        return result

    # Try AI for single customer
    ai_results = _classify_batch_with_ai(
        [{"index": 0, "name": name, "city": city, "state": state}],
        db=db,
        company_id=company_id,
        tenant_name=tenant_name,
    )
    ai = ai_results[0]

    if ai["confidence"] >= _AI_CONFIDENCE_THRESHOLD:
        # Conflict resolution
        if result["confidence"] > 0 and result["customer_type"] != ai["customer_type"]:
            return ai if ai["confidence"] > result["confidence"] else result
        return ai

    # Fallback to whatever rules gave (even low confidence)
    if result["confidence"] > 0:
        return result
    return ai

"""Anomaly Intelligence Stream V1 — rule-based synthesis.

Per BRIDGEABLE_MASTER §3.26.2.5 Tier 3. Phase W-4a ships ONE Tier 3
demo-quality stream: anomaly intelligence. V1 is rule-based template
synthesis (0ms latency, 0 AI cost). V2 (Haiku-cached) deferred per
D6 to a separate post-W-4a polish session.

Inputs: the anomaly layer service's intelligence-stream payload
(total_unresolved + severity counts + top_anomalies + work_areas).

Output: a synthesized `IntelligenceStream` with:
  • title: "Today's watch list" (canonical for V1)
  • synthesized_text: rule-driven prose mentioning highest-severity
    items, count breakdown, and work-area relevance
  • referenced_items: list of `ReferencedItem`s for the top
    anomalies — frontend renders as click-through chips beneath
    the synthesis copy
  • priority: 95 (above raw anomalies widget; matches anomaly_layer
    intelligence stream item priority)

Work-area relevance filter: when the user has work_areas set, the
synthesis prioritizes anomalies whose `agent_job_type` (or anomaly_
type) maps to one of the user's work_areas. The current mapping is
heuristic — not all anomaly types have clean work-area mapping; we
use generous defaults so anomalies surface even when the mapping
is ambiguous.

**V1 quality bar:** the synthesis must read coherently and surface
the most-urgent items by name. It must NOT invent facts or use
placeholder language. The template explicitly extracts entity names
from `top_anomalies[].description` when possible, falling back to
the `anomaly_type` field when descriptions are too generic.

**Empty-state contract:** when the input has zero anomalies, this
module returns `None` — the composition engine omits the stream
entirely. The anomaly_layer_service's "All clear" advisory carries
the empty-state UX.
"""
from __future__ import annotations

from typing import Any

from app.services.pulse.types import IntelligenceStream, ReferencedItem


# Heuristic mapping from accounting agent_job_type → work areas
# they relate to. When the user's work_areas overlap, the anomaly
# is "relevant" for prioritization. Conservative — most anomaly
# types map to Accounting since they originate from accounting
# agents. Future agents (delivery SLA, inventory) will extend this
# mapping when their anomaly types ship.
_ANOMALY_TYPE_TO_WORK_AREAS: dict[str, set[str]] = {
    # Accounting-driven anomalies (Phase 1+ accounting agents).
    "balance_mismatch": {"Accounting"},
    "uninvoiced_delivery": {"Accounting", "Delivery Scheduling"},
    "invoice_amount_mismatch": {"Accounting"},
    "unmatched_payment": {"Accounting"},
    "duplicate_payment": {"Accounting"},
    "overdue_ar_90plus": {"Accounting"},
    "revenue_outlier": {"Accounting"},
    "low_collection_rate": {"Accounting"},
    "inactive_customer": {"Accounting", "Customer Service"},
    "low_invoice_volume": {"Accounting"},
    "statement_run_conflict": {"Accounting"},
    "anomaly_resolved": {"Accounting"},
    # Future operational anomalies (placeholder mapping; activates
    # when these anomaly types ship).
    "delivery_sla_risk": {"Delivery Scheduling"},
    "schedule_conflict": {"Delivery Scheduling", "Production Scheduling"},
    "inventory_low_stock": {"Inventory Management"},
    "inventory_oversold": {"Inventory Management"},
    "production_unscheduled": {"Production Scheduling"},
}


def _is_relevant_to_work_areas(
    anomaly_type: str, work_areas: list[str]
) -> bool:
    """Return True when the anomaly's known work_areas overlap with
    the user's selected work_areas. When the user has no work_areas
    (vertical-default fallback case), every anomaly is relevant."""
    if not work_areas:
        return True
    mapped = _ANOMALY_TYPE_TO_WORK_AREAS.get(anomaly_type, set())
    if not mapped:
        # Unknown type — treat as relevant by default (defensive
        # over-surfacing > silent under-surfacing).
        return True
    return bool(mapped & set(work_areas))


def _format_severity_count_phrase(
    critical: int, warning: int, info: int
) -> str:
    """Phrase the severity distribution in natural language."""
    parts: list[str] = []
    if critical > 0:
        parts.append(
            f"{critical} critical" if critical > 1 else "1 critical"
        )
    if warning > 0:
        parts.append(
            f"{warning} warning" if warning > 1 else "1 warning"
        )
    if info > 0:
        parts.append(f"{info} info")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return " and ".join(parts)
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _humanize_anomaly_type(anomaly_type: str) -> str:
    """Convert snake_case anomaly_type to readable phrase."""
    return anomaly_type.replace("_", " ")


def _entity_label_from_anomaly(anomaly: dict[str, Any]) -> str:
    """Best-effort entity label from an anomaly row.

    Description strings vary by agent — we want the most informative
    short label for the chip. Falls back to humanized anomaly_type
    when the description is generic or missing.
    """
    desc = (anomaly.get("description") or "").strip()
    atype = anomaly.get("anomaly_type") or "anomaly"
    if not desc:
        return _humanize_anomaly_type(atype)
    # Cap to a short phrase — chip should fit in tetris layout.
    if len(desc) > 60:
        desc = desc[:57].rstrip() + "…"
    return desc


def synthesize(
    *,
    payload: dict[str, Any],
) -> IntelligenceStream | None:
    """Synthesize the V1 anomaly intelligence stream from the
    `anomaly_layer_service`'s LayerItem payload.

    Expected payload shape (matches
    `anomaly_layer_service._build_anomaly_intelligence_stream_item`):

        {
          "total_unresolved": int,
          "critical_count": int,
          "warning_count": int,
          "info_count": int,
          "top_anomalies": list[dict],   # serialized anomaly rows
          "work_areas": list[str],       # user's work_areas
        }

    Returns None when `total_unresolved == 0` — composition engine
    omits the stream entirely (anomaly layer carries "All clear"
    advisory).
    """
    total = int(payload.get("total_unresolved", 0))
    if total == 0:
        return None

    critical = int(payload.get("critical_count", 0))
    warning = int(payload.get("warning_count", 0))
    info = int(payload.get("info_count", 0))
    top_raw: list[dict[str, Any]] = list(payload.get("top_anomalies", []))
    work_areas = list(payload.get("work_areas", []))

    # Work-area relevance filter — prioritize anomalies whose type
    # maps to one of the user's work_areas. We don't drop irrelevant
    # ones entirely; we surface relevant ones first.
    if work_areas:
        relevant = [
            a
            for a in top_raw
            if _is_relevant_to_work_areas(
                a.get("anomaly_type", ""), work_areas
            )
        ]
        irrelevant = [a for a in top_raw if a not in relevant]
        ordered = relevant + irrelevant
    else:
        ordered = top_raw

    # ── Build synthesized text ───────────────────────────────────
    # Sentence 1: severity-distribution headline.
    severity_phrase = _format_severity_count_phrase(critical, warning, info)
    sentences: list[str] = []
    if total == 1 and critical == 1:
        sentences.append("One critical anomaly needs attention.")
    elif severity_phrase:
        sentences.append(
            f"You have {severity_phrase} "
            f"{'anomaly' if total == 1 else 'anomalies'} unresolved."
        )
    else:
        sentences.append(
            f"You have {total} unresolved "
            f"{'anomaly' if total == 1 else 'anomalies'}."
        )

    # Sentence 2: most urgent.
    if ordered:
        first = ordered[0]
        first_label = _entity_label_from_anomaly(first)
        first_sev = (first.get("severity") or "").lower()
        if first_sev == "critical":
            sentences.append(f"Most urgent: {first_label}.")
        else:
            sentences.append(f"Top item: {first_label}.")

    # Sentence 3: watch list (next 2 items, if any).
    if len(ordered) >= 2:
        watch_labels = [
            _entity_label_from_anomaly(a) for a in ordered[1:3]
        ]
        if len(watch_labels) == 1:
            sentences.append(f"Also watch: {watch_labels[0]}.")
        elif len(watch_labels) == 2:
            sentences.append(
                f"Also watch: {watch_labels[0]}; {watch_labels[1]}."
            )

    synthesized_text = " ".join(sentences)

    # ── Build referenced items (top 5 for chip rendering) ────────
    referenced_items: list[ReferencedItem] = []
    for a in ordered[:5]:
        anomaly_id = a.get("id")
        if not anomaly_id:
            continue
        referenced_items.append(
            ReferencedItem(
                kind="anomaly",
                entity_id=str(anomaly_id),
                label=_entity_label_from_anomaly(a),
                # Future: route to /agents/anomalies/{id}; for W-4a
                # the chip is informational + the click-through is
                # handled by the parent widget render.
                href=None,
            )
        )

    return IntelligenceStream(
        stream_id="anomaly_intelligence",
        layer="anomaly",
        title="Today's watch list",
        synthesized_text=synthesized_text,
        referenced_items=referenced_items,
        priority=95,
    )

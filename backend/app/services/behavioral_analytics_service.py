"""Behavioral analytics service — event recording, causal linking, insights."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.behavioral_analytics import (
    BehavioralEvent,
    BehavioralInsight,
    EntityBehavioralProfile,
    InsightFeedback,
)

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.700


# ---------------------------------------------------------------------------
# Event Recording — fire-and-forget, never throws
# ---------------------------------------------------------------------------


def record_event(
    db: Session,
    tenant_id: str,
    event_category: str,
    event_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    secondary_entity_type: str | None = None,
    secondary_entity_id: str | None = None,
    caused_by_event_id: str | None = None,
    event_data: dict | None = None,
    actor_type: str = "agent",
    actor_id: str | None = None,
) -> str | None:
    """Record a behavioral event. Never throws — errors are logged and swallowed."""
    try:
        event = BehavioralEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_category=event_category,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            secondary_entity_type=secondary_entity_type,
            secondary_entity_id=secondary_entity_id,
            caused_by_event_id=caused_by_event_id,
            event_data=event_data or {},
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.add(event)
        db.commit()
        return event.id
    except Exception:
        logger.exception("Failed to record behavioral event %s/%s", event_category, event_type)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def find_causal_event(
    db: Session,
    tenant_id: str,
    entity_id: str,
    entity_type: str,
    action_event_types: list[str],
    within_days: int = 60,
) -> str | None:
    """Find the most recent agent action for this entity within the time window."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
        event = (
            db.query(BehavioralEvent)
            .filter(
                BehavioralEvent.tenant_id == tenant_id,
                BehavioralEvent.entity_id == entity_id,
                BehavioralEvent.entity_type == entity_type,
                BehavioralEvent.event_type.in_(action_event_types),
                BehavioralEvent.occurred_at >= cutoff,
                BehavioralEvent.event_category == "agent_action",
            )
            .order_by(desc(BehavioralEvent.occurred_at))
            .first()
        )
        return event.id if event else None
    except Exception:
        logger.exception("Failed to find causal event")
        return None


def mark_outcome_measured(db: Session, event_id: str) -> None:
    try:
        db.query(BehavioralEvent).filter(BehavioralEvent.id == event_id).update({
            "outcome_measured": True,
            "outcome_measured_at": datetime.now(timezone.utc),
        })
        db.commit()
    except Exception:
        logger.exception("Failed to mark outcome measured")
        try:
            db.rollback()
        except Exception:
            pass


def get_entity_events(
    db: Session, tenant_id: str, entity_type: str, entity_id: str,
    event_types: list[str] | None = None, period_days: int = 180,
) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
    query = db.query(BehavioralEvent).filter(
        BehavioralEvent.tenant_id == tenant_id,
        BehavioralEvent.entity_type == entity_type,
        BehavioralEvent.entity_id == entity_id,
        BehavioralEvent.occurred_at >= cutoff,
    )
    if event_types:
        query = query.filter(BehavioralEvent.event_type.in_(event_types))
    events = query.order_by(desc(BehavioralEvent.occurred_at)).all()
    return [
        {
            "id": e.id,
            "event_category": e.event_category,
            "event_type": e.event_type,
            "event_data": e.event_data,
            "actor_type": e.actor_type,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in events
    ]


# ---------------------------------------------------------------------------
# Insight Generation
# ---------------------------------------------------------------------------


def generate_insight(
    db: Session,
    tenant_id: str,
    insight_type: str,
    headline: str,
    detail: str | None = None,
    scope: str = "tenant",
    scope_entity_type: str | None = None,
    scope_entity_id: str | None = None,
    supporting_data: dict | None = None,
    confidence: float = 0.80,
    action_type: str | None = None,
    action_label: str | None = None,
    action_url: str | None = None,
    generated_by_job: str | None = None,
    data_period_start: date | None = None,
    data_period_end: date | None = None,
) -> BehavioralInsight | None:
    """Create or update a behavioral insight. Skips if below confidence threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return None

    # Check suppression
    if scope_entity_id:
        suppressed = (
            db.query(BehavioralInsight)
            .filter(
                BehavioralInsight.tenant_id == tenant_id,
                BehavioralInsight.insight_type == insight_type,
                BehavioralInsight.scope_entity_id == scope_entity_id,
                BehavioralInsight.suppressed_until.isnot(None),
                BehavioralInsight.suppressed_until > date.today(),
            )
            .first()
        )
        if suppressed:
            return None

    # Check for existing active insight of same type and scope
    existing = (
        db.query(BehavioralInsight)
        .filter(
            BehavioralInsight.tenant_id == tenant_id,
            BehavioralInsight.insight_type == insight_type,
            BehavioralInsight.scope == scope,
            BehavioralInsight.status.in_(["active", "seen"]),
        )
    )
    if scope_entity_id:
        existing = existing.filter(BehavioralInsight.scope_entity_id == scope_entity_id)
    existing = existing.first()

    if existing:
        existing.last_updated_at = datetime.now(timezone.utc)
        existing.headline = headline
        if detail:
            existing.detail = detail
        existing.supporting_data = supporting_data or {}
        existing.confidence = confidence
        db.commit()
        return existing

    insight = BehavioralInsight(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        insight_type=insight_type,
        scope=scope,
        scope_entity_type=scope_entity_type,
        scope_entity_id=scope_entity_id,
        headline=headline,
        detail=detail,
        supporting_data=supporting_data or {},
        confidence=confidence,
        action_type=action_type,
        action_label=action_label,
        action_url=action_url,
        generated_by_job=generated_by_job,
        data_period_start=data_period_start,
        data_period_end=data_period_end,
    )
    db.add(insight)
    db.commit()
    return insight


# ---------------------------------------------------------------------------
# Insight Queries
# ---------------------------------------------------------------------------


def get_insights(
    db: Session, tenant_id: str, status: str | None = None,
    scope: str | None = None, entity_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = db.query(BehavioralInsight).filter(BehavioralInsight.tenant_id == tenant_id)
    if status:
        query = query.filter(BehavioralInsight.status == status)
    if scope:
        query = query.filter(BehavioralInsight.scope == scope)
    if entity_id:
        query = query.filter(BehavioralInsight.scope_entity_id == entity_id)
    insights = query.order_by(desc(BehavioralInsight.confidence), desc(BehavioralInsight.first_surfaced_at)).limit(limit).all()
    return [
        {
            "id": i.id,
            "insight_type": i.insight_type,
            "scope": i.scope,
            "scope_entity_type": i.scope_entity_type,
            "scope_entity_id": i.scope_entity_id,
            "headline": i.headline,
            "detail": i.detail,
            "supporting_data": i.supporting_data,
            "confidence": float(i.confidence) if i.confidence else None,
            "action_type": i.action_type,
            "action_label": i.action_label,
            "action_url": i.action_url,
            "status": i.status,
            "first_surfaced_at": i.first_surfaced_at.isoformat() if i.first_surfaced_at else None,
        }
        for i in insights
    ]


def get_insight_count(db: Session, tenant_id: str) -> int:
    return (
        db.query(BehavioralInsight)
        .filter(BehavioralInsight.tenant_id == tenant_id, BehavioralInsight.status == "active")
        .count()
    )


def dismiss_insight(db: Session, insight_id: str, user_id: str, reason: str | None = None, suppress_days: int = 90) -> bool:
    insight = db.query(BehavioralInsight).filter(BehavioralInsight.id == insight_id).first()
    if not insight:
        return False
    insight.status = "dismissed"
    insight.dismissed_by = user_id
    insight.dismissed_at = datetime.now(timezone.utc)
    insight.dismissal_reason = reason
    insight.suppressed_until = date.today() + timedelta(days=suppress_days)
    db.commit()
    return True


def mark_insight_seen(db: Session, insight_id: str) -> bool:
    return (
        db.query(BehavioralInsight)
        .filter(BehavioralInsight.id == insight_id, BehavioralInsight.status == "active")
        .update({"status": "seen"})
    ) > 0


def add_feedback(
    db: Session, tenant_id: str, insight_id: str, user_id: str,
    feedback_type: str, note: str | None = None,
) -> InsightFeedback:
    fb = InsightFeedback(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        insight_id=insight_id,
        user_id=user_id,
        feedback_type=feedback_type,
        feedback_note=note,
    )
    db.add(fb)
    if feedback_type == "acted_on":
        db.query(BehavioralInsight).filter(BehavioralInsight.id == insight_id).update({"status": "acted_on"})
    db.commit()
    return fb


# ---------------------------------------------------------------------------
# Entity Profiles
# ---------------------------------------------------------------------------


def get_or_create_profile(
    db: Session, tenant_id: str, entity_type: str, entity_id: str,
) -> EntityBehavioralProfile:
    profile = (
        db.query(EntityBehavioralProfile)
        .filter(
            EntityBehavioralProfile.tenant_id == tenant_id,
            EntityBehavioralProfile.entity_type == entity_type,
            EntityBehavioralProfile.entity_id == entity_id,
        )
        .first()
    )
    if not profile:
        profile = EntityBehavioralProfile(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_profile(db: Session, tenant_id: str, entity_type: str, entity_id: str) -> dict | None:
    profile = (
        db.query(EntityBehavioralProfile)
        .filter(
            EntityBehavioralProfile.tenant_id == tenant_id,
            EntityBehavioralProfile.entity_type == entity_type,
            EntityBehavioralProfile.entity_id == entity_id,
        )
        .first()
    )
    if not profile:
        return None
    return {
        "entity_type": profile.entity_type,
        "entity_id": profile.entity_id,
        "avg_days_to_pay": float(profile.avg_days_to_pay) if profile.avg_days_to_pay else None,
        "payment_consistency_score": float(profile.payment_consistency_score) if profile.payment_consistency_score else None,
        "discount_uptake_rate": float(profile.discount_uptake_rate) if profile.discount_uptake_rate else None,
        "collections_response_rate": float(profile.collections_response_rate) if profile.collections_response_rate else None,
        "preferred_contact_day": profile.preferred_contact_day,
        "finance_charge_forgiveness_rate": float(profile.finance_charge_forgiveness_rate) if profile.finance_charge_forgiveness_rate else None,
        "relationship_health_score": float(profile.relationship_health_score) if profile.relationship_health_score else None,
        "relationship_health_trend": profile.relationship_health_trend,
        "last_order_date": str(profile.last_order_date) if profile.last_order_date else None,
        "order_frequency_days": float(profile.order_frequency_days) if profile.order_frequency_days else None,
        "on_time_delivery_rate": float(profile.on_time_delivery_rate) if profile.on_time_delivery_rate else None,
        "invoice_accuracy_rate": float(profile.invoice_accuracy_rate) if profile.invoice_accuracy_rate else None,
        "avg_price_variance_percent": float(profile.avg_price_variance_percent) if profile.avg_price_variance_percent else None,
        "price_trend": profile.price_trend,
        "last_computed_at": profile.last_computed_at.isoformat() if profile.last_computed_at else None,
    }


# ---------------------------------------------------------------------------
# Cemetery enrichment — funeral home behavioral profiles
# ---------------------------------------------------------------------------

_MIN_ORDERS_FOR_ENRICHMENT = 5


def enrich_funeral_home_profiles(db: Session, tenant_id: str) -> int:
    """
    PROFILE_UPDATE_JOB — cemetery enrichment pass.

    For each funeral home customer with 5+ orders in Bridgeable, analyse:
      - Most common vault type
      - Most common equipment combination
      - Top cemeteries

    Updates entity_behavioral_profiles.profile_data JSONB with cemetery
    and vault preference fields.

    Returns count of profiles updated.
    """
    from app.models.customer import Customer
    from app.models.funeral_home_cemetery_history import FuneralHomeCemeteryHistory
    from app.models.cemetery import Cemetery
    from app.models.sales_order import SalesOrder
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    updated = 0

    # Find funeral home customers with sufficient order history
    funeral_homes = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.customer_type == "funeral_home",
            Customer.is_active == True,  # noqa: E712
        )
        .all()
    )

    for fh in funeral_homes:
        # Count orders for this customer
        order_count = (
            db.query(func.count(SalesOrder.id))
            .filter(
                SalesOrder.company_id == tenant_id,
                SalesOrder.customer_id == fh.id,
            )
            .scalar()
            or 0
        )

        if order_count < _MIN_ORDERS_FOR_ENRICHMENT:
            continue

        # Top cemeteries from history table
        top_cemetery_records = (
            db.query(FuneralHomeCemeteryHistory)
            .filter(
                FuneralHomeCemeteryHistory.company_id == tenant_id,
                FuneralHomeCemeteryHistory.customer_id == fh.id,
            )
            .order_by(FuneralHomeCemeteryHistory.order_count.desc())
            .limit(5)
            .all()
        )

        top_cemeteries = []
        for rec in top_cemetery_records:
            cem = db.query(Cemetery).filter(Cemetery.id == rec.cemetery_id).first()
            if cem and cem.is_active:
                top_cemeteries.append(
                    {
                        "cemetery_id": rec.cemetery_id,
                        "cemetery_name": cem.name,
                        "order_count": rec.order_count,
                    }
                )

        if not top_cemeteries:
            continue

        # Upsert the behavioral profile
        profile = (
            db.query(EntityBehavioralProfile)
            .filter(
                EntityBehavioralProfile.tenant_id == tenant_id,
                EntityBehavioralProfile.entity_type == "customer",
                EntityBehavioralProfile.entity_id == fh.id,
            )
            .first()
        )

        enrichment_patch = {
            "top_cemeteries": top_cemeteries,
            "cemetery_enrichment_at": datetime.now(timezone.utc).isoformat(),
            "order_count_at_enrichment": order_count,
        }

        if profile:
            existing = profile.profile_data or {}
            existing.update(enrichment_patch)
            profile.profile_data = existing
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(profile, "profile_data")
        else:
            profile = EntityBehavioralProfile(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                entity_type="customer",
                entity_id=fh.id,
                profile_data=enrichment_patch,
            )
            db.add(profile)

        updated += 1

    if updated:
        db.commit()

    return updated

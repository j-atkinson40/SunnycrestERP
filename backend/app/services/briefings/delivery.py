"""Phase 6 — briefing delivery dispatch.

Follows the Phase D-7 pattern: every email flows through the managed
template registry via `document_renderer.render_html(template_key=...)`
then through `DeliveryService`. No on-disk Jinja templates;
`scripts/seed_intelligence_phase6.py` seeds the `email.briefing.morning`
+ `email.briefing.evening` template_key rows.

in-app delivery is pull-based (frontend fetches `/briefings/v2/latest`),
so this module's in_app handler only stamps `delivered_at`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.briefing import Briefing
from app.models.company import Company
from app.models.user import User

logger = logging.getLogger(__name__)


def deliver_briefing(
    db: Session,
    briefing: Briefing,
    *,
    channels: list[str],
) -> list[str]:
    """Dispatch the briefing via each channel. Returns channels that
    actually delivered (failures are logged, not raised).

    in_app channel is always implicit (the briefing row exists → UI can
    fetch it); including "in_app" in `channels` just stamps the
    `delivered_at` timestamp so reporting can distinguish "generated but
    not yet delivered" from "delivered".
    """
    delivered: list[str] = []

    if "in_app" in channels:
        # Stamp and move on.
        briefing.delivered_at = datetime.now(timezone.utc)
        delivered.append("in_app")

    if "email" in channels:
        ok = _deliver_email(db, briefing)
        if ok:
            delivered.append("email")
            if briefing.delivered_at is None:
                briefing.delivered_at = datetime.now(timezone.utc)

    briefing.delivery_channels = delivered
    flag_modified(briefing, "delivery_channels")
    db.commit()
    return delivered


# ── Channels ─────────────────────────────────────────────────────────


def _deliver_email(db: Session, briefing: Briefing) -> bool:
    """Send the briefing as an email via DeliveryService.

    Template: `email.briefing.morning` or `email.briefing.evening`.
    Context: `{user, company, narrative, sections, briefing_id}`.
    Subject: rendered from the same template's subject block.
    """
    # Resolve recipient + sender metadata.
    user = db.query(User).filter(User.id == briefing.user_id).first()
    if not user or not user.email:
        logger.info(
            "Briefing %s email skipped — user email not available",
            briefing.id,
        )
        return False
    company = (
        db.query(Company).filter(Company.id == briefing.company_id).first()
    )
    company_name = company.name if company else "Bridgeable"

    template_key = (
        "email.briefing.morning"
        if briefing.briefing_type == "morning"
        else "email.briefing.evening"
    )

    try:
        from app.services.delivery import delivery_service
    except ImportError as e:  # pragma: no cover — defensive
        logger.warning("DeliveryService unavailable: %s", e)
        return False

    context: dict[str, Any] = {
        "user_first_name": user.first_name or "there",
        "user_last_name": user.last_name or "",
        "company_name": company_name,
        "briefing_type": briefing.briefing_type,
        "narrative_text": briefing.narrative_text,
        "structured_sections": briefing.structured_sections or {},
        "briefing_id": briefing.id,
    }

    try:
        delivery = delivery_service.send_email_with_template(
            db,
            company_id=briefing.company_id,
            to_email=user.email,
            to_name=user.first_name,
            template_key=template_key,
            template_context=context,
            subject_override=_subject_for(briefing, company_name),
            caller_module="briefings",
        )
        ok = bool(getattr(delivery, "status", None) in ("sent", "delivered"))
        if not ok:
            logger.info(
                "Briefing email not accepted by channel: status=%s",
                getattr(delivery, "status", None),
            )
        return ok
    except Exception as e:
        logger.exception("Briefing email send raised: %s", e)
        return False


def _subject_for(briefing: Briefing, company_name: str) -> str:
    if briefing.briefing_type == "morning":
        return f"Your morning briefing — {company_name}"
    return f"End of day summary — {company_name}"


__all__ = ["deliver_briefing"]

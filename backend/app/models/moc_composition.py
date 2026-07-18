"""Maps of Content — the composition store + the engagement substrate
(The Map Home campaign, r130 + r131).

`MoCComposition` — platform-tier authored compositions, one store for both:
  kind='area'        — an area overview ponder's philosophy layer: `captions`
                       (beat_key → authored text) overlay the deriver's honest
                       placeholders, the SAME pattern as task-ponder captions.
                       Keyed (kind, key=<vocabulary type>, vertical).
  kind='onboarding'  — fully-authored beat sequences (`beats` JSONB list of
                       {key, kind, text}); `sequence` orders the curriculum
                       LIST (deliberately not an engine). Vertical-less.

`PonderEngagement` — one row per (user, ponder_key); the quiet record of
viewed/completed/dismissed across ALL ponder kinds. Suggestions + the
onboarding-state derivation read it; nothing else does (yet — the
usage-driven layer arrives when this substrate has history to be honest
about).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCComposition(Base):
    __tablename__ = "moc_composition"
    __table_args__ = (
        CheckConstraint("kind IN ('area', 'onboarding', 'platform', 'tip', 'module')", name="ck_moc_composition_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    captions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    beats: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PonderEngagement(Base):
    __tablename__ = "ponder_engagement"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ponder_key: Mapped[str] = mapped_column(String(200), nullable=False)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

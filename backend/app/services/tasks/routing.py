"""v1 task substrate B3 — three-tier routing resolver + assignee resolution.

Per build prompt §7.8 + state doc §5.4.

Three-tier inheritance (FIRST MATCH WINS at READ time):
  tenant → vertical_default → platform_default

Two routing modes ship in v1:
  • direct_user — returns the rule's target_user_id verbatim.
  • round_robin — queries users with the rule's target_permission_key
                  in the tenant, picks the least-recently-assigned one
                  (via the most recent task_details.assigned_at the
                  user owns), and returns that user_id. Deterministic
                  within a single create call.

Called by `create_task_with_provenance` when no explicit
assignee_user_id is supplied AND a routing rule exists for the
task_type_key. The resolver is failure-tolerant: if no rule matches,
returns None and the caller proceeds with the original (None) assignee.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.task_details import TaskDetails
from app.models.task_routing_rule import TaskRoutingRule


logger = logging.getLogger(__name__)


class RoutingResult:
    """Lightweight return shape for the resolver."""

    __slots__ = ("rule", "assignee_user_id")

    def __init__(
        self,
        rule: TaskRoutingRule,
        assignee_user_id: str | None,
    ) -> None:
        self.rule = rule
        self.assignee_user_id = assignee_user_id


def _resolve_company_vertical(db: Session, company_id: str) -> str | None:
    """Read Company.vertical for the given tenant."""
    try:
        from app.models.company import Company

        co = db.query(Company).filter(Company.id == company_id).first()
        if co is None:
            return None
        return co.vertical
    except Exception:
        return None


def _pick_round_robin_user(
    db: Session,
    *,
    company_id: str,
    permission_key: str,
) -> str | None:
    """Return least-recently-assigned user in tenant with permission.

    Permission lookup honors the standard `core.permissions` resolution
    via `user_has_permission`. Pick deterministically: the user whose
    most-recent assigned task is oldest (or who has zero assignments)
    wins. Ties broken by user.id sort.
    """
    try:
        from app.models.user import User
    except ImportError:
        return None

    candidates: list[User] = []
    try:
        users = (
            db.query(User)
            .filter(User.company_id == company_id)
            .filter(User.is_active.is_(True))
            .all()
        )
    except Exception:
        return None

    # Late import to avoid circular dep at module load.
    from app.core.permissions import user_has_permission

    for u in users:
        try:
            if user_has_permission(u, db, permission_key):
                candidates.append(u)
        except Exception:
            continue

    if not candidates:
        return None

    # Tabulate most-recent assignment per candidate.
    def _last_assigned(user_id: str) -> Any:
        row = (
            db.query(TaskDetails.assigned_at)
            .filter(TaskDetails.assignee_user_id == user_id)
            .order_by(TaskDetails.assigned_at.desc().nullslast())
            .first()
        )
        return row[0] if row is not None else None

    # Least-recently-assigned (None = never assigned, wins).
    def _sort_key(u: User) -> tuple[int, Any, str]:
        last = _last_assigned(u.id)
        # Sort: never-assigned (None) first → tuple (0, "", user.id);
        # then by assigned_at asc; final tiebreak by user.id.
        if last is None:
            return (0, "", u.id)
        return (1, last.isoformat(), u.id)

    candidates.sort(key=_sort_key)
    return candidates[0].id


def resolve_routing(
    db: Session,
    *,
    company_id: str,
    task_type_key: str,
    vertical: str | None = None,
) -> RoutingResult | None:
    """Resolve a routing rule + assignee for a given (tenant, task_type).

    Walk tenant → vertical_default → platform_default; first match wins.
    Within a tier, highest priority wins (descending); ties broken by
    created_at desc.

    For matched rules, additionally compute the assignee_user_id:
      • direct_user → rule.target_user_id verbatim
      • round_robin → least-recently-assigned permission-holder

    Returns None when no rule matches the task_type_key.
    """
    if vertical is None:
        vertical = _resolve_company_vertical(db, company_id)

    def _query_for_scope(
        scope: str,
        *,
        vertical_filter: str | None = None,
        tenant_filter: str | None = None,
    ) -> TaskRoutingRule | None:
        q = (
            db.query(TaskRoutingRule)
            .filter(TaskRoutingRule.task_type_key == task_type_key)
            .filter(TaskRoutingRule.scope == scope)
            .filter(TaskRoutingRule.is_active.is_(True))
        )
        if vertical_filter is not None:
            q = q.filter(TaskRoutingRule.vertical == vertical_filter)
        if tenant_filter is not None:
            q = q.filter(TaskRoutingRule.tenant_id == tenant_filter)
        q = q.order_by(
            TaskRoutingRule.priority.desc(),
            TaskRoutingRule.created_at.desc(),
        )
        return q.first()

    # Tier 1 — tenant
    rule = _query_for_scope("tenant", tenant_filter=company_id)
    # Tier 2 — vertical_default
    if rule is None and vertical:
        rule = _query_for_scope("vertical_default", vertical_filter=vertical)
    # Tier 3 — platform_default
    if rule is None:
        rule = _query_for_scope("platform_default")
    if rule is None:
        return None

    # Apply routing mode.
    assignee_user_id: str | None = None
    if rule.routing_mode == "direct_user":
        assignee_user_id = rule.target_user_id
    elif rule.routing_mode == "round_robin":
        if rule.target_permission_key:
            assignee_user_id = _pick_round_robin_user(
                db,
                company_id=company_id,
                permission_key=rule.target_permission_key,
            )

    return RoutingResult(rule=rule, assignee_user_id=assignee_user_id)


__all__ = ["RoutingResult", "resolve_routing"]

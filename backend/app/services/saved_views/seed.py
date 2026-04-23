"""Role-based saved-view seeding — Phase 2.

Each (vertical, role) has a list of `SeedViewTemplate` defaults.
When a user is created or their roles change, `seed_for_user()`:

  1. Reads the user's `preferences.saved_views_seeded_for_roles`
     array (an array of role slugs already seeded).
  2. Determines the user's current roles (right now: 1 role per
     user via role_id; multi-role future-proofed via the list
     model).
  3. For each role NOT yet in the array:
     a. Looks up `SEED_TEMPLATES[(vertical, role_slug)]` — may be
        empty for that combo.
     b. Creates a VaultItem per template (idempotent via
        `source_entity_id = "saved_view_seed:{role_slug}:{template_id}"`).
     c. Appends the role_slug to the preferences array.

Idempotency rules:
  - Running seed_for_user twice in a row creates zero new views.
  - Adding a new template AND running seed_for_user on a user
    whose role was previously seeded will NOT backfill the new
    template. Template additions require either a one-off backfill
    script OR a role-version bump. Phase 2 accepts this trade-off
    per the approved audit.

Templates live inline in SEED_TEMPLATES. A template is a
SavedViewConfig plus a human title + description.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.role import Role
from app.models.user import User
from app.models.vault_item import VaultItem
from app.services.saved_views import crud as crud_mod
from app.services.saved_views.types import (
    CalendarConfig,
    CardConfig,
    EntityType,
    Filter,
    KanbanConfig,
    Permissions,
    Presentation,
    Query,
    SavedViewConfig,
    Sort,
    StatConfig,
    TableConfig,
)

logger = logging.getLogger(__name__)


# ── Template model ───────────────────────────────────────────────────


@dataclass
class SeedTemplate:
    """One seed template. Per-user instantiation supplies owner +
    shared_with_roles at create time."""

    template_id: str       # stable key, becomes part of source_entity_id
    title: str
    description: str | None
    entity_type: EntityType
    # Build a SavedViewConfig FOR this template. The factory receives
    # the role slug so role-filter views can reference the user's
    # role. It returns a config WITHOUT the owner_user_id set —
    # seed_for_user fills that in.
    config_factory: Any    # Callable[[str], SavedViewConfig]


def _template_seed_key(role_slug: str, template_id: str) -> str:
    """The stable key stored in VaultItem.source_entity_id for seed
    idempotency."""
    return f"saved_view_seed:{role_slug}:{template_id}"


# ── Helpers for building seed configs ────────────────────────────────


def _basic_list(
    *,
    entity_type: EntityType,
    filters: list[Filter] | None = None,
    sort: list[Sort] | None = None,
    role_slug: str = "admin",
) -> SavedViewConfig:
    return SavedViewConfig(
        query=Query(
            entity_type=entity_type,
            filters=filters or [],
            sort=sort or [],
        ),
        presentation=Presentation(mode="list"),
        permissions=Permissions(
            owner_user_id="",  # filled in by seed_for_user
            visibility="role_shared",
            shared_with_roles=[role_slug],
        ),
    )


def _basic_table(
    *,
    entity_type: EntityType,
    filters: list[Filter] | None = None,
    sort: list[Sort] | None = None,
    columns: list[str] | None = None,
    role_slug: str = "admin",
) -> SavedViewConfig:
    return SavedViewConfig(
        query=Query(
            entity_type=entity_type,
            filters=filters or [],
            sort=sort or [],
        ),
        presentation=Presentation(
            mode="table",
            table_config=TableConfig(columns=columns or []),
        ),
        permissions=Permissions(
            owner_user_id="",
            visibility="role_shared",
            shared_with_roles=[role_slug],
        ),
    )


def _basic_kanban(
    *,
    entity_type: EntityType,
    group_by: str,
    card_title: str,
    card_meta: list[str] | None = None,
    filters: list[Filter] | None = None,
    role_slug: str = "admin",
) -> SavedViewConfig:
    from app.services.saved_views.types import Grouping

    return SavedViewConfig(
        query=Query(
            entity_type=entity_type,
            filters=filters or [],
            grouping=Grouping(field=group_by),
        ),
        presentation=Presentation(
            mode="kanban",
            kanban_config=KanbanConfig(
                group_by_field=group_by,
                card_title_field=card_title,
                card_meta_fields=card_meta or [],
            ),
        ),
        permissions=Permissions(
            owner_user_id="",
            visibility="role_shared",
            shared_with_roles=[role_slug],
        ),
    )


# ── Templates by (vertical, role) ───────────────────────────────────
# Keys: ("vertical_slug", "role_slug"). Values: list of SeedTemplate.
#
# Role slugs match Role.slug on the Role model. Common slugs in
# this codebase: "admin", "office", "director", "production",
# "driver", "accountant". Unknown slugs are silently no-op.


SEED_TEMPLATES: dict[tuple[str, str], list[SeedTemplate]] = {
    # ── Funeral Home — director ──────────────────────────────────
    ("funeral_home", "director"): [
        SeedTemplate(
            template_id="my_active_cases",
            title="My active cases",
            description="Cases I am working on that aren't closed.",
            entity_type="fh_case",
            config_factory=lambda role: _basic_list(
                entity_type="fh_case",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["closed", "cancelled"]),
                ],
                sort=[Sort(field="updated_at", direction="desc")],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="this_weeks_services",
            title="This week's services",
            description="Events and services scheduled in the next 7 days.",
            entity_type="vault_item",
            config_factory=lambda role: SavedViewConfig(
                query=Query(
                    entity_type="vault_item",
                    filters=[
                        Filter(field="item_type", operator="eq", value="event"),
                        Filter(field="status", operator="eq", value="active"),
                    ],
                    sort=[Sort(field="event_start", direction="asc")],
                ),
                presentation=Presentation(
                    mode="calendar",
                    calendar_config=CalendarConfig(
                        date_field="event_start",
                        end_date_field="event_end",
                        label_field="title",
                    ),
                ),
                permissions=Permissions(
                    owner_user_id="",
                    visibility="role_shared",
                    shared_with_roles=[role],
                ),
            ),
        ),
    ],

    # ── Office manager (generic) ─────────────────────────────────
    ("manufacturing", "office"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "invoice_date", "due_date"],
                role_slug=role,
            ),
        ),
    ],
    # same for funeral_home office
    ("funeral_home", "office"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "invoice_date", "due_date"],
                role_slug=role,
            ),
        ),
    ],

    # ── Manufacturing — production role ──────────────────────────
    # Production-board replacement: kanban of active WOs grouped by
    # status. The existing /api/v1/production/board endpoint stays
    # in place; frontend dashboards use these saved views via the
    # widget component.
    ("manufacturing", "production"): [
        SeedTemplate(
            template_id="active_pours",
            title="Active pours",
            description="Work orders in active production.",
            entity_type="vault_item",
            config_factory=lambda role: _basic_kanban(
                entity_type="vault_item",
                group_by="status",
                card_title="title",
                card_meta=["event_type"],
                filters=[
                    Filter(field="item_type", operator="eq", value="production_record"),
                ],
                role_slug=role,
            ),
        ),
    ],

    # ── Admin across every vertical — a minimal safety net ───────
    ("manufacturing", "admin"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "due_date"],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="recent_cases",
            title="Recent cases",
            description="Cases updated in the last 30 days.",
            entity_type="fh_case",
            config_factory=lambda role: _basic_list(
                entity_type="fh_case",
                sort=[Sort(field="updated_at", direction="desc")],
                role_slug=role,
            ),
        ),
    ],
    ("funeral_home", "admin"): [
        SeedTemplate(
            template_id="my_active_cases",
            title="My active cases",
            description="Cases the team is actively working.",
            entity_type="fh_case",
            config_factory=lambda role: _basic_list(
                entity_type="fh_case",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["closed", "cancelled"]),
                ],
                sort=[Sort(field="updated_at", direction="desc")],
                role_slug=role,
            ),
        ),
    ],

    # ────────────────────────────────────────────────────────────────
    # Phase 8e — saved view seeds for new space templates
    # Each Phase 8e space template that references
    # `saved_view_seed:<role>:<key>` needs a matching SeedTemplate
    # here (seed key = `saved_view_seed:{role_slug}:{template_id}`).
    # ────────────────────────────────────────────────────────────────

    # ── Cemetery — admin ──
    ("cemetery", "admin"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "due_date"],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="recent_cases",
            title="Recent cases",
            description="Cases updated in the last 30 days.",
            entity_type="fh_case",
            config_factory=lambda role: _basic_list(
                entity_type="fh_case",
                sort=[Sort(field="updated_at", direction="desc")],
                role_slug=role,
            ),
        ),
    ],

    # ── Cemetery — office ──
    ("cemetery", "office"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "invoice_date", "due_date"],
                role_slug=role,
            ),
        ),
    ],

    # ── Crematory — admin ──
    ("crematory", "admin"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "due_date"],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="recent_cases",
            title="Recent cases",
            description="Cases updated in the last 30 days.",
            entity_type="fh_case",
            config_factory=lambda role: _basic_list(
                entity_type="fh_case",
                sort=[Sort(field="updated_at", direction="desc")],
                role_slug=role,
            ),
        ),
    ],

    # ── Crematory — office ──
    ("crematory", "office"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "invoice_date", "due_date"],
                role_slug=role,
            ),
        ),
    ],

    # ── Funeral home — accountant ──
    ("funeral_home", "accountant"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "invoice_date", "due_date"],
                role_slug=role,
            ),
        ),
    ],

    # ── Manufacturing — accountant ──
    ("manufacturing", "accountant"): [
        SeedTemplate(
            template_id="outstanding_invoices",
            title="Outstanding invoices",
            description="Invoices that aren't paid.",
            entity_type="invoice",
            config_factory=lambda role: _basic_table(
                entity_type="invoice",
                filters=[
                    Filter(field="status", operator="not_in",
                           value=["paid", "cancelled"]),
                ],
                sort=[Sort(field="due_date", direction="asc")],
                columns=["number", "status", "total", "due_date"],
                role_slug=role,
            ),
        ),
    ],

    # ────────────────────────────────────────────────────────────────
    # Phase B Session 1 — Dispatcher (manufacturing) saved-view seeds.
    # Five filtered views over the `delivery` entity type. Referenced
    # by the (manufacturing, dispatcher) Pulse composition in
    # `spaces/pulse_compositions.py` via their seed keys.
    #
    # NOTE ON DATE FILTERS — these seeds intentionally filter on
    # structural conditions (scheduling_type, status, null/not-null)
    # rather than relative dates. Today/Tomorrow/Two-Days-Out are
    # rendered by the `dispatch_monitor` component which computes
    # relative dates at render time; they don't live as saved views.
    # Relative-date filters are a deferred saved-view feature.
    # ────────────────────────────────────────────────────────────────

    ("manufacturing", "dispatcher"): [
        SeedTemplate(
            template_id="pending_dispatch",
            title="Needs a driver",
            description=(
                "Kanban-scheduled deliveries with a requested date set "
                "but not yet assigned to a driver."
            ),
            entity_type="delivery",
            config_factory=lambda role: _basic_table(
                entity_type="delivery",
                filters=[
                    Filter(field="scheduling_type", operator="eq", value="kanban"),
                    Filter(field="requested_date", operator="is_not_null"),
                    Filter(field="status", operator="not_in",
                           value=["completed", "cancelled", "failed"]),
                    Filter(field="assigned_driver_id", operator="is_null"),
                ],
                sort=[Sort(field="requested_date", direction="asc")],
                columns=[
                    "requested_date",
                    "status",
                    "hole_dug_status",
                    "assigned_driver_id",
                ],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="this_weeks_deliveries",
            title="This week's deliveries",
            description=(
                "All active kanban-scheduled deliveries across the "
                "coming week, sorted by date."
            ),
            entity_type="delivery",
            config_factory=lambda role: _basic_table(
                entity_type="delivery",
                filters=[
                    Filter(field="scheduling_type", operator="eq", value="kanban"),
                    Filter(field="requested_date", operator="is_not_null"),
                    Filter(field="status", operator="not_in",
                           value=["completed", "cancelled", "failed"]),
                ],
                sort=[Sort(field="requested_date", direction="asc")],
                columns=[
                    "requested_date",
                    "status",
                    "priority",
                    "hole_dug_status",
                    "assigned_driver_id",
                ],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="ancillary_pending",
            title="Ancillary — pickup / drop",
            description=(
                "Ancillary deliveries awaiting a dispatcher's next "
                "action (unassigned, awaiting pickup, assigned)."
            ),
            entity_type="delivery",
            config_factory=lambda role: _basic_list(
                entity_type="delivery",
                filters=[
                    Filter(field="scheduling_type", operator="eq", value="ancillary"),
                    Filter(
                        field="ancillary_fulfillment_status",
                        operator="in",
                        value=["unassigned", "awaiting_pickup", "assigned_to_driver"],
                    ),
                ],
                sort=[Sort(field="requested_date", direction="asc")],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="direct_ship_pending",
            title="Direct ship — in flight",
            description=(
                "Direct-ship deliveries pending fulfillment from "
                "Wilbert. Dispatcher tracks ordered + shipped states."
            ),
            entity_type="delivery",
            config_factory=lambda role: _basic_list(
                entity_type="delivery",
                filters=[
                    Filter(field="scheduling_type", operator="eq", value="direct_ship"),
                    Filter(
                        field="direct_ship_status",
                        operator="in",
                        value=["pending", "ordered_from_wilbert", "shipped"],
                    ),
                ],
                sort=[Sort(field="requested_date", direction="asc")],
                role_slug=role,
            ),
        ),
        SeedTemplate(
            template_id="hole_dug_unknown",
            title="Hole status unknown",
            description=(
                "Kanban deliveries whose hole-dug status is unresolved "
                "— quick-toggle from the Monitor card."
            ),
            entity_type="delivery",
            config_factory=lambda role: _basic_list(
                entity_type="delivery",
                filters=[
                    Filter(field="scheduling_type", operator="eq", value="kanban"),
                    Filter(field="requested_date", operator="is_not_null"),
                    Filter(field="status", operator="not_in",
                           value=["completed", "cancelled", "failed"]),
                    Filter(field="hole_dug_status", operator="is_null"),
                ],
                sort=[Sort(field="requested_date", direction="asc")],
                role_slug=role,
            ),
        ),
    ],
}


# ── Public API ───────────────────────────────────────────────────────


def seed_for_user(
    db: Session,
    *,
    user: User,
    tenant_vertical: str | None = None,
) -> int:
    """Seed default saved views for `user` based on their current
    roles. Idempotent — safe to call on every login, user creation,
    or role change.

    Arguments:
        db: active DB session
        user: the user to seed (User ORM instance)
        tenant_vertical: "manufacturing" | "funeral_home" | etc.
            Resolved from the company if not provided.

    Returns the number of new saved views created.
    """
    vertical = tenant_vertical or _resolve_tenant_vertical(db, user.company_id)
    if vertical is None:
        # Unknown vertical → nothing to seed. Not an error.
        return 0

    current_roles = _current_role_slugs(db, user)
    if not current_roles:
        return 0

    prefs = dict(user.preferences or {})
    already_seeded = list(prefs.get("saved_views_seeded_for_roles", []))

    new_roles = [r for r in current_roles if r not in already_seeded]
    if not new_roles:
        return 0

    created_count = 0
    for role_slug in new_roles:
        templates = SEED_TEMPLATES.get((vertical, role_slug), [])
        for template in templates:
            if _already_seeded(db, user, role_slug, template.template_id):
                # Defense in depth — preferences array said we
                # haven't seeded this role, but a VaultItem with the
                # seed key exists. Skip creation; don't orphan a row.
                continue
            config = template.config_factory(role_slug)
            crud_mod.create_saved_view(
                db,
                user=user,
                title=template.title,
                description=template.description,
                config=config,
                source_entity_id=_template_seed_key(role_slug, template.template_id),
            )
            created_count += 1
        already_seeded.append(role_slug)

    prefs["saved_views_seeded_for_roles"] = already_seeded
    user.preferences = prefs
    # JSONB in SQLAlchemy — flag the attribute as modified so the
    # change is committed.
    flag_modified(user, "preferences")
    db.commit()
    return created_count


# ── Internal helpers ─────────────────────────────────────────────────


def _resolve_tenant_vertical(db: Session, company_id: str) -> str | None:
    """Look up the company's preset / vertical. Stored on companies."""
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == company_id).first()
    if co is None:
        return None
    # The codebase standard is `vertical`; fall back to `preset` for
    # any historical seed configs.
    return (
        getattr(co, "vertical", None)
        or getattr(co, "preset", None)
        or getattr(co, "preset_key", None)
        or None
    )


def _current_role_slugs(db: Session, user: User) -> list[str]:
    """Single role today (via role_id). Returned as a list to match
    the multi-role future. Handles null role_id."""
    if user.role_id is None:
        return []
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return [role.slug] if role and role.slug else []


def _already_seeded(db: Session, user: User, role_slug: str, template_id: str) -> bool:
    """Second-level idempotency check: does a VaultItem with the
    seed_key already exist for this user in this tenant?"""
    seed_key = _template_seed_key(role_slug, template_id)
    existing = (
        db.query(VaultItem.id)
        .filter(
            VaultItem.company_id == user.company_id,
            VaultItem.created_by == user.id,
            VaultItem.item_type == "saved_view",
            VaultItem.source_entity_id == seed_key,
            VaultItem.is_active.is_(True),
        )
        .first()
    )
    return existing is not None

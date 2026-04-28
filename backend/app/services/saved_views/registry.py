"""Entity type registry for Saved Views — Phase 2.

Declares which entity types can back a saved view, their available
fields with types, and the per-entity query builders the executor
uses to fetch rows with tenant isolation baked in.

Pattern mirrors `backend/app/services/vault/hub_registry.py` and
`backend/app/services/command_bar/registry.py`:

  - Module-level dict + lazy seed on first access
  - `reset_registry()` for tests
  - `register_entity()` replacement API for extensions

Seven entity types registered in Phase 2:

  fh_case, sales_order, invoice, contact, product, document,
  vault_item

The first six match the Phase 1 command-bar resolver entities —
intentional, so the same fuzzy-search resolves to the same
database rows. `vault_item` is the generic fallback (needed for
event-based calendar views, communication feeds, etc.).

To register an 8th entity type in a future phase:

  1. Build an EntityTypeMetadata with the 5 required fields +
     the field list.
  2. `register_entity(metadata)` at app startup.
  3. If the entity has a text column worth fuzzy-matching, add a
     GIN trigram index via a new migration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from sqlalchemy.orm import Query as SAQuery, Session


logger = logging.getLogger(__name__)


# ── Field metadata ───────────────────────────────────────────────────


FieldType = Literal[
    "text",
    "number",
    "currency",
    "date",
    "datetime",
    "boolean",
    "enum",
    "relation",
]


@dataclass
class FieldMetadata:
    """One filterable/sortable/groupable field on an entity."""

    field_name: str         # SQLAlchemy attribute name OR virtual name resolved in query_builder
    display_name: str
    field_type: FieldType
    filterable: bool = True
    sortable: bool = True
    groupable: bool = True
    # Enum values — required when field_type == "enum", ignored otherwise.
    enum_values: list[str] = field(default_factory=list)
    # Relation entity — required when field_type == "relation".
    # The value of this field is the ID of a row in that entity.
    relation_entity: str | None = None
    # If True, field is hidden from the builder UI by default (still
    # accepts values from code). Useful for fields like `id`,
    # `company_id` that aren't user-meaningful.
    hidden_by_default: bool = False
    # Whether the column value needs pre-processing in the executor
    # before comparison (e.g. case-insensitive compares for text).
    # Defaults applied per field_type.
    case_insensitive: bool | None = None

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "display_name": self.display_name,
            "field_type": self.field_type,
            "filterable": self.filterable,
            "sortable": self.sortable,
            "groupable": self.groupable,
            "enum_values": list(self.enum_values),
            "relation_entity": self.relation_entity,
            "hidden_by_default": self.hidden_by_default,
        }


@dataclass
class EntityTypeMetadata:
    """One registered entity type.

    `query_builder(db, company_id)` MUST return a SQLAlchemy Query
    that is already:
      - tenant-isolated (filtered to the caller's company_id)
      - scoped to rows the entity type considers "visible"
        (e.g. is_active filters, NOT including soft-deleted rows)

    Saved view executor calls this query_builder and adds the
    saved-view filters + sort + limit on top. Never overrides
    tenant isolation.

    `allowed_verticals` declares which tenant verticals this entity
    is meaningful for (Phase W-4a Step 3, BRIDGEABLE_MASTER §3.25
    saved view vertical-scope inheritance amendment). Pattern A
    enforcement uses this to:
      - Reject seed templates that bind a cross-vertical entity_type
        to a tenant of incompatible vertical (seed layer).
      - Reject saved-view creation when the tenant's vertical isn't
        in the entity's allowed_verticals (creation layer, 400).
      - Filter out cross-vertical instances at read time
        (defense-in-depth).
    Use `["*"]` for entities that genuinely span every vertical
    (sales_order, invoice, contact, product, document, vault_item,
    delivery). Use `["funeral_home"]`-style narrow lists for entities
    that only one vertical can produce or consume (fh_case is
    FH-only; future cremation / interment entities belong to
    crematory / cemetery respectively).
    """

    entity_type: str       # "fh_case", "sales_order", ...
    display_name: str
    icon: str
    navigate_url_template: str   # e.g. "/cases/{id}" for tile-click
    # Query factory — see docstring.
    query_builder: Callable[[Session, str], SAQuery]
    # Serializer turning a row ORM object → flat dict for JSON
    # transport. Receives a single ORM row; returns dict. The dict's
    # keys are the field_names clients expect.
    row_serializer: Callable[[Any], dict]
    available_fields: list[FieldMetadata] = field(default_factory=list)
    # Default sort used when the saved view doesn't specify one.
    default_sort: list[dict] = field(default_factory=list)
    # Columns shown in "table" presentation mode when the config's
    # table_config.columns is empty. Ordered.
    default_columns: list[str] = field(default_factory=list)
    # Phase W-4a Step 3: vertical-scope inheritance per
    # BRIDGEABLE_MASTER §3.25 amendment. ["*"] = cross-vertical;
    # ["funeral_home"]-style = single-vertical. Default ["*"] for
    # backward compat — explicit entity-by-entity declarations live
    # in _seed_default_entities below.
    allowed_verticals: list[str] = field(default_factory=lambda: ["*"])

    def field_by_name(self, field_name: str) -> FieldMetadata | None:
        return next(
            (f for f in self.available_fields if f.field_name == field_name),
            None,
        )

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "display_name": self.display_name,
            "icon": self.icon,
            "navigate_url_template": self.navigate_url_template,
            "available_fields": [f.to_dict() for f in self.available_fields],
            "default_sort": list(self.default_sort),
            "default_columns": list(self.default_columns),
            "allowed_verticals": list(self.allowed_verticals),
        }


# ── Internal state ───────────────────────────────────────────────────


_registry: dict[str, EntityTypeMetadata] = {}
_seeded: bool = False


def register_entity(metadata: EntityTypeMetadata) -> None:
    """Register (or replace) an entity type by `entity_type`."""
    if metadata.entity_type in _registry:
        logger.debug(
            "saved_views.registry: replacing entity %s",
            metadata.entity_type,
        )
    _registry[metadata.entity_type] = metadata


def get_entity(entity_type: str) -> EntityTypeMetadata | None:
    _ensure_seeded()
    return _registry.get(entity_type)


def list_entities() -> list[EntityTypeMetadata]:
    _ensure_seeded()
    return sorted(_registry.values(), key=lambda e: e.display_name)


def is_entity_compatible_with_vertical(
    entity_type: str,
    vertical: str | None,
) -> bool:
    """Pattern A check (Phase W-4a Step 3, BRIDGEABLE_MASTER §3.25):
    is this entity_type meaningful for a tenant of the given
    vertical?

    Returns True when the entity is cross-vertical (`["*"]` allowed
    list) or when the tenant's vertical is explicitly in the allowed
    list. Returns False otherwise.

    Unknown entity_types return False (defensive — better to reject
    than silently allow). Callers should treat False as "block this
    saved-view from being seeded / created / read in this tenant."

    `vertical=None` returns False — a tenant without a known
    vertical can't accept any vertical-scoped entity. Cross-vertical
    entities still need a known vertical for context (the calling
    tenant must be classified).
    """
    meta = get_entity(entity_type)
    if meta is None:
        return False
    if not vertical:
        return False
    if "*" in meta.allowed_verticals:
        return True
    return vertical in meta.allowed_verticals


def reset_registry() -> None:
    """Test-only — clear and mark unseeded."""
    global _seeded
    _registry.clear()
    _seeded = False


def _ensure_seeded() -> None:
    global _seeded
    if _seeded:
        return
    _seed_default_entities()
    _seeded = True


# ── Seed ─────────────────────────────────────────────────────────────


def _seed_default_entities() -> None:
    """Register the 7 Phase 2 entity types.

    The query_builder lambdas live here because putting them in
    separate files would pull in the full ORM model graph at module
    import time — keeping them inline defers imports to first call.
    """

    # fh_case ────────────────────────────────────────────────────────
    def fh_case_query(db: Session, company_id: str):
        from app.models.fh_case import FHCase

        return db.query(FHCase).filter(
            FHCase.company_id == company_id,
        )

    def fh_case_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "case_number": row.case_number,
            "status": row.status,
            "deceased_first_name": row.deceased_first_name,
            "deceased_last_name": row.deceased_last_name,
            "deceased_date_of_death": _iso_date(row.deceased_date_of_death),
            "service_type": row.service_type,
            "service_date": _iso_date(row.service_date),
            "disposition_type": row.disposition_type,
            "updated_at": _iso_dt(row.updated_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="fh_case",
        display_name="Cases",
        icon="Folder",
        navigate_url_template="/cases/{id}",
        query_builder=fh_case_query,
        row_serializer=fh_case_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("case_number", "Case number", "text"),
            FieldMetadata(
                "status", "Status", "enum",
                enum_values=["first_call", "arranging", "scheduled", "completed", "closed", "cancelled"],
            ),
            FieldMetadata("deceased_first_name", "Decedent first name", "text"),
            FieldMetadata("deceased_last_name", "Decedent last name", "text"),
            FieldMetadata("deceased_date_of_death", "Date of death", "date"),
            FieldMetadata(
                "service_type", "Service type", "enum",
                enum_values=["traditional", "cremation", "memorial", "graveside", "direct"],
            ),
            FieldMetadata("service_date", "Service date", "date"),
            FieldMetadata(
                "disposition_type", "Disposition type", "enum",
                enum_values=["burial", "cremation", "entombment", "other"],
            ),
            FieldMetadata("updated_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "updated_at", "direction": "desc"}],
        default_columns=["case_number", "deceased_last_name", "status", "service_date"],
        # Single-vertical: only funeral homes have FH cases. The
        # canonical example for Pattern A enforcement
        # (BRIDGEABLE_MASTER §3.25 amendment).
        allowed_verticals=["funeral_home"],
    ))

    # sales_order ────────────────────────────────────────────────────
    def sales_order_query(db: Session, company_id: str):
        from app.models.sales_order import SalesOrder

        return db.query(SalesOrder).filter(
            SalesOrder.company_id == company_id,
        )

    def sales_order_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "order_date": _iso_dt(row.order_date),
            "customer_id": row.customer_id,
            "ship_to_name": row.ship_to_name,
            "total": float(row.total) if row.total is not None else 0.0,
            "created_at": _iso_dt(row.created_at),
            "modified_at": _iso_dt(row.modified_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="sales_order",
        display_name="Sales Orders",
        icon="ShoppingCart",
        navigate_url_template="/orders/{id}",
        query_builder=sales_order_query,
        row_serializer=sales_order_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("number", "Order #", "text"),
            FieldMetadata(
                "status", "Status", "enum",
                enum_values=["draft", "confirmed", "scheduled", "in_production", "delivered", "cancelled"],
            ),
            FieldMetadata("customer_id", "Customer", "relation", relation_entity="customer"),
            FieldMetadata("ship_to_name", "Ship-to", "text"),
            FieldMetadata("total", "Total", "currency"),
            FieldMetadata("order_date", "Order date", "datetime"),
            FieldMetadata("modified_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "modified_at", "direction": "desc"}],
        default_columns=["number", "status", "ship_to_name", "total", "order_date"],
        # Cross-vertical: every tenant has sales orders.
        allowed_verticals=["*"],
    ))

    # invoice ───────────────────────────────────────────────────────
    def invoice_query(db: Session, company_id: str):
        from app.models.invoice import Invoice

        return db.query(Invoice).filter(
            Invoice.company_id == company_id,
        )

    def invoice_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "customer_id": row.customer_id,
            "invoice_date": _iso_date(row.invoice_date),
            "due_date": _iso_date(row.due_date),
            "total": float(row.total) if row.total is not None else 0.0,
            "amount_paid": float(row.amount_paid) if row.amount_paid is not None else 0.0,
            "created_at": _iso_dt(row.created_at),
            "modified_at": _iso_dt(row.modified_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="invoice",
        display_name="Invoices",
        icon="Receipt",
        navigate_url_template="/ar/invoices/{id}",
        query_builder=invoice_query,
        row_serializer=invoice_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("number", "Invoice #", "text"),
            FieldMetadata(
                "status", "Status", "enum",
                enum_values=["draft", "sent", "viewed", "paid", "overdue", "cancelled"],
            ),
            FieldMetadata("customer_id", "Customer", "relation", relation_entity="customer"),
            FieldMetadata("total", "Total", "currency"),
            FieldMetadata("amount_paid", "Amount paid", "currency"),
            FieldMetadata("invoice_date", "Invoice date", "date"),
            FieldMetadata("due_date", "Due date", "date"),
            FieldMetadata("modified_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "invoice_date", "direction": "desc"}],
        default_columns=["number", "status", "total", "invoice_date", "due_date"],
        # Cross-vertical: every tenant invoices.
        allowed_verticals=["*"],
    ))

    # contact ───────────────────────────────────────────────────────
    def contact_query(db: Session, company_id: str):
        from app.models.contact import Contact

        return db.query(Contact).filter(
            Contact.company_id == company_id,
            Contact.is_active.is_(True),
        )

    def contact_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "title": row.title,
            "email": row.email,
            "master_company_id": row.master_company_id,
            "updated_at": _iso_dt(row.updated_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="contact",
        display_name="Contacts",
        icon="User",
        navigate_url_template="/vault/crm/companies/{master_company_id}",
        query_builder=contact_query,
        row_serializer=contact_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("name", "Name", "text"),
            FieldMetadata("title", "Title", "text"),
            FieldMetadata("email", "Email", "text"),
            FieldMetadata("master_company_id", "Company", "relation", relation_entity="company_entity"),
            FieldMetadata("updated_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "updated_at", "direction": "desc"}],
        default_columns=["name", "title", "email"],
        # Cross-vertical: every tenant's CRM has contacts.
        allowed_verticals=["*"],
    ))

    # product ───────────────────────────────────────────────────────
    def product_query(db: Session, company_id: str):
        from app.models.product import Product

        return db.query(Product).filter(
            Product.company_id == company_id,
            Product.is_active.is_(True),
        )

    def product_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "updated_at": _iso_dt(row.updated_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="product",
        display_name="Products",
        icon="Package",
        navigate_url_template="/products/{id}",
        query_builder=product_query,
        row_serializer=product_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("name", "Name", "text"),
            FieldMetadata("sku", "SKU", "text"),
            FieldMetadata("updated_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "name", "direction": "asc"}],
        default_columns=["name", "sku"],
        # Cross-vertical: every tenant has products (material catalogs
        # vary by vertical but all have a product table).
        allowed_verticals=["*"],
    ))

    # document ──────────────────────────────────────────────────────
    def document_query(db: Session, company_id: str):
        from app.models.canonical_document import Document

        return db.query(Document).filter(
            Document.company_id == company_id,
        )

    def document_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "document_type": row.document_type,
            "status": row.status,
            "created_at": _iso_dt(row.created_at),
            "updated_at": _iso_dt(row.updated_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="document",
        display_name="Documents",
        icon="FileText",
        navigate_url_template="/vault/documents/{id}",
        query_builder=document_query,
        row_serializer=document_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("title", "Title", "text"),
            FieldMetadata("document_type", "Document type", "text"),
            FieldMetadata("status", "Status", "enum", enum_values=["draft", "final", "archived"]),
            FieldMetadata("updated_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "updated_at", "direction": "desc"}],
        default_columns=["title", "document_type", "status", "updated_at"],
        # Cross-vertical: documents (V-1d canonical Document model)
        # are platform infrastructure shared across every vertical.
        allowed_verticals=["*"],
    ))

    # vault_item ────────────────────────────────────────────────────
    # The generic fallback — any VaultItem the tenant has access to.
    # Excludes saved_view rows so a saved-view-of-all-vault-items
    # doesn't include itself + every other saved view.
    def vault_item_query(db: Session, company_id: str):
        from app.models.vault_item import VaultItem

        return db.query(VaultItem).filter(
            VaultItem.company_id == company_id,
            VaultItem.is_active.is_(True),
            VaultItem.item_type != "saved_view",
        )

    def vault_item_serialize(row: Any) -> dict:
        return {
            "id": row.id,
            "item_type": row.item_type,
            "title": row.title,
            "description": row.description,
            "event_start": _iso_dt(row.event_start),
            "event_end": _iso_dt(row.event_end),
            "event_type": row.event_type,
            "status": row.status,
            "related_entity_type": row.related_entity_type,
            "related_entity_id": row.related_entity_id,
            "created_at": _iso_dt(row.created_at),
            "updated_at": _iso_dt(row.updated_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="vault_item",
        display_name="Vault items",
        icon="Vault",
        navigate_url_template="/vault/items/{id}",
        query_builder=vault_item_query,
        row_serializer=vault_item_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata(
                "item_type", "Type", "enum",
                enum_values=[
                    "document", "event", "communication", "reminder",
                    "order", "quote", "case", "contact",
                    "asset", "compliance_item", "production_record",
                ],
            ),
            FieldMetadata("title", "Title", "text"),
            FieldMetadata("event_start", "Event start", "datetime"),
            FieldMetadata("event_end", "Event end", "datetime"),
            FieldMetadata("event_type", "Event type", "text"),
            FieldMetadata(
                "status", "Status", "enum",
                enum_values=["active", "completed", "cancelled", "expired"],
            ),
            FieldMetadata("updated_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "updated_at", "direction": "desc"}],
        default_columns=["title", "item_type", "status", "updated_at"],
        # Cross-vertical: Vault is platform infrastructure (V-1c+).
        # Every tenant has a vault and vault_items spanning the
        # platform's polymorphic surface (events, communications,
        # reminders, etc.).
        allowed_verticals=["*"],
    ))

    # delivery ──────────────────────────────────────────────────────
    # Phase B Session 1 — dispatcher-role saved views need delivery as
    # a first-class entity. Surfaces the three-panel-scheduling-board
    # data (kanban / ancillary / direct_ship) through one entity type;
    # filters narrow the view.
    def delivery_query(db: Session, company_id: str):
        from app.models.delivery import Delivery

        return db.query(Delivery).filter(Delivery.company_id == company_id)

    def delivery_serialize(row: Any) -> dict:
        # Pull enrichment from type_config JSONB (populated at render
        # by the scheduling board's kanban serializer). Present with
        # null-safety so saved views work even on deliveries without
        # enriched type_config.
        tc = row.type_config or {}
        return {
            "id": row.id,
            "order_id": row.order_id,
            "customer_id": row.customer_id,
            "delivery_type": row.delivery_type,
            "status": row.status,
            "priority": row.priority,
            "requested_date": _iso_date(row.requested_date),
            "scheduled_at": _iso_dt(row.scheduled_at),
            "completed_at": _iso_dt(row.completed_at),
            "scheduling_type": row.scheduling_type,
            "ancillary_fulfillment_status": row.ancillary_fulfillment_status,
            "direct_ship_status": row.direct_ship_status,
            "primary_assignee_id": row.primary_assignee_id,
            "hole_dug_status": row.hole_dug_status,
            "family_name": tc.get("family_name"),
            "cemetery_name": tc.get("cemetery_name"),
            "funeral_home_name": tc.get("funeral_home_name"),
            "service_time": tc.get("service_time"),
            "vault_type": tc.get("vault_type"),
            "created_at": _iso_dt(row.created_at),
            "modified_at": _iso_dt(row.modified_at),
        }

    register_entity(EntityTypeMetadata(
        entity_type="delivery",
        display_name="Deliveries",
        icon="Truck",
        navigate_url_template="/delivery/deliveries/{id}",
        query_builder=delivery_query,
        row_serializer=delivery_serialize,
        available_fields=[
            FieldMetadata("id", "ID", "text", filterable=False, groupable=False, hidden_by_default=True),
            FieldMetadata("delivery_type", "Type", "text"),
            FieldMetadata(
                "status", "Status", "enum",
                enum_values=[
                    "pending", "scheduled", "in_transit", "arrived",
                    "setup", "completed", "cancelled", "failed",
                ],
            ),
            FieldMetadata(
                "priority", "Priority", "enum",
                enum_values=["low", "normal", "high", "urgent"],
            ),
            FieldMetadata("requested_date", "Requested date", "date"),
            FieldMetadata(
                "scheduling_type", "Scheduling bucket", "enum",
                enum_values=["kanban", "ancillary", "direct_ship"],
            ),
            FieldMetadata(
                "ancillary_fulfillment_status",
                "Ancillary status",
                "enum",
                enum_values=[
                    "unassigned", "awaiting_pickup", "assigned_to_driver",
                    "picked_up", "delivered", "completed",
                ],
            ),
            FieldMetadata(
                "direct_ship_status", "Direct-ship status", "enum",
                enum_values=[
                    "pending", "ordered_from_wilbert", "shipped", "done",
                ],
            ),
            FieldMetadata(
                "hole_dug_status", "Hole dug", "enum",
                enum_values=["unknown", "yes", "no"],
            ),
            # Phase 4.3.2 (r56) — renamed from assigned_driver_id; FK
            # to users.id. `relation_entity="user"` reflects the
            # underlying tenant-user identity.
            FieldMetadata("primary_assignee_id", "Primary assignee", "relation", relation_entity="user"),
            FieldMetadata("modified_at", "Last updated", "datetime", groupable=False),
        ],
        default_sort=[{"field": "requested_date", "direction": "asc"}],
        default_columns=[
            "requested_date",
            "scheduling_type",
            "status",
            "hole_dug_status",
            "primary_assignee_id",
        ],
        # Cross-vertical: the Delivery model serves any vertical that
        # ships physical artifacts. Today the surfaced fields lean
        # mfg (hole_dug_status, scheduling_type kanban/ancillary/
        # direct_ship); future per-vertical query builders may filter
        # the field set further. Pattern A only constrains
        # entity_type, not which fields render — fine to keep this
        # cross-vertical at the entity level.
        allowed_verticals=["*"],
    ))


# ── Helpers ──────────────────────────────────────────────────────────


def _iso_date(v: Any) -> str | None:
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else (v if v is None else str(v))


def _iso_dt(v: Any) -> str | None:
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else (v if v is None else str(v))

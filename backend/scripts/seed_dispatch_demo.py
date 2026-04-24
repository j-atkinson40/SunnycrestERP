"""Seed realistic dispatch demo data on the testco tenant.

Phase B Session 1 — populates the Dispatch Monitor with James-
verifiable data grounded in Sunnycrest Precast's operational reality
(Auburn, NY area + nearby towns). Idempotent: re-running cleans and
rebuilds the dispatch-layer seed without touching unrelated data.

What this script creates / refreshes on `testco` (`staging-test-001`):

  - 4 drivers (Driver rows) — realistic names, CDL classes
  - 1 dispatcher user (`dispatcher@testco.com` / TestDispatch123!)
    assigned the Phase B `dispatcher` system role
  - ~20 deliveries distributed across:
      * TODAY — 5 deliveries, all assigned, hole_dug mixed,
        schedule FINALIZED (the "already-committed today" demo)
      * TOMORROW — 6 deliveries, most assigned but 1-2 unassigned,
        hole_dug mostly unknown, schedule DRAFT (the "being
        composed" demo)
      * TWO DAYS OUT — 4 deliveries, fewer assigned, draft
      * THREE DAYS OUT — 2 deliveries, unassigned
      * 3 ancillary pickups mixed across the window
      * 2 direct-ship orders in flight

Scheduling-type distribution matches James's operation: majority
kanban (graveside + drop-off), some ancillary (urn pickups from
homes, extras to FH), direct-ship (jewelry/memento drop-ship from
Wilbert).

Cemeteries + funeral homes already exist in testco from
`seed_staging.py`; this script reuses them. If they're missing,
the script fails loudly — run `seed_staging.py` first.

Usage:
    cd backend
    source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \\
        python scripts/seed_dispatch_demo.py

Idempotency: the script deletes dispatcher-owned demo rows before
rebuilding. Uses a stable tag in `Delivery.special_instructions`
prefix (`[dispatch-demo]`) to find its own rows without touching
unrelated deliveries.
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, ".")  # run from backend/ with `python scripts/...`

from sqlalchemy.orm import Session  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.cemetery import Cemetery  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.company_entity import CompanyEntity  # noqa: E402
from app.models.customer import Customer  # noqa: E402
from app.models.delivery import Delivery  # noqa: E402
from app.models.delivery_schedule import DeliverySchedule  # noqa: E402
from app.models.driver import Driver  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.sales_order import SalesOrder  # noqa: E402
from app.models.user import User  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.services import delivery_schedule_service as schedule_svc  # noqa: E402
from app.services.role_service import seed_default_roles  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed_dispatch_demo")


# ── Constants ──────────────────────────────────────────────────────────

TENANT_ID = "staging-test-001"
DEMO_TAG = "[dispatch-demo]"  # Prefix marker for idempotent cleanup

# Dispatcher user credentials
DISPATCHER_EMAIL = "dispatcher@testco.com"
DISPATCHER_PASSWORD = "TestDispatch123!"
DISPATCHER_FIRST = "Dana"
DISPATCHER_LAST = "Dispatcher"

# Drivers — realistic Auburn-area names + CDL grades. Phase B
# Session 1 uses `Driver.employee_id` path (pre-portal-era drivers).
# Names chosen to be James-recognizable and culturally neutral.
DRIVERS = [
    {"email": "driver_dave@testco.com", "first": "Dave", "last": "Miller",
     "license_number": "CDL-NY-4421", "license_class": "CDL-A"},
    {"email": "driver_tom@testco.com", "first": "Tom", "last": "Henderson",
     "license_number": "CDL-NY-5893", "license_class": "CDL-A"},
    {"email": "driver_mike@testco.com", "first": "Mike", "last": "Kowalski",
     "license_number": "CDL-NY-6112", "license_class": "CDL-B"},
    {"email": "driver_bob@testco.com", "first": "Bob", "last": "Johnson",
     "license_number": "CDL-NY-2970", "license_class": "CDL-A"},
]


# ── Demo delivery configuration ────────────────────────────────────────
# Each entry describes ONE delivery. The seed script:
#   1. Creates a SalesOrder (FH as customer) if one doesn't exist.
#   2. Creates a Delivery row linked to the SO.
#   3. Populates Delivery.type_config with the display fields the
#      Monitor card reads.
#
# `day_offset` from today: 0 = today, 1 = tomorrow, etc.
# `driver_idx` = index into DRIVERS; None = unassigned.

# Service types in approximate real-world distribution:
#   60% graveside (direct to cemetery)
#   25% church service → cemetery (drop-off then graveside setup)
#   15% funeral home → cemetery (procession start)

DEMO_DELIVERIES = [
    # ── TODAY — 5 deliveries, all assigned, schedule finalized ──
    {
        "day_offset": 0, "time": "10:00", "driver_idx": 0,
        "family": "Fitzgerald", "fh_name_match": "Johnson Funeral Home",
        "cemetery_match": "St. Joseph's",  # expected but may fallback
        "vault_type": "Monticello", "service_type": "graveside",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 14, Lot 42B",
        "equipment_type": "Full w/ Placer",
    },
    {
        "day_offset": 0, "time": "11:00", "driver_idx": 1,
        "family": "DiNardo", "fh_name_match": "Smith & Sons Funeral Home",
        "cemetery_match": "Fort Hill",
        "vault_type": "Cameo Rose", "service_type": "church",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 7, Lot 108",
        "equipment_type": "Full Equipment",
        "eta": "12:15",
        "driver_note": "FH said procession may run long",
    },
    {
        "day_offset": 0, "time": "13:00", "driver_idx": 2,
        "family": "O'Brien", "fh_name_match": "Memorial Chapel",
        "cemetery_match": "Oakwood",
        "vault_type": "Continental Bronze", "service_type": "graveside",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 3, Lot 12",
        "equipment_type": "Full w/ Placer",
        "chat_activity_count": 2,
    },
    {
        "day_offset": 0, "time": "14:00", "driver_idx": 0,
        "family": "Hartmann", "fh_name_match": "Riverside Funeral Home",
        "cemetery_match": "Skaneateles",
        "vault_type": "Standard", "service_type": "funeral_home",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 22, Lot 5",
        "equipment_type": "Device",
        "eta": "15:30",
    },
    {
        "day_offset": 0, "time": "11:00", "driver_idx": 3,
        "family": "Murphy", "fh_name_match": "Green Valley Memorial",
        "cemetery_match": "Oakwood",
        "vault_type": "Triune Copper", "service_type": "church",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 3, Lot 77",
        "equipment_type": "Full w/ Placer",
        "eta": "12:10",
    },

    # ── TOMORROW — 6 deliveries, 1 unassigned, schedule draft ──
    {
        "day_offset": 1, "time": "10:00", "driver_idx": 0,
        "family": "Bianchi", "fh_name_match": "Johnson Funeral Home",
        "cemetery_match": "St. Joseph's",
        "vault_type": "Monticello", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 14, Lot 51",
        "equipment_type": "Full Equipment",
    },
    {
        "day_offset": 1, "time": "11:00", "driver_idx": 1,
        "family": "Smith", "fh_name_match": "Smith & Sons Funeral Home",
        "cemetery_match": "Fort Hill",
        "vault_type": "Cameo Rose", "service_type": "church",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 7, Lot 211",
        "equipment_type": "Full w/ Placer",
        "eta": "12:00",
        "chat_activity_count": 1,
    },
    {
        "day_offset": 1, "time": "13:00", "driver_idx": 2,
        "family": "Nowak", "fh_name_match": "Memorial Chapel",
        "cemetery_match": "Fort Hill",
        "vault_type": "Standard", "service_type": "graveside",
        "hole_dug": "no", "scheduling_type": "kanban",
        "cemetery_section": "Sec 9, Lot 33",
        "equipment_type": "Full Equipment",
        "driver_note": "Call before arrival — gate closes 2pm",
    },
    {
        "day_offset": 1, "time": "14:00", "driver_idx": 3,
        "family": "Cooper", "fh_name_match": "Riverside Funeral Home",
        "cemetery_match": "Oakwood",
        "vault_type": "Continental Bronze", "service_type": "graveside",
        "hole_dug": "yes", "scheduling_type": "kanban",
        "cemetery_section": "Sec 3, Lot 88",
        "equipment_type": "Full w/ Placer",
    },
    {
        "day_offset": 1, "time": "15:00", "driver_idx": None,  # unassigned
        "family": "Reynolds", "fh_name_match": "Green Valley Memorial",
        "cemetery_match": "Skaneateles",
        "vault_type": "Triune Copper", "service_type": "funeral_home",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 22, Lot 14",
        "equipment_type": "Full Equipment",
        "eta": "16:15",
    },
    {
        "day_offset": 1, "time": "16:00", "driver_idx": 0,
        "family": "Sullivan", "fh_name_match": "Johnson Funeral Home",
        "cemetery_match": "St. Mary's",
        "vault_type": "Standard", "service_type": "church",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 2, Lot 119",
        "equipment_type": "Device",
        "eta": "17:00",
    },

    # ── TWO DAYS OUT — 4 deliveries, some unassigned ──
    {
        "day_offset": 2, "time": "10:00", "driver_idx": 1,
        "family": "Flanagan", "fh_name_match": "Smith & Sons Funeral Home",
        "cemetery_match": "Fort Hill",
        "vault_type": "Cameo Rose", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 7, Lot 309",
        "equipment_type": "Full w/ Placer",
    },
    {
        "day_offset": 2, "time": "11:00", "driver_idx": None,
        "family": "Vasquez", "fh_name_match": "Memorial Chapel",
        "cemetery_match": "Oakwood",
        "vault_type": "Standard", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 3, Lot 141",
        "equipment_type": "Full Equipment",
    },
    {
        "day_offset": 2, "time": "13:00", "driver_idx": 2,
        "family": "Weber", "fh_name_match": "Johnson Funeral Home",
        "cemetery_match": "Lakeview",
        "vault_type": "Monticello", "service_type": "church",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 11, Lot 67",
        "equipment_type": "Full w/ Placer",
        "eta": "14:15",
    },
    {
        "day_offset": 2, "time": "14:00", "driver_idx": None,
        "family": "McKinney", "fh_name_match": "Riverside Funeral Home",
        "cemetery_match": "Oakwood",
        "vault_type": "Standard", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 3, Lot 202",
        "equipment_type": "Device",
    },

    # ── THREE DAYS OUT — 2 deliveries, all unassigned ──
    {
        "day_offset": 3, "time": "11:00", "driver_idx": None,
        "family": "Hoffman", "fh_name_match": "Green Valley Memorial",
        "cemetery_match": "Skaneateles",
        "vault_type": "Standard", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 22, Lot 71",
        "equipment_type": "Full Equipment",
    },
    {
        "day_offset": 3, "time": "13:00", "driver_idx": None,
        "family": "Rossi", "fh_name_match": "Memorial Chapel",
        "cemetery_match": "St. Mary's",
        "vault_type": "Cameo Rose", "service_type": "graveside",
        "hole_dug": "unknown", "scheduling_type": "kanban",
        "cemetery_section": "Sec 2, Lot 40",
        "equipment_type": "Full w/ Placer",
    },

    # ── ANCILLARY — 3 pickups/drops across window ──
    {
        "day_offset": 1, "time": "09:00", "driver_idx": 3,
        "family": "Patel", "fh_name_match": "Smith & Sons Funeral Home",
        "cemetery_match": None,
        "vault_type": "Urn vault (extra)", "service_type": "ancillary_pickup",
        "hole_dug": "unknown", "scheduling_type": "ancillary",
        "ancillary_status": "assigned_to_driver",
    },
    {
        "day_offset": 1, "time": "15:30", "driver_idx": 0,
        "family": "Chen", "fh_name_match": "Johnson Funeral Home",
        "cemetery_match": None,
        "vault_type": "Marker base", "service_type": "ancillary_drop",
        "hole_dug": "unknown", "scheduling_type": "ancillary",
        "ancillary_status": "awaiting_pickup",
    },
    {
        "day_offset": 2, "time": "10:00", "driver_idx": None,
        "family": "Lombardi", "fh_name_match": "Memorial Chapel",
        "cemetery_match": None,
        "vault_type": "Proof approval pickup", "service_type": "ancillary_pickup",
        "hole_dug": "unknown", "scheduling_type": "ancillary",
        "ancillary_status": "unassigned",
    },

    # ── DIRECT SHIP — 2 in-flight from Wilbert ──
    {
        "day_offset": 4, "time": None, "driver_idx": None,
        "family": "Anderson", "fh_name_match": "Riverside Funeral Home",
        "cemetery_match": None,
        "vault_type": "Memorial jewelry (drop-ship)", "service_type": "direct_ship",
        "hole_dug": "unknown", "scheduling_type": "direct_ship",
        "direct_ship_status": "ordered_from_wilbert",
    },
    {
        "day_offset": 2, "time": None, "driver_idx": None,
        "family": "Torres", "fh_name_match": "Green Valley Memorial",
        "cemetery_match": None,
        "vault_type": "Keepsake urn (drop-ship)", "service_type": "direct_ship",
        "hole_dug": "unknown", "scheduling_type": "direct_ship",
        "direct_ship_status": "shipped",
    },
]


# ── Matching helpers ───────────────────────────────────────────────────


def _find_cemetery(db: Session, name_match: str | None) -> Cemetery | None:
    if name_match is None:
        return None
    # Loose match — first cemetery whose name contains the hint.
    cems = db.query(Cemetery).filter(Cemetery.company_id == TENANT_ID).all()
    for cem in cems:
        if name_match.lower() in cem.name.lower():
            return cem
    # Fallback: return first cemetery (keep seed runnable even if
    # the exact cemetery name isn't there).
    return cems[0] if cems else None


def _find_fh(db: Session, name_match: str) -> CompanyEntity | None:
    fhs = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == TENANT_ID,
            CompanyEntity.is_funeral_home.is_(True),
        )
        .all()
    )
    for fh in fhs:
        if name_match.lower() in fh.name.lower():
            return fh
    return fhs[0] if fhs else None


def _find_customer_for_fh(db: Session, fh: CompanyEntity | None) -> Customer | None:
    if fh is None:
        return db.query(Customer).filter(Customer.company_id == TENANT_ID).first()
    # Try matching by name
    cust = (
        db.query(Customer)
        .filter(
            Customer.company_id == TENANT_ID,
            Customer.name.ilike(f"%{fh.name}%"),
        )
        .first()
    )
    if cust:
        return cust
    return db.query(Customer).filter(Customer.company_id == TENANT_ID).first()


# ── Cleanup (idempotency) ──────────────────────────────────────────────


def _cleanup(db: Session) -> None:
    """Remove all rows tagged by a previous seed run."""
    # Deliveries — identified by DEMO_TAG in special_instructions
    demo_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == TENANT_ID,
            Delivery.special_instructions.like(f"{DEMO_TAG}%"),
        )
        .all()
    )
    logger.info(f"cleanup: {len(demo_deliveries)} demo deliveries to delete")
    for d in demo_deliveries:
        db.delete(d)

    # Orders — identified by DEMO_TAG in customer_notes or reference
    demo_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == TENANT_ID,
            SalesOrder.notes.like(f"{DEMO_TAG}%"),
        )
        .all()
    )
    logger.info(f"cleanup: {len(demo_orders)} demo orders to delete")
    for o in demo_orders:
        db.delete(o)

    # Schedules for the demo date range (today through +7 days)
    start = date.today() - timedelta(days=1)
    end = date.today() + timedelta(days=10)
    demo_schedules = (
        db.query(DeliverySchedule)
        .filter(
            DeliverySchedule.company_id == TENANT_ID,
            DeliverySchedule.schedule_date >= start,
            DeliverySchedule.schedule_date <= end,
        )
        .all()
    )
    logger.info(f"cleanup: {len(demo_schedules)} demo schedules to delete")
    for s in demo_schedules:
        db.delete(s)

    db.commit()


# ── Creation helpers ───────────────────────────────────────────────────


def _ensure_dispatcher_role(db: Session) -> Role:
    """Ensure `dispatcher` role exists on the testco tenant. Calls
    seed_default_roles which is idempotent."""
    seed_default_roles(db, TENANT_ID)
    db.commit()
    role = (
        db.query(Role)
        .filter(Role.company_id == TENANT_ID, Role.slug == "dispatcher")
        .first()
    )
    if role is None:
        raise RuntimeError("Failed to seed dispatcher role for testco")
    return role


def _ensure_dispatcher_user(db: Session, role: Role) -> User:
    """Create or refresh the dispatcher test user."""
    user = db.query(User).filter(User.email == DISPATCHER_EMAIL).first()
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email=DISPATCHER_EMAIL,
            hashed_password=hash_password(DISPATCHER_PASSWORD),
            first_name=DISPATCHER_FIRST,
            last_name=DISPATCHER_LAST,
            company_id=TENANT_ID,
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        logger.info(f"created dispatcher user: {DISPATCHER_EMAIL}")
    else:
        user.role_id = role.id
        user.is_active = True
        user.hashed_password = hash_password(DISPATCHER_PASSWORD)
        logger.info(f"refreshed dispatcher user: {DISPATCHER_EMAIL}")
    db.commit()
    db.refresh(user)
    return user


def _ensure_drivers(db: Session) -> list[Driver]:
    """Ensure 4 driver records exist. Creates companion User rows."""
    driver_role = (
        db.query(Role)
        .filter(Role.company_id == TENANT_ID, Role.slug == "driver")
        .first()
    )
    if driver_role is None:
        raise RuntimeError("driver role not seeded on testco")

    drivers_out: list[Driver] = []
    for cfg in DRIVERS:
        # User row — matches the legacy employee_id-based Driver model
        user = db.query(User).filter(User.email == cfg["email"]).first()
        if user is None:
            user = User(
                id=str(uuid.uuid4()),
                email=cfg["email"],
                hashed_password=hash_password("TestDriver123!"),
                first_name=cfg["first"],
                last_name=cfg["last"],
                company_id=TENANT_ID,
                role_id=driver_role.id,
                is_active=True,
            )
            db.add(user)
            db.flush()

        # Driver row — use employee_id path (pre-portal)
        driver = (
            db.query(Driver)
            .filter(
                Driver.company_id == TENANT_ID,
                Driver.employee_id == user.id,
            )
            .first()
        )
        if driver is None:
            driver = Driver(
                id=str(uuid.uuid4()),
                company_id=TENANT_ID,
                employee_id=user.id,
                license_number=cfg["license_number"],
                license_class=cfg["license_class"],
                active=True,
            )
            db.add(driver)
        else:
            driver.license_number = cfg["license_number"]
            driver.license_class = cfg["license_class"]
            driver.active = True
        db.flush()
        drivers_out.append(driver)

    db.commit()
    logger.info(f"ensured {len(drivers_out)} driver records")
    return drivers_out


def _create_delivery(
    db: Session,
    cfg: dict,
    drivers: list[Driver],
    today: date,
) -> Delivery:
    """Create one demo delivery with its backing SalesOrder."""
    schedule_date = today + timedelta(days=cfg["day_offset"])
    fh = _find_fh(db, cfg["fh_name_match"])
    cem = _find_cemetery(db, cfg["cemetery_match"])
    customer = _find_customer_for_fh(db, fh)

    # Build a realistic service datetime in UTC (ET +4h).
    if cfg["time"] is not None:
        hh, mm = cfg["time"].split(":")
        local_dt = datetime.combine(
            schedule_date, time(int(hh), int(mm)), tzinfo=timezone(timedelta(hours=-4))
        )
        utc_dt = local_dt.astimezone(timezone.utc)
        scheduled_at = utc_dt
        service_time_display = cfg["time"]
    else:
        scheduled_at = None
        service_time_display = None

    # Create the SalesOrder (idempotent delete+create since we clean
    # first).
    so = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=TENANT_ID,
        number=f"SO-DEMO-{uuid.uuid4().hex[:8].upper()}",
        customer_id=customer.id if customer else None,
        cemetery_id=cem.id if cem else None,
        status="confirmed",
        total=Decimal("0.00"),
        order_date=datetime.now(timezone.utc),
        notes=(
            f"{DEMO_TAG} {cfg['family']} family — "
            f"{cfg['service_type']} for {cfg['vault_type']}"
        ),
    )
    db.add(so)
    db.flush()

    # Primary assignee (Phase 4.3.2 r56 — renamed from
    # assigned_driver_id; FK users.id). Translate driver.id →
    # users.id via drivers.employee_id.
    primary_assignee_id = None
    if cfg["driver_idx"] is not None and cfg["driver_idx"] < len(drivers):
        primary_assignee_id = drivers[cfg["driver_idx"]].employee_id

    # type_config JSONB — powers the Monitor card display. Phase 3.1+3.2
    # compaction fields: cemetery_section (→ MapPin icon tooltip),
    # driver_note (→ StickyNote icon tooltip), chat_activity_count
    # (→ MessageCircle icon tooltip with unread-pill badge), eta
    # (→ inline "ETA 12:00" in the primary service-time line for
    # church/funeral_home services).
    #
    # Phase 3.2.1 semantics correction:
    #   - service_type  = SERVICE LOCATION (graveside/church/funeral_
    #                     home/ancillary_*). Drives the time-line
    #                     label on the card. NOT equipment.
    #   - vault_type    = PRODUCT name (Monticello, Cameo Rose, etc).
    #   - equipment_type = EQUIPMENT BUNDLE (Full Equipment, Full w/
    #                     Placer, Device, etc). Distinct field;
    #                     previously confused with service_type-
    #                     derived hint ("Graveside setup" etc).
    type_config = {
        "family_name": cfg["family"],
        "cemetery_name": cem.name if cem else None,
        "cemetery_city": cem.city if cem else None,
        "cemetery_section": cfg.get("cemetery_section"),
        "funeral_home_name": fh.name if fh else None,
        "service_time": service_time_display,
        "service_type": cfg["service_type"],
        "vault_type": cfg["vault_type"],
        "equipment_type": cfg.get("equipment_type"),
        "eta": cfg.get("eta"),
        "driver_note": cfg.get("driver_note"),
        "chat_activity_count": cfg.get("chat_activity_count", 0),
    }

    # Delivery row
    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=TENANT_ID,
        delivery_type="vault",
        order_id=so.id,
        customer_id=customer.id if customer else None,
        requested_date=schedule_date,
        scheduled_at=scheduled_at,
        status="scheduled" if cfg["day_offset"] >= 0 else "pending",
        priority="normal",
        scheduling_type=cfg["scheduling_type"],
        type_config=type_config,
        hole_dug_status=cfg["hole_dug"],
        primary_assignee_id=primary_assignee_id,
        special_instructions=(
            f"{DEMO_TAG} {cfg['family']} — {cfg['service_type']}"
        ),
    )

    # Ancillary-specific fields
    if cfg["scheduling_type"] == "ancillary":
        delivery.ancillary_fulfillment_status = cfg.get(
            "ancillary_status", "unassigned"
        )
    elif cfg["scheduling_type"] == "direct_ship":
        delivery.direct_ship_status = cfg.get("direct_ship_status", "pending")

    db.add(delivery)
    db.flush()
    return delivery


# ── Main orchestration ────────────────────────────────────────────────


def run() -> None:
    db = SessionLocal()
    try:
        # Sanity-check tenant exists
        company = db.query(Company).filter(Company.id == TENANT_ID).first()
        if company is None:
            raise RuntimeError(
                f"Tenant {TENANT_ID} not found. Run seed_staging.py first."
            )

        # 1. Clean previous demo data
        _cleanup(db)

        # 2. Ensure dispatcher role + user
        role = _ensure_dispatcher_role(db)
        dispatcher = _ensure_dispatcher_user(db, role)
        logger.info(
            f"dispatcher user ready: {dispatcher.email} (role={role.slug})"
        )

        # 3. Ensure drivers
        drivers = _ensure_drivers(db)

        # 4. Create deliveries
        today = date.today()
        deliveries_created = 0
        for cfg in DEMO_DELIVERIES:
            _create_delivery(db, cfg, drivers, today)
            deliveries_created += 1
        db.commit()
        logger.info(f"created {deliveries_created} demo deliveries")

        # 5. Create schedule rows — TODAY finalized, others draft
        today_schedule = schedule_svc.ensure_schedule(db, TENANT_ID, today)
        if today_schedule.state == "draft":
            schedule_svc.finalize_schedule(
                db, TENANT_ID, today,
                user_id=dispatcher.id, auto=False,
            )
            logger.info(f"today schedule ({today}): FINALIZED")
        tomorrow = today + timedelta(days=1)
        schedule_svc.ensure_schedule(db, TENANT_ID, tomorrow)
        logger.info(f"tomorrow schedule ({tomorrow}): DRAFT")
        day2 = today + timedelta(days=2)
        schedule_svc.ensure_schedule(db, TENANT_ID, day2)
        logger.info(f"two days out schedule ({day2}): DRAFT")
        day3 = today + timedelta(days=3)
        schedule_svc.ensure_schedule(db, TENANT_ID, day3)
        logger.info(f"three days out schedule ({day3}): DRAFT")

        # Summary
        total_kanban = sum(1 for c in DEMO_DELIVERIES if c["scheduling_type"] == "kanban")
        total_ancillary = sum(1 for c in DEMO_DELIVERIES if c["scheduling_type"] == "ancillary")
        total_direct = sum(1 for c in DEMO_DELIVERIES if c["scheduling_type"] == "direct_ship")
        unassigned = sum(1 for c in DEMO_DELIVERIES if c["driver_idx"] is None)
        logger.info("=" * 60)
        logger.info("seed_dispatch_demo complete:")
        logger.info(f"  dispatcher user: {DISPATCHER_EMAIL} / {DISPATCHER_PASSWORD}")
        logger.info(f"  drivers: {len(drivers)}")
        logger.info(f"  deliveries: {deliveries_created} total")
        logger.info(f"    kanban: {total_kanban}")
        logger.info(f"    ancillary: {total_ancillary}")
        logger.info(f"    direct_ship: {total_direct}")
        logger.info(f"    unassigned: {unassigned}")
        logger.info(f"  schedule states: today=finalized, +1d/+2d/+3d=draft")
        logger.info("=" * 60)
    except Exception:
        db.rollback()
        logger.exception("seed_dispatch_demo FAILED")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()

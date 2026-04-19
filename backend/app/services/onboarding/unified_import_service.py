"""Unified import orchestrator — cross-references all data sources for onboarding.

Coordinates Sage/QBO/CSV imports, order history, cemetery/FH CSVs into staging,
then cross-references, classifies, clusters duplicates, and applies to real tables.
"""

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.import_staging_company import ImportStagingCompany
from app.models.unified_import_session import UnifiedImportSession
from app.services.onboarding.cluster_service import cluster_duplicates

logger = logging.getLogger(__name__)

# ── Zip-to-state lookup (first 2 digits → state) ──────────────────
_ZIP_STATE_MAP = {
    "01": "MA", "02": "MA", "03": "NH", "04": "ME", "05": "VT", "06": "CT",
    "07": "NJ", "08": "NJ", "10": "NY", "11": "NY", "12": "NY", "13": "NY",
    "14": "NY", "15": "PA", "16": "PA", "17": "PA", "18": "PA", "19": "PA",
    "20": "DC", "21": "MD", "22": "VA", "23": "VA", "24": "WV", "25": "WV",
    "26": "WV", "27": "NC", "28": "NC", "29": "SC", "30": "GA", "31": "GA",
    "32": "FL", "33": "FL", "34": "FL", "35": "AL", "36": "AL", "37": "TN",
    "38": "TN", "39": "MS", "40": "KY", "41": "KY", "42": "KY", "43": "OH",
    "44": "OH", "45": "OH", "46": "IN", "47": "IN", "48": "MI", "49": "MI",
    "50": "IA", "51": "IA", "52": "IA", "53": "WI", "54": "WI", "55": "MN",
    "56": "MN", "57": "SD", "58": "ND", "59": "MT", "60": "IL", "61": "IL",
    "62": "IL", "63": "MO", "64": "MO", "65": "MO", "66": "KS", "67": "KS",
    "68": "NE", "69": "NE", "70": "LA", "71": "LA", "72": "AR", "73": "OK",
    "74": "OK", "75": "TX", "76": "TX", "77": "TX", "78": "TX", "79": "TX",
    "80": "CO", "81": "CO", "82": "WY", "83": "ID", "84": "UT", "85": "AZ",
    "86": "AZ", "87": "NM", "88": "NM", "89": "NV", "90": "CA", "91": "CA",
    "92": "CA", "93": "CA", "94": "CA", "95": "CA", "96": "HI", "97": "OR",
    "98": "WA", "99": "AK",
}


# ── Session management ─────────────────────────────────────────────

def get_or_create_session(db: Session, tenant_id: str) -> UnifiedImportSession:
    """Get existing session or create a new one for tenant."""
    session = (
        db.query(UnifiedImportSession)
        .filter(UnifiedImportSession.tenant_id == tenant_id)
        .first()
    )
    if session:
        return session
    session = UnifiedImportSession(tenant_id=tenant_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, tenant_id: str) -> UnifiedImportSession | None:
    """Get existing session for tenant."""
    return (
        db.query(UnifiedImportSession)
        .filter(UnifiedImportSession.tenant_id == tenant_id)
        .first()
    )


def reset_session(db: Session, tenant_id: str) -> UnifiedImportSession:
    """Delete existing session and staging data, create fresh."""
    existing = get_session(db, tenant_id)
    if existing:
        db.delete(existing)
        db.commit()
    return get_or_create_session(db, tenant_id)


# ── Source ingestion into staging ──────────────────────────────────

def ingest_accounting_customers(
    db: Session,
    session: UnifiedImportSession,
    parsed_customers: list[dict],
) -> int:
    """Ingest Sage/QBO/CSV customer data into staging."""
    # Clear prior accounting staging rows
    db.query(ImportStagingCompany).filter(
        ImportStagingCompany.session_id == session.id,
        ImportStagingCompany.source_type == "accounting",
    ).delete()

    count = 0
    for i, cust in enumerate(parsed_customers):
        row = ImportStagingCompany(
            session_id=session.id,
            source_type="accounting",
            source_row_id=cust.get("sage_customer_no") or cust.get("account_number") or str(i),
            raw_data=cust,
            name=cust.get("name"),
            address=None,
            city=None,
            state=None,
            zip=cust.get("zip"),
            phone=cust.get("phone"),
            email=cust.get("email"),
            sage_customer_id=cust.get("sage_customer_no") or cust.get("sage_customer_id"),
            account_number=cust.get("account_number"),
            suggested_type=cust.get("customer_type"),
        )
        db.add(row)
        count += 1

    session.accounting_status = "uploaded"
    session.staging_customers_count = count
    db.commit()
    return count


def ingest_csv_source(
    db: Session,
    session: UnifiedImportSession,
    source_type: str,  # "cemetery_csv" | "fh_csv"
    rows: list[dict],
    field_map: dict[str, str],
) -> int:
    """Ingest a mapped CSV (cemetery or funeral home) into staging."""
    # Clear prior rows of this source type
    db.query(ImportStagingCompany).filter(
        ImportStagingCompany.session_id == session.id,
        ImportStagingCompany.source_type == source_type,
    ).delete()

    default_type = "cemetery" if source_type == "cemetery_csv" else "funeral_home"
    reverse_map = {v: k for k, v in field_map.items()}

    count = 0
    for i, row in enumerate(rows):
        mapped = {}
        for col_name, value in row.items():
            std_field = reverse_map.get(col_name)
            if std_field:
                mapped[std_field] = value

        name = mapped.get("name", "").strip()
        if not name:
            continue

        staging = ImportStagingCompany(
            session_id=session.id,
            source_type=source_type,
            source_row_id=str(i),
            raw_data=row,
            name=name,
            address=mapped.get("address"),
            city=mapped.get("city"),
            state=mapped.get("state"),
            zip=mapped.get("zip"),
            phone=mapped.get("phone"),
            email=mapped.get("email"),
            website=mapped.get("website"),
            contact_name=mapped.get("contact_name") or mapped.get("director_name"),
            notes=mapped.get("notes"),
            suggested_type=default_type,
            classification_confidence=0.80 if source_type == "cemetery_csv" else 0.75,
        )
        db.add(staging)
        count += 1

    if source_type == "cemetery_csv":
        session.cemetery_csv_status = "uploaded"
        session.staging_cemeteries_count = count
    else:
        session.funeral_home_csv_status = "uploaded"
        session.staging_funeral_homes_count = count

    db.commit()
    return count


def ingest_order_history_signals(
    db: Session,
    session: UnifiedImportSession,
    tenant_id: str,
) -> int:
    """Pull order history signals into staging rows.

    Reads from historical_orders table (already imported via existing flow)
    and creates staging rows for any companies found in orders that don't
    already exist in accounting staging.
    """
    from app.models.historical_order_import import HistoricalOrder

    # Get unique funeral homes and cemeteries from order history
    fh_counts = (
        db.query(
            HistoricalOrder.raw_funeral_home,
            func.count().label("order_count"),
        )
        .filter(
            HistoricalOrder.company_id == tenant_id,
            HistoricalOrder.raw_funeral_home.isnot(None),
        )
        .group_by(HistoricalOrder.raw_funeral_home)
        .all()
    )

    cem_counts = (
        db.query(
            HistoricalOrder.raw_cemetery,
            func.count().label("order_count"),
        )
        .filter(
            HistoricalOrder.company_id == tenant_id,
            HistoricalOrder.raw_cemetery.isnot(None),
        )
        .group_by(HistoricalOrder.raw_cemetery)
        .all()
    )

    # Get existing staging names for cross-referencing
    existing_names = {
        (r.name or "").lower().strip()
        for r in db.query(ImportStagingCompany.name).filter(
            ImportStagingCompany.session_id == session.id,
        ).all()
    }

    count = 0

    # Add funeral homes from order history not already in staging
    for raw_name, order_count in fh_counts:
        name = raw_name.strip()
        if not name or name.lower() in existing_names:
            # Will cross-reference later, but skip creating new staging row
            continue
        staging = ImportStagingCompany(
            session_id=session.id,
            source_type="order_history",
            source_row_id=f"fh:{name}",
            name=name,
            suggested_type="funeral_home",
            order_count=order_count,
            classification_confidence=0.60,
        )
        db.add(staging)
        existing_names.add(name.lower())
        count += 1

    # Add cemeteries from order history not already in staging
    for raw_name, order_count in cem_counts:
        name = raw_name.strip()
        if not name or name.lower() in existing_names:
            continue
        staging = ImportStagingCompany(
            session_id=session.id,
            source_type="order_history",
            source_row_id=f"cem:{name}",
            name=name,
            suggested_type="cemetery",
            appears_as_cemetery_count=order_count,
            classification_confidence=0.65,
        )
        db.add(staging)
        existing_names.add(name.lower())
        count += 1

    session.order_history_status = "uploaded"
    session.staging_orders_count = count
    db.commit()
    return count


# ── Cross-referencing and classification ───────────────────────────

def _infer_state_from_zip(zip_code: str | None) -> str | None:
    """Basic zip prefix → state lookup."""
    if not zip_code:
        return None
    z = zip_code.strip()[:2]
    return _ZIP_STATE_MAP.get(z)


def _name_sim(a: str, b: str) -> float:
    """Quick SequenceMatcher ratio."""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _cross_reference_order_history(
    db: Session,
    session_id: str,
    tenant_id: str,
) -> None:
    """Enrich staging rows with order history stats."""
    from app.models.historical_order_import import HistoricalOrder

    staging_rows = (
        db.query(ImportStagingCompany)
        .filter(ImportStagingCompany.session_id == session_id)
        .all()
    )

    if not staging_rows:
        return

    # Build order history lookup
    fh_counts: dict[str, int] = {}
    cem_counts: dict[str, int] = {}

    for raw_name, cnt in (
        db.query(HistoricalOrder.raw_funeral_home, func.count())
        .filter(
            HistoricalOrder.company_id == tenant_id,
            HistoricalOrder.raw_funeral_home.isnot(None),
        )
        .group_by(HistoricalOrder.raw_funeral_home)
        .all()
    ):
        fh_counts[raw_name.lower().strip()] = cnt

    for raw_name, cnt in (
        db.query(HistoricalOrder.raw_cemetery, func.count())
        .filter(
            HistoricalOrder.company_id == tenant_id,
            HistoricalOrder.raw_cemetery.isnot(None),
        )
        .group_by(HistoricalOrder.raw_cemetery)
        .all()
    ):
        cem_counts[raw_name.lower().strip()] = cnt

    for row in staging_rows:
        if not row.name:
            continue
        name_lower = row.name.lower().strip()

        # Fuzzy match against order history names
        best_fh_count = 0
        for oh_name, cnt in fh_counts.items():
            if _name_sim(name_lower, oh_name) > 0.80:
                best_fh_count = max(best_fh_count, cnt)

        best_cem_count = 0
        for oh_name, cnt in cem_counts.items():
            if _name_sim(name_lower, oh_name) > 0.80:
                best_cem_count = max(best_cem_count, cnt)

        if best_fh_count > 0:
            row.order_count = max(row.order_count or 0, best_fh_count)
        if best_cem_count > 0:
            row.appears_as_cemetery_count = max(row.appears_as_cemetery_count or 0, best_cem_count)


def _cross_reference_sources(
    db: Session,
    session_id: str,
) -> None:
    """Cross-reference staging rows across sources to merge data and boost confidence."""
    rows = (
        db.query(ImportStagingCompany)
        .filter(ImportStagingCompany.session_id == session_id)
        .all()
    )

    # Group by source type
    by_source: dict[str, list[ImportStagingCompany]] = {}
    for r in rows:
        by_source.setdefault(r.source_type, []).append(r)

    accounting_rows = by_source.get("accounting", [])
    cemetery_rows = by_source.get("cemetery_csv", [])
    fh_rows = by_source.get("fh_csv", [])

    # Cross-ref accounting against cemetery CSV
    for acct in accounting_rows:
        if not acct.name:
            continue

        for cem in cemetery_rows:
            if not cem.name:
                continue
            sim = _name_sim(acct.name, cem.name)
            city_ok = (
                not acct.city
                or not cem.city
                or acct.city.lower().strip() == cem.city.lower().strip()
            )
            if sim > 0.70 and city_ok:
                # Merge: cemetery CSV has better address data
                matched = list(acct.matched_sources or [])
                matched.append("cemetery_csv")
                acct.matched_sources = matched
                if cem.city and not acct.city:
                    acct.city = cem.city
                if cem.state and not acct.state:
                    acct.state = cem.state
                if cem.address and not acct.address:
                    acct.address = cem.address
                if cem.phone and not acct.phone:
                    acct.phone = cem.phone

        # Cross-ref accounting against FH CSV
        for fh in fh_rows:
            if not fh.name:
                continue
            sim = _name_sim(acct.name, fh.name)
            city_ok = (
                not acct.city
                or not fh.city
                or acct.city.lower().strip() == fh.city.lower().strip()
            )
            if sim > 0.70 and city_ok:
                matched = list(acct.matched_sources or [])
                matched.append("fh_csv")
                acct.matched_sources = matched
                if fh.city and not acct.city:
                    acct.city = fh.city
                if fh.state and not acct.state:
                    acct.state = fh.state
                if fh.phone and not acct.phone:
                    acct.phone = fh.phone
                if fh.contact_name and not acct.contact_name:
                    acct.contact_name = fh.contact_name


def _classify_with_signals(
    db: Session,
    session_id: str,
) -> None:
    """Classify staging rows using all available signals."""
    # Resolve tenant_id from the session so _classify_batch_ai can populate
    # company_id on the intelligence_executions row.
    session = db.query(UnifiedImportSession).filter_by(id=session_id).first()
    tenant_id = session.tenant_id if session else None

    rows = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.review_status == "pending",
        )
        .all()
    )

    # ── Phase 1: rule-based high-confidence ────────────────────────
    needs_ai: list[ImportStagingCompany] = []

    for row in rows:
        signals = {
            "name": row.name,
            "order_count": row.order_count or 0,
            "appears_as_cemetery_count": row.appears_as_cemetery_count or 0,
            "matched_sources": row.matched_sources or [],
            "current_suggested_type": row.suggested_type,
            "source_type": row.source_type,
        }
        row.classification_signals = signals

        # Strong signal: appears as cemetery in orders
        if (row.appears_as_cemetery_count or 0) >= 2:
            row.suggested_type = "cemetery"
            row.classification_confidence = float(Decimal("0.95"))
            row.cross_ref_confidence = float(Decimal("0.95"))
            continue

        # Strong signal: matched cemetery CSV
        if "cemetery_csv" in (row.matched_sources or []):
            row.suggested_type = "cemetery"
            row.classification_confidence = float(Decimal("0.90"))
            row.cross_ref_confidence = float(Decimal("0.90"))
            continue

        # Strong signal: matched FH CSV + has vault orders
        if "fh_csv" in (row.matched_sources or []):
            row.suggested_type = "funeral_home"
            row.classification_confidence = float(Decimal("0.90"))
            row.cross_ref_confidence = float(Decimal("0.90"))
            continue

        # Strong signal: many orders = funeral home
        if (row.order_count or 0) >= 3:
            row.suggested_type = "funeral_home"
            row.classification_confidence = float(Decimal("0.85"))
            row.cross_ref_confidence = float(Decimal("0.85"))
            continue

        # Source-based defaults with lower confidence
        if row.source_type == "cemetery_csv":
            row.suggested_type = "cemetery"
            row.classification_confidence = float(Decimal("0.80"))
            row.cross_ref_confidence = float(Decimal("0.80"))
            continue

        if row.source_type == "fh_csv":
            row.suggested_type = "funeral_home"
            row.classification_confidence = float(Decimal("0.75"))
            row.cross_ref_confidence = float(Decimal("0.75"))
            continue

        # Try name-based rules
        from app.services.customer_classification_service import classify_by_name

        result = classify_by_name(row.name or "")
        if result["confidence"] >= 0.75:
            row.suggested_type = result["customer_type"]
            row.classification_confidence = result["confidence"]
            row.cross_ref_confidence = result["confidence"]
            continue

        # Needs AI classification
        needs_ai.append(row)

    # ── Phase 2: AI batch classification ───────────────────────────
    if needs_ai:
        _classify_batch_ai(needs_ai, db=db, tenant_id=tenant_id)

    db.flush()


def _classify_batch_ai(
    rows: list[ImportStagingCompany],
    *,
    db=None,
    tenant_id: str | None = None,
) -> None:
    """Phase 2c-4 — managed onboarding.classify_import_companies prompt."""
    from app.services.intelligence import intelligence_service

    if db is None:
        from app.database import SessionLocal
        db = SessionLocal()
        _owns_db = True
    else:
        _owns_db = False

    BATCH_SIZE = 40

    try:
        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start: batch_start + BATCH_SIZE]
            companies_data = []
            for row in batch:
                companies_data.append({
                    "id": row.id,
                    "name": row.name,
                    "city": row.city,
                    "state": row.state,
                    "order_count": row.order_count or 0,
                    "appears_as_cemetery": row.appears_as_cemetery_count or 0,
                    "matched_sources": row.matched_sources or [],
                })

            try:
                import json as _json

                intel = intelligence_service.execute(
                    db,
                    prompt_key="onboarding.classify_import_companies",
                    variables={"companies_data": _json.dumps(companies_data)},
                    company_id=tenant_id,
                    caller_module="onboarding.unified_import_service._classify_batch_ai",
                    caller_entity_type=None,
                )
                result = intel.response_parsed if intel.status == "success" else None

                if isinstance(result, list):
                    result_map = {r.get("id"): r for r in result if isinstance(r, dict)}
                elif isinstance(result, dict) and "classifications" in result:
                    result_map = {r.get("id"): r for r in result["classifications"] if isinstance(r, dict)}
                else:
                    logger.warning("Unexpected AI classification response format")
                result_map = {}

            for row in batch:
                ai = result_map.get(row.id)
                if ai:
                    row.suggested_type = ai.get("customer_type", "unknown")
                    row.suggested_contractor_type = ai.get("contractor_type")
                    conf = ai.get("confidence", 0.5)
                    row.classification_confidence = float(Decimal(str(conf)))
                    row.cross_ref_confidence = float(Decimal(str(conf)))
                else:
                    row.suggested_type = row.suggested_type or "unknown"
                    row.classification_confidence = float(Decimal("0.3"))

        except Exception:
            logger.exception("AI classification batch failed")
            for row in batch:
                row.suggested_type = row.suggested_type or "unknown"
                row.classification_confidence = float(Decimal("0.3"))


# ── Main processing orchestrator ───────────────────────────────────

def process_all_sources(db: Session, session_id: str) -> dict:
    """Cross-reference all sources, classify, and cluster.

    Returns processing summary.
    """
    session = db.query(UnifiedImportSession).get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session.phase = "processing"
    db.commit()

    try:
        # Step 1: Geography enrichment
        _enrich_geography(db, session_id)

        # Step 2: Cross-reference order history
        if session.order_history_status in ("uploaded", "processed"):
            _cross_reference_order_history(db, session_id, session.tenant_id)

        # Step 3: Cross-reference across sources
        _cross_reference_sources(db, session_id)

        # Step 4: Classify with all signals
        _classify_with_signals(db, session_id)

        # Step 5: Cluster duplicates
        cluster_result = cluster_duplicates(db, session_id)

        # Step 6: Auto-apply high confidence
        auto_count = _auto_apply_high_confidence(db, session_id)

        # Step 7: Build summary
        summary = _build_processing_summary(db, session_id, cluster_result, auto_count)
        session.processing_summary = summary
        session.phase = "review"
        db.commit()

        return summary

    except Exception as e:
        logger.exception("Processing failed for session %s", session_id)
        session.phase = "error"
        session.processing_error = str(e)
        db.commit()
        raise


def _enrich_geography(db: Session, session_id: str) -> None:
    """Fill in missing state from zip codes."""
    rows = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.state.is_(None),
            ImportStagingCompany.zip.isnot(None),
        )
        .all()
    )
    for row in rows:
        inferred = _infer_state_from_zip(row.zip)
        if inferred:
            row.state = inferred
    db.flush()


def _auto_apply_high_confidence(db: Session, session_id: str) -> int:
    """Mark high-confidence non-clustered rows as auto_applied."""
    rows = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.review_status == "pending",
        )
        .all()
    )
    count = 0
    for row in rows:
        conf = float(row.cross_ref_confidence or row.classification_confidence or 0)
        in_cluster = row.cluster_id is not None

        if conf >= 0.90 and not in_cluster:
            row.review_status = "auto_applied"
            count += 1
        elif in_cluster and row.is_cluster_primary and conf >= 0.90:
            # Cluster primary with high confidence — still needs cluster review
            pass  # Keep as pending for cluster decision

    db.flush()
    return count


def _build_processing_summary(
    db: Session,
    session_id: str,
    cluster_result: dict,
    auto_applied: int,
) -> dict:
    """Build summary stats for the processing phase."""
    all_rows = (
        db.query(ImportStagingCompany)
        .filter(ImportStagingCompany.session_id == session_id)
        .all()
    )

    by_type: dict[str, int] = {}
    pending = 0
    for row in all_rows:
        t = row.suggested_type or "unknown"
        by_type[t] = by_type.get(t, 0) + 1
        if row.review_status == "pending":
            pending += 1

    sources_used = set()
    for row in all_rows:
        sources_used.add(row.source_type)

    return {
        "total_records": len(all_rows),
        "auto_applied": auto_applied,
        "needs_review": pending,
        "clusters_found": cluster_result.get("clusters_found", 0),
        "total_records_in_clusters": cluster_result.get("total_records_in_clusters", 0),
        "by_type": by_type,
        "sources_used": sorted(sources_used),
    }


# ── Review operations ──────────────────────────────────────────────

def get_review_data(db: Session, session_id: str) -> dict:
    """Get review queue: clusters and classification groups."""
    rows = (
        db.query(ImportStagingCompany)
        .filter(ImportStagingCompany.session_id == session_id)
        .all()
    )

    # Build clusters
    clusters_map: dict[str, list[dict]] = {}
    classification_pending: list[dict] = []
    auto_applied_count = 0

    for row in rows:
        row_data = _serialize_staging(row)

        if row.review_status == "auto_applied":
            auto_applied_count += 1
            continue

        if row.cluster_id:
            if row.cluster_id not in clusters_map:
                clusters_map[row.cluster_id] = []
            clusters_map[row.cluster_id].append(row_data)
        elif row.review_status == "pending":
            classification_pending.append(row_data)

    # Group classification pending by suggested_type for bulk review
    bulk_groups: dict[str, list[dict]] = {}
    for item in classification_pending:
        key = item.get("suggested_type") or "unknown"
        if key not in bulk_groups:
            bulk_groups[key] = []
        bulk_groups[key].append(item)

    clusters = []
    for cluster_id, members in clusters_map.items():
        members.sort(key=lambda m: (-1 if m.get("is_cluster_primary") else 0, -(m.get("order_count") or 0)))
        clusters.append({
            "cluster_id": cluster_id,
            "members": members,
            "suggested_primary_id": next((m["id"] for m in members if m.get("is_cluster_primary")), None),
        })

    classification_groups = []
    for type_key, items in bulk_groups.items():
        classification_groups.append({
            "suggested_type": type_key,
            "count": len(items),
            "examples": items[:5],
            "all_ids": [i["id"] for i in items],
        })

    return {
        "clusters": clusters,
        "bulk_classification_groups": classification_groups,
        "auto_applied_count": auto_applied_count,
        "pending_count": len(classification_pending),
        "cluster_count": len(clusters),
    }


def merge_cluster(db: Session, session_id: str, cluster_id: str, primary_id: str) -> dict:
    """Resolve a cluster by marking one record as primary, others as rejected."""
    members = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.cluster_id == cluster_id,
        )
        .all()
    )
    if not members:
        raise ValueError(f"Cluster {cluster_id} not found")

    primary = None
    for m in members:
        if m.id == primary_id:
            m.is_cluster_primary = True
            m.review_status = "approved"
            primary = m
        else:
            m.is_cluster_primary = False
            m.review_status = "rejected"

    if not primary:
        raise ValueError(f"Primary {primary_id} not in cluster")

    # Merge data from rejected into primary
    for m in members:
        if m.id == primary_id:
            continue
        if m.city and not primary.city:
            primary.city = m.city
        if m.state and not primary.state:
            primary.state = m.state
        if m.address and not primary.address:
            primary.address = m.address
        if m.phone and not primary.phone:
            primary.phone = m.phone
        if m.email and not primary.email:
            primary.email = m.email
        if m.contact_name and not primary.contact_name:
            primary.contact_name = m.contact_name
        # Accumulate order counts
        primary.order_count = (primary.order_count or 0) + (m.order_count or 0)
        primary.appears_as_cemetery_count = (
            (primary.appears_as_cemetery_count or 0) + (m.appears_as_cemetery_count or 0)
        )

    db.commit()
    return {"cluster_id": cluster_id, "primary_id": primary_id, "merged_count": len(members) - 1}


def split_cluster(db: Session, session_id: str, cluster_id: str) -> dict:
    """Mark cluster members as intentionally separate."""
    members = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.cluster_id == cluster_id,
        )
        .all()
    )
    for m in members:
        m.cluster_id = None
        m.is_cluster_primary = False
        m.review_status = "approved"
    db.commit()
    return {"cluster_id": cluster_id, "split_count": len(members)}


def bulk_classify(
    db: Session,
    session_id: str,
    staging_ids: list[str],
    customer_type: str,
    contractor_type: str | None = None,
) -> dict:
    """Bulk-approve a classification for multiple staging rows."""
    rows = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session_id,
            ImportStagingCompany.id.in_(staging_ids),
        )
        .all()
    )
    for row in rows:
        row.reviewed_classification = customer_type
        row.suggested_type = customer_type
        row.suggested_contractor_type = contractor_type
        row.review_status = "approved"
    db.commit()
    return {"classified_count": len(rows), "customer_type": customer_type}


# ── Apply to real tables ───────────────────────────────────────────

def apply_all(db: Session, session_id: str, actor_id: str) -> dict:
    """Write approved/auto-applied staging records to real tables.

    Returns final apply summary.
    """
    session = db.query(UnifiedImportSession).get(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session.phase = "applying"
    db.commit()

    try:
        from app.models.cemetery import Cemetery
        from app.models.company_entity import CompanyEntity
        from app.models.contact import Contact
        from app.models.customer import Customer

        tenant_id = session.tenant_id
        rows = (
            db.query(ImportStagingCompany)
            .filter(
                ImportStagingCompany.session_id == session_id,
                ImportStagingCompany.review_status.in_(["auto_applied", "approved"]),
            )
            .all()
        )

        # Dedup: skip cluster non-primaries
        final_rows = []
        for row in rows:
            if row.cluster_id and not row.is_cluster_primary:
                continue
            final_rows.append(row)

        counts = {
            "customers_created": 0,
            "cemeteries_created": 0,
            "company_entities_created": 0,
            "contacts_created": 0,
            "duplicates_merged": 0,
            "skipped": 0,
            "by_type": {},
        }

        for row in final_rows:
            final_type = row.reviewed_classification or row.suggested_type or "unknown"
            counts["by_type"][final_type] = counts["by_type"].get(final_type, 0) + 1

            try:
                with db.begin_nested():
                    # Check for existing customer by sage_customer_id or name
                    existing_customer = None
                    if row.sage_customer_id:
                        existing_customer = (
                            db.query(Customer)
                            .filter(
                                Customer.company_id == tenant_id,
                                Customer.sage_customer_id == row.sage_customer_id,
                            )
                            .first()
                        )
                    if not existing_customer and row.name:
                        existing_customer = (
                            db.query(Customer)
                            .filter(
                                Customer.company_id == tenant_id,
                                func.lower(Customer.name) == row.name.lower().strip(),
                            )
                            .first()
                        )

                    if existing_customer:
                        # Update classification on existing
                        existing_customer.customer_type = final_type
                        if row.city and not existing_customer.city:
                            existing_customer.city = row.city
                        if row.phone and not existing_customer.phone:
                            existing_customer.phone = row.phone
                        existing_customer.classification_confidence = float(
                            row.cross_ref_confidence or row.classification_confidence or 0
                        )
                        existing_customer.classification_method = "unified_import"
                        counts["skipped"] += 1
                        continue

                    # Create new customer
                    customer = Customer(
                        company_id=tenant_id,
                        name=row.name or "Unknown",
                        customer_type=final_type,
                        phone=row.phone,
                        email=row.email,
                        zip_code=row.zip,
                        city=row.city,
                        state=row.state,
                        sage_customer_id=row.sage_customer_id,
                        account_number=row.account_number,
                        classification_confidence=float(
                            row.cross_ref_confidence or row.classification_confidence or 0
                        ),
                        classification_method="unified_import",
                        notes=row.notes,
                    )
                    db.add(customer)
                    counts["customers_created"] += 1

                    # Create CompanyEntity
                    ce = CompanyEntity(
                        company_id=tenant_id,
                        name=row.name or "Unknown",
                        phone=row.phone,
                        email=row.email,
                        city=row.city,
                        state=row.state,
                        zip=row.zip,
                        address_line1=row.address,
                        customer_type=final_type,
                        is_customer=final_type in ("funeral_home", "contractor", "individual"),
                        is_funeral_home=final_type == "funeral_home",
                        is_cemetery=final_type == "cemetery",
                    )
                    db.add(ce)
                    counts["company_entities_created"] += 1

                    # Create Cemetery record if cemetery type
                    if final_type == "cemetery":
                        cem = Cemetery(
                            company_id=tenant_id,
                            name=row.name or "Unknown",
                            city=row.city,
                            state=row.state,
                            zip_code=row.zip,
                            phone=row.phone,
                            address=row.address,
                            equipment_note=row.notes,
                        )
                        db.add(cem)
                        counts["cemeteries_created"] += 1

                    # Create contact if we have a contact name
                    if row.contact_name:
                        contact = Contact(
                            company_id=tenant_id,
                            name=row.contact_name,
                            phone=row.phone,
                            email=row.email,
                        )
                        db.add(contact)
                        counts["contacts_created"] += 1

            except Exception:
                logger.exception("Failed to apply staging row %s", row.id)
                counts["skipped"] += 1

        # Count merged duplicates
        merged = (
            db.query(ImportStagingCompany)
            .filter(
                ImportStagingCompany.session_id == session_id,
                ImportStagingCompany.review_status == "rejected",
            )
            .count()
        )
        counts["duplicates_merged"] = merged

        session.phase = "complete"
        session.apply_summary = counts
        db.commit()

        # Auto-complete onboarding steps
        try:
            from app.services.onboarding_service import check_completion

            # Always complete these — unified import replaces them
            check_completion(db, tenant_id, "data_migration")
            check_completion(db, tenant_id, "import_order_history")
            check_completion(db, tenant_id, "review_customer_types")

            # Complete setup_cemeteries if cemeteries were imported
            if counts.get("cemeteries_created", 0) > 0:
                check_completion(db, tenant_id, "setup_cemeteries")

            # Complete add_products if products already exist (seeded or imported)
            from app.models.product import Product

            product_count = (
                db.query(func.count(Product.id))
                .filter(Product.company_id == tenant_id, Product.is_active == True)
                .scalar()
            )
            if product_count and product_count > 0:
                check_completion(db, tenant_id, "add_products")
        except Exception:
            logger.exception("Failed to auto-complete onboarding steps after import")

        return counts

    except Exception as e:
        logger.exception("Apply failed for session %s", session_id)
        session.phase = "error"
        session.processing_error = str(e)
        db.commit()
        raise


# ── Serialization ──────────────────────────────────────────────────

def _serialize_staging(row: ImportStagingCompany) -> dict:
    """Serialize a staging row for API response."""
    return {
        "id": row.id,
        "source_type": row.source_type,
        "name": row.name,
        "address": row.address,
        "city": row.city,
        "state": row.state,
        "zip": row.zip,
        "phone": row.phone,
        "email": row.email,
        "contact_name": row.contact_name,
        "suggested_type": row.suggested_type,
        "suggested_contractor_type": row.suggested_contractor_type,
        "classification_confidence": float(row.classification_confidence) if row.classification_confidence else None,
        "cross_ref_confidence": float(row.cross_ref_confidence) if row.cross_ref_confidence else None,
        "matched_sources": row.matched_sources or [],
        "cluster_id": row.cluster_id,
        "is_cluster_primary": row.is_cluster_primary,
        "review_status": row.review_status,
        "order_count": row.order_count or 0,
        "appears_as_cemetery_count": row.appears_as_cemetery_count or 0,
        "notes": row.notes,
    }


def serialize_session(session: UnifiedImportSession) -> dict:
    """Serialize session for API response."""
    return {
        "id": session.id,
        "tenant_id": session.tenant_id,
        "phase": session.phase,
        "accounting_source": session.accounting_source,
        "accounting_status": session.accounting_status,
        "order_history_status": session.order_history_status,
        "cemetery_csv_status": session.cemetery_csv_status,
        "funeral_home_csv_status": session.funeral_home_csv_status,
        "processing_summary": session.processing_summary,
        "processing_error": session.processing_error,
        "staging_customers_count": session.staging_customers_count or 0,
        "staging_cemeteries_count": session.staging_cemeteries_count or 0,
        "staging_funeral_homes_count": session.staging_funeral_homes_count or 0,
        "staging_orders_count": session.staging_orders_count or 0,
        "apply_summary": session.apply_summary,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }

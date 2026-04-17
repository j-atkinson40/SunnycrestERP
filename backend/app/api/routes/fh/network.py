"""FH network / connections — active & pending tenant relationships."""

from fastapi import APIRouter, Depends
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User


router = APIRouter()


@router.get("/connections")
def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active and pending connections for the current tenant.

    Uses platform_tenant_relationships. Columns used: tenant_id,
    supplier_tenant_id, relationship_type, status, connected_at.
    """
    rows = db.execute(
        sql_text(
            """
            SELECT id, tenant_id, supplier_tenant_id, relationship_type, status, connected_at
            FROM platform_tenant_relationships
            WHERE tenant_id = :cid OR supplier_tenant_id = :cid
            ORDER BY connected_at DESC NULLS LAST
            """
        ),
        {"cid": current_user.company_id},
    ).fetchall()

    results = []
    for r in rows:
        other_id = r[2] if r[1] == current_user.company_id else r[1]
        other = db.query(Company).filter(Company.id == other_id).first()
        results.append({
            "id": r[0],
            "other_company_id": other_id,
            "other_company_name": other.name if other else "Unknown",
            "other_company_slug": other.slug if other else None,
            "other_vertical": (other.vertical or "").lower() if other else None,
            "relationship_type": r[3],
            "status": r[4],
            "connected_at": r[5].isoformat() if r[5] else None,
            "is_supplier": r[2] != current_user.company_id,   # true if other is the supplier to us
        })

    grouped: dict[str, list] = {"manufacturer": [], "cemetery": [], "crematory": [], "other": []}
    for c in results:
        rtype = (c["relationship_type"] or "").lower()
        if "manufacturer" in rtype or c["other_vertical"] == "manufacturing":
            grouped["manufacturer"].append(c)
        elif "cemetery" in rtype or c["other_vertical"] == "cemetery":
            grouped["cemetery"].append(c)
        elif "crematory" in rtype or c["other_vertical"] == "crematory":
            grouped["crematory"].append(c)
        else:
            grouped["other"].append(c)

    return {"connections": results, "grouped": grouped}

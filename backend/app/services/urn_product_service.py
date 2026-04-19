"""UrnProductService — CRUD and search for urn products."""

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.urn_product import UrnProduct
from app.models.urn_inventory import UrnInventory
from app.schemas.urns import UrnProductCreate, UrnProductUpdate

logger = logging.getLogger(__name__)


class UrnProductService:

    @staticmethod
    def list_products(
        db: Session,
        tenant_id: str,
        source_type: str | None = None,
        material: str | None = None,
        active: bool | None = True,
        discontinued: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UrnProduct]:
        q = (
            db.query(UrnProduct)
            .options(joinedload(UrnProduct.inventory))
            .filter(UrnProduct.tenant_id == tenant_id)
        )
        if source_type:
            q = q.filter(UrnProduct.source_type == source_type)
        if material:
            q = q.filter(UrnProduct.material == material)
        if active is not None:
            q = q.filter(UrnProduct.is_active == active)
        if discontinued is not None:
            q = q.filter(UrnProduct.discontinued == discontinued)
        return q.order_by(UrnProduct.name).offset(offset).limit(limit).all()

    @staticmethod
    def get_product(db: Session, tenant_id: str, product_id: str) -> UrnProduct:
        product = (
            db.query(UrnProduct)
            .options(joinedload(UrnProduct.inventory))
            .filter(
                UrnProduct.id == product_id,
                UrnProduct.tenant_id == tenant_id,
            )
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="Urn product not found")
        return product

    @staticmethod
    def create_product(
        db: Session, tenant_id: str, data: UrnProductCreate,
    ) -> UrnProduct:
        # Enforce: stocked products cannot be engravable
        engravable = data.engravable
        if data.source_type == "stocked":
            engravable = False

        product = UrnProduct(
            tenant_id=tenant_id,
            name=data.name,
            sku=data.sku,
            source_type=data.source_type,
            material=data.material,
            style=data.style,
            available_colors=data.available_colors,
            is_keepsake_set=data.is_keepsake_set,
            companion_skus=data.companion_skus,
            engravable=engravable,
            photo_etch_capable=data.photo_etch_capable,
            available_fonts=data.available_fonts,
            base_cost=data.base_cost,
            retail_price=data.retail_price,
            image_url=data.image_url,
            wilbert_catalog_url=data.wilbert_catalog_url,
        )
        db.add(product)
        db.flush()

        # Create inventory record for stocked products
        if data.source_type == "stocked":
            inv = UrnInventory(
                tenant_id=tenant_id,
                urn_product_id=product.id,
            )
            db.add(inv)
            db.flush()

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def update_product(
        db: Session, tenant_id: str, product_id: str, data: UrnProductUpdate,
    ) -> UrnProduct:
        product = UrnProductService.get_product(db, tenant_id, product_id)

        update_data = data.model_dump(exclude_unset=True)
        # Enforce: stocked products cannot be engravable
        if product.source_type == "stocked" and update_data.get("engravable"):
            update_data["engravable"] = False

        for key, value in update_data.items():
            setattr(product, key, value)

        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def search_products(
        db: Session, tenant_id: str, query: str,
    ) -> list[dict]:
        """Natural language search using Claude via the Intelligence layer.

        Falls back to ILIKE on the raw query if the AI call fails for any
        reason (no API key, parse error, etc.) so search stays functional.
        """
        terms: list[str] = [query]
        try:
            from app.services.intelligence import intelligence_service

            result = intelligence_service.execute(
                db,
                prompt_key="urn.semantic_search",
                variables={"query": query},
                company_id=tenant_id,
                caller_module="urn_product_service.search_products",
                caller_entity_type="urn_product",
            )
            if result.status == "success" and isinstance(result.response_parsed, list):
                # The urn.semantic_search prompt returns a bare JSON array, not an object
                terms = [str(t) for t in result.response_parsed if t] or [query]
        except Exception:
            terms = [query]

        # Build ILIKE query with all terms
        products = (
            db.query(UrnProduct)
            .options(joinedload(UrnProduct.inventory))
            .filter(
                UrnProduct.tenant_id == tenant_id,
                UrnProduct.is_active == True,
                UrnProduct.discontinued == False,
            )
        )

        from sqlalchemy import or_, func
        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.extend([
                UrnProduct.name.ilike(pattern),
                UrnProduct.style.ilike(pattern),
                UrnProduct.material.ilike(pattern),
                UrnProduct.sku.ilike(pattern),
            ])

        if conditions:
            products = products.filter(or_(*conditions))

        results = products.limit(20).all()

        # Score results by relevance
        scored = []
        query_lower = query.lower()
        for p in results:
            score = 0.0
            if p.name and query_lower in p.name.lower():
                score += 1.0
            if p.sku and query_lower in p.sku.lower():
                score += 0.8
            if p.material and query_lower in p.material.lower():
                score += 0.5
            if p.style and query_lower in p.style.lower():
                score += 0.5
            # Availability note
            avail = None
            if p.source_type == "stocked" and p.inventory:
                available = p.inventory.qty_on_hand - p.inventory.qty_reserved
                avail = f"{available} available" if available > 0 else "Out of stock"
            elif p.source_type == "drop_ship":
                avail = "Drop ship from Wilbert"
            scored.append({
                "product": p,
                "match_score": round(max(score, 0.1), 2),
                "availability_note": avail,
            })

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored

"""UrnOrderService — order lifecycle management for urn sales."""

import logging
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.urn_engraving_job import UrnEngravingJob
from app.models.urn_inventory import UrnInventory
from app.models.urn_order import UrnOrder
from app.models.urn_product import UrnProduct
from app.models.urn_tenant_settings import UrnTenantSettings

logger = logging.getLogger(__name__)


class UrnOrderService:

    @staticmethod
    def create_order(
        db: Session,
        tenant_id: str,
        data: dict,
        intake_channel: str = "manual",
        created_by: str | None = None,
    ) -> UrnOrder:
        product = (
            db.query(UrnProduct)
            .filter(UrnProduct.id == data["urn_product_id"], UrnProduct.tenant_id == tenant_id)
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="Urn product not found")

        fulfillment_type = product.source_type

        order = UrnOrder(
            tenant_id=tenant_id,
            funeral_home_id=data.get("funeral_home_id"),
            fh_contact_email=data.get("fh_contact_email"),
            urn_product_id=product.id,
            fulfillment_type=fulfillment_type,
            quantity=data.get("quantity", 1),
            need_by_date=data.get("need_by_date"),
            delivery_method=data.get("delivery_method"),
            intake_channel=intake_channel,
            notes=data.get("notes"),
            status="draft",
            created_by=created_by,
        )
        db.add(order)
        db.flush()

        # Stocked: reserve inventory
        if fulfillment_type == "stocked":
            inv = (
                db.query(UrnInventory)
                .filter(UrnInventory.urn_product_id == product.id)
                .first()
            )
            if inv:
                inv.qty_reserved += data.get("quantity", 1)

        # Drop-ship + engravable: scaffold engraving jobs
        if fulfillment_type == "drop_ship" and product.engravable:
            # Main piece
            main_job = UrnEngravingJob(
                tenant_id=tenant_id,
                urn_order_id=order.id,
                piece_label="main",
            )
            db.add(main_job)

            # Companion pieces if keepsake set
            if product.is_keepsake_set and product.companion_skus:
                for i, _sku in enumerate(product.companion_skus[:3], start=1):
                    companion_job = UrnEngravingJob(
                        tenant_id=tenant_id,
                        urn_order_id=order.id,
                        piece_label=f"companion_{i}",
                    )
                    db.add(companion_job)

            # Apply inline engraving specs if provided
            engraving_specs = data.get("engraving_specs") or []
            if engraving_specs:
                db.flush()  # Ensure jobs have IDs
                jobs = (
                    db.query(UrnEngravingJob)
                    .filter(UrnEngravingJob.urn_order_id == order.id)
                    .all()
                )
                for spec in engraving_specs:
                    target_label = spec.get("piece_label", "main")
                    for job in jobs:
                        if job.piece_label == target_label:
                            for field in [
                                "engraving_line_1", "engraving_line_2",
                                "engraving_line_3", "engraving_line_4",
                                "font_selection", "color_selection",
                            ]:
                                val = spec.get(field)
                                if val is not None:
                                    setattr(job, field, val)

        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def create_draft_from_extraction(
        db: Session,
        tenant_id: str,
        extracted_data: dict,
        intake_channel: str = "email_intake",
    ) -> dict:
        """Create draft order from intake agent / call intelligence extraction.

        Returns dict with order_id and flagged_fields list.
        """
        flagged_fields = []
        confidence = extracted_data.get("confidence_scores", {})

        # Flag low-confidence fields
        for field, score in confidence.items():
            if score < 0.7:
                flagged_fields.append(field)

        # Try to match product
        product_id = extracted_data.get("urn_product_id")
        if not product_id and extracted_data.get("urn_description"):
            from app.services.urn_product_service import UrnProductService
            results = UrnProductService.search_products(
                db, tenant_id, extracted_data["urn_description"],
            )
            if results:
                product_id = results[0]["product"].id
                if results[0]["match_score"] < 0.7:
                    flagged_fields.append("urn_product_id")
            else:
                flagged_fields.append("urn_product_id")

        if not product_id:
            raise HTTPException(
                status_code=400,
                detail="Could not identify urn product from extraction",
            )

        order_data = {
            "funeral_home_id": extracted_data.get("funeral_home_id"),
            "fh_contact_email": extracted_data.get("fh_contact_email"),
            "urn_product_id": product_id,
            "quantity": extracted_data.get("quantity", 1),
            "need_by_date": extracted_data.get("need_by_date"),
            "delivery_method": extracted_data.get("delivery_method"),
            "notes": extracted_data.get("notes"),
        }

        # Add engraving specs if present
        if extracted_data.get("engraving_line_1"):
            order_data["engraving_specs"] = [{
                "piece_label": "main",
                "engraving_line_1": extracted_data.get("engraving_line_1"),
                "engraving_line_2": extracted_data.get("engraving_line_2"),
                "engraving_line_3": extracted_data.get("engraving_line_3"),
                "engraving_line_4": extracted_data.get("engraving_line_4"),
                "font_selection": extracted_data.get("font_selection"),
                "color_selection": extracted_data.get("color_selection"),
            }]

        order = UrnOrderService.create_order(
            db, tenant_id, order_data, intake_channel=intake_channel,
        )
        return {
            "order_id": order.id,
            "flagged_fields": flagged_fields,
            "status": order.status,
        }

    @staticmethod
    def confirm_order(db: Session, tenant_id: str, order_id: str) -> UrnOrder:
        order = UrnOrderService._get_order(db, tenant_id, order_id)
        if order.status != "draft":
            raise HTTPException(status_code=400, detail="Only draft orders can be confirmed")

        # Snapshot pricing
        product = db.query(UrnProduct).filter(UrnProduct.id == order.urn_product_id).first()
        if product:
            order.unit_cost = product.base_cost
            order.unit_retail = product.retail_price

        order.status = "confirmed"
        if order.fulfillment_type == "drop_ship" and product and product.engravable:
            order.status = "engraving_pending"

        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def cancel_order(db: Session, tenant_id: str, order_id: str) -> UrnOrder:
        order = UrnOrderService._get_order(db, tenant_id, order_id)
        if order.status in ("delivered", "cancelled"):
            raise HTTPException(status_code=400, detail="Cannot cancel this order")

        # Release reserved inventory for stocked orders
        if order.fulfillment_type == "stocked":
            inv = (
                db.query(UrnInventory)
                .filter(UrnInventory.urn_product_id == order.urn_product_id)
                .first()
            )
            if inv:
                inv.qty_reserved = max(0, inv.qty_reserved - order.quantity)

        order.status = "cancelled"
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def mark_delivered(db: Session, tenant_id: str, order_id: str) -> UrnOrder:
        order = UrnOrderService._get_order(db, tenant_id, order_id)
        if order.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot deliver cancelled order")

        # Deduct inventory for stocked orders
        if order.fulfillment_type == "stocked":
            inv = (
                db.query(UrnInventory)
                .filter(UrnInventory.urn_product_id == order.urn_product_id)
                .first()
            )
            if inv:
                inv.qty_on_hand = max(0, inv.qty_on_hand - order.quantity)
                inv.qty_reserved = max(0, inv.qty_reserved - order.quantity)

        order.status = "delivered"
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def list_orders(
        db: Session,
        tenant_id: str,
        status_filter: str | None = None,
        funeral_home_id: str | None = None,
        fulfillment_type: str | None = None,
        need_by_start: date | None = None,
        need_by_end: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UrnOrder]:
        q = (
            db.query(UrnOrder)
            .options(
                joinedload(UrnOrder.urn_product),
                joinedload(UrnOrder.funeral_home),
                joinedload(UrnOrder.engraving_jobs),
            )
            .filter(
                UrnOrder.tenant_id == tenant_id,
                UrnOrder.is_active == True,
            )
        )
        if status_filter:
            q = q.filter(UrnOrder.status == status_filter)
        if funeral_home_id:
            q = q.filter(UrnOrder.funeral_home_id == funeral_home_id)
        if fulfillment_type:
            q = q.filter(UrnOrder.fulfillment_type == fulfillment_type)
        if need_by_start:
            q = q.filter(UrnOrder.need_by_date >= need_by_start)
        if need_by_end:
            q = q.filter(UrnOrder.need_by_date <= need_by_end)

        return q.order_by(UrnOrder.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def get_order(db: Session, tenant_id: str, order_id: str) -> UrnOrder:
        return UrnOrderService._get_order(db, tenant_id, order_id)

    @staticmethod
    def search_orders(
        db: Session, tenant_id: str,
        fh_id: str | None = None,
        decedent_name: str | None = None,
    ) -> list[UrnOrder]:
        """Fuzzy lookup for call intelligence status queries."""
        q = (
            db.query(UrnOrder)
            .options(
                joinedload(UrnOrder.urn_product),
                joinedload(UrnOrder.funeral_home),
                joinedload(UrnOrder.engraving_jobs),
            )
            .filter(UrnOrder.tenant_id == tenant_id, UrnOrder.is_active == True)
        )
        if fh_id:
            q = q.filter(UrnOrder.funeral_home_id == fh_id)
        if decedent_name:
            pattern = f"%{decedent_name}%"
            q = q.join(UrnOrder.engraving_jobs).filter(
                UrnEngravingJob.engraving_line_1.ilike(pattern)
            )
        return q.order_by(UrnOrder.created_at.desc()).limit(20).all()

    @staticmethod
    def get_ancillary_items_for_scheduling(
        db: Session, tenant_id: str, reference_date: date,
    ) -> list[UrnOrder]:
        """Stocked orders where need_by_date <= reference_date + window."""
        settings = (
            db.query(UrnTenantSettings)
            .filter(UrnTenantSettings.tenant_id == tenant_id)
            .first()
        )
        window = settings.ancillary_window_days if settings else 3
        cutoff = reference_date + timedelta(days=window)

        return (
            db.query(UrnOrder)
            .options(
                joinedload(UrnOrder.urn_product),
                joinedload(UrnOrder.funeral_home),
            )
            .filter(
                UrnOrder.tenant_id == tenant_id,
                UrnOrder.fulfillment_type == "stocked",
                UrnOrder.need_by_date <= cutoff,
                UrnOrder.status.notin_(["delivered", "cancelled"]),
                UrnOrder.is_active == True,
            )
            .order_by(UrnOrder.need_by_date)
            .all()
        )

    @staticmethod
    def get_drop_ship_visibility_feed(
        db: Session, tenant_id: str,
    ) -> list[UrnOrder]:
        """Open drop-ship orders for scheduling board visibility."""
        return (
            db.query(UrnOrder)
            .options(
                joinedload(UrnOrder.urn_product),
                joinedload(UrnOrder.funeral_home),
            )
            .filter(
                UrnOrder.tenant_id == tenant_id,
                UrnOrder.fulfillment_type == "drop_ship",
                UrnOrder.status.notin_(["delivered", "cancelled", "draft"]),
                UrnOrder.is_active == True,
            )
            .order_by(UrnOrder.expected_arrival_date)
            .all()
        )

    @staticmethod
    def _get_order(db: Session, tenant_id: str, order_id: str) -> UrnOrder:
        order = (
            db.query(UrnOrder)
            .options(
                joinedload(UrnOrder.urn_product),
                joinedload(UrnOrder.funeral_home),
                joinedload(UrnOrder.engraving_jobs),
            )
            .filter(
                UrnOrder.id == order_id,
                UrnOrder.tenant_id == tenant_id,
            )
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="Urn order not found")
        return order

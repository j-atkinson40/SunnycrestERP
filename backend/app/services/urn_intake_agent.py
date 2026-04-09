"""UrnIntakeAgent — processes inbound emails for urn orders and proofs."""

import logging
import re

from sqlalchemy.orm import Session

from app.models.urn_engraving_job import UrnEngravingJob
from app.models.urn_order import UrnOrder

logger = logging.getLogger(__name__)


class UrnIntakeAgent:

    @staticmethod
    def process_intake_email(
        db: Session, tenant_id: str, email_data: dict,
    ) -> dict:
        """Parse inbound email from funeral home for new urn order.

        Uses Claude to extract order details, then creates draft via
        UrnOrderService.create_draft_from_extraction.

        email_data keys: from_email, subject, body_text, body_html, attachments
        Returns dict with order_id, flagged_fields, extraction.
        """
        from app.services.ai_service import call_anthropic

        body = email_data.get("body_text") or email_data.get("body_html", "")
        subject = email_data.get("subject", "")

        prompt = (
            "Extract urn order details from this funeral home email.\n"
            "Return ONLY a JSON object with these fields:\n"
            "- funeral_home_name: string or null\n"
            "- fh_contact_email: string or null\n"
            "- urn_description: string or null (product name, SKU, or description)\n"
            "- quantity: integer (default 1)\n"
            "- engraving_line_1: string or null (decedent name)\n"
            "- engraving_line_2: string or null (dates, e.g. birth-death)\n"
            "- engraving_line_3: string or null\n"
            "- engraving_line_4: string or null\n"
            "- font_selection: string or null\n"
            "- color_selection: string or null\n"
            "- need_by_date: string or null (ISO format)\n"
            "- delivery_method: string or null\n"
            "- notes: string or null\n"
            "- confidence_scores: object mapping field names to 0.0-1.0\n\n"
            f"Subject: {subject}\n\n"
            f"Body:\n{body[:3000]}"
        )

        try:
            import json
            result = call_anthropic(prompt, max_tokens=800)
            extraction = json.loads(result) if result else {}
        except Exception as e:
            logger.error("AI extraction failed for intake email: %s", e)
            extraction = {}

        if not extraction:
            return {"error": "Could not extract order details from email"}

        # Try to match funeral home
        fh_name = extraction.get("funeral_home_name")
        from_email = email_data.get("from_email", "")
        if fh_name:
            extraction["funeral_home_id"] = UrnIntakeAgent._match_funeral_home(
                db, tenant_id, fh_name, from_email,
            )
        if not extraction.get("fh_contact_email") and from_email:
            extraction["fh_contact_email"] = from_email

        from app.services.urn_order_service import UrnOrderService
        try:
            result = UrnOrderService.create_draft_from_extraction(
                db, tenant_id, extraction, intake_channel="email_intake",
            )
            result["extraction"] = extraction
            return result
        except Exception as e:
            logger.error("Failed to create draft from extraction: %s", e)
            return {"error": str(e), "extraction": extraction}

    @staticmethod
    def match_proof_email(
        db: Session, tenant_id: str, email_data: dict,
    ) -> dict:
        """Match an inbound proof email from Wilbert to an existing order.

        Looks for order reference in subject line, then fuzzy match on
        decedent name or SKU.

        Returns dict with matched job_id or error.
        """
        subject = email_data.get("subject", "")
        body = email_data.get("body_text") or email_data.get("body_html", "")

        # Try to extract order reference from subject
        order_ref_match = re.search(r"URN-([a-f0-9]{8})", subject, re.IGNORECASE)
        if order_ref_match:
            order_prefix = order_ref_match.group(1)
            order = (
                db.query(UrnOrder)
                .filter(
                    UrnOrder.tenant_id == tenant_id,
                    UrnOrder.id.like(f"{order_prefix}%"),
                )
                .first()
            )
            if order:
                job = (
                    db.query(UrnEngravingJob)
                    .filter(
                        UrnEngravingJob.urn_order_id == order.id,
                        UrnEngravingJob.piece_label == "main",
                    )
                    .first()
                )
                if job:
                    return {
                        "matched": True,
                        "order_id": order.id,
                        "job_id": job.id,
                        "match_method": "order_reference",
                    }

        # Fuzzy match: extract decedent name from subject/body
        from app.services.ai_service import call_anthropic
        try:
            import json
            prompt = (
                "Extract the decedent name from this proof email from Wilbert.\n"
                "Return ONLY a JSON object: {\"decedent_name\": \"...\"}\n\n"
                f"Subject: {subject}\nBody:\n{body[:1500]}"
            )
            result = call_anthropic(prompt, max_tokens=100)
            parsed = json.loads(result) if result else {}
            decedent = parsed.get("decedent_name")
        except Exception:
            decedent = None

        if decedent:
            pattern = f"%{decedent}%"
            job = (
                db.query(UrnEngravingJob)
                .join(UrnOrder, UrnEngravingJob.urn_order_id == UrnOrder.id)
                .filter(
                    UrnOrder.tenant_id == tenant_id,
                    UrnOrder.status.in_(["proof_pending", "engraving_pending"]),
                    UrnEngravingJob.engraving_line_1.ilike(pattern),
                    UrnEngravingJob.piece_label == "main",
                )
                .first()
            )
            if job:
                return {
                    "matched": True,
                    "order_id": job.urn_order_id,
                    "job_id": job.id,
                    "match_method": "decedent_name",
                    "decedent_name": decedent,
                }

        return {"matched": False, "error": "Could not match proof to an order"}

    @staticmethod
    def _match_funeral_home(
        db: Session, tenant_id: str, name: str, email: str,
    ) -> str | None:
        """Try to match funeral home name/email to a CompanyEntity."""
        from app.models.company_entity import CompanyEntity

        # Try email match first
        if email:
            entity = (
                db.query(CompanyEntity)
                .filter(
                    CompanyEntity.tenant_id == tenant_id,
                    CompanyEntity.is_funeral_home == True,
                    CompanyEntity.email == email,
                )
                .first()
            )
            if entity:
                return entity.id

        # Fuzzy name match
        if name:
            pattern = f"%{name}%"
            entity = (
                db.query(CompanyEntity)
                .filter(
                    CompanyEntity.tenant_id == tenant_id,
                    CompanyEntity.is_funeral_home == True,
                    CompanyEntity.name.ilike(pattern),
                )
                .first()
            )
            if entity:
                return entity.id

        return None

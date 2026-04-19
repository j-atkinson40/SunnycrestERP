"""UrnEngravingService — engraving specs, proof workflow, FH approval."""

import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.urn_engraving_job import UrnEngravingJob
from app.models.urn_order import UrnOrder
from app.models.urn_product import UrnProduct
from app.models.urn_tenant_settings import UrnTenantSettings

logger = logging.getLogger(__name__)


class UrnEngravingService:

    @staticmethod
    def get_jobs_for_order(
        db: Session, tenant_id: str, order_id: str,
    ) -> list[UrnEngravingJob]:
        return (
            db.query(UrnEngravingJob)
            .filter(
                UrnEngravingJob.urn_order_id == order_id,
                UrnEngravingJob.tenant_id == tenant_id,
            )
            .order_by(UrnEngravingJob.piece_label)
            .all()
        )

    @staticmethod
    def update_specs(
        db: Session, tenant_id: str, job_id: str, data: dict,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)

        for field in [
            "engraving_line_1", "engraving_line_2",
            "engraving_line_3", "engraving_line_4",
            "font_selection", "color_selection",
        ]:
            val = data.get(field)
            if val is not None:
                setattr(job, field, val)

        # Propagate to companions if flag set
        if data.get("propagate_to_companions") and job.piece_label == "main":
            companions = (
                db.query(UrnEngravingJob)
                .filter(
                    UrnEngravingJob.urn_order_id == job.urn_order_id,
                    UrnEngravingJob.piece_label != "main",
                )
                .all()
            )
            for companion in companions:
                for field in [
                    "engraving_line_1", "engraving_line_2",
                    "engraving_line_3", "engraving_line_4",
                    "font_selection", "color_selection",
                ]:
                    val = data.get(field)
                    if val is not None:
                        setattr(companion, field, val)

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def generate_wilbert_form(
        db: Session, tenant_id: str, order_id: str,
    ) -> dict:
        """Compile all jobs into Wilbert form structure + PDF.

        Returns dict with entries list and pdf_bytes.
        """
        from app.services.wilbert_utils import generate_form_data, render_form_pdf

        order = (
            db.query(UrnOrder)
            .options(joinedload(UrnOrder.urn_product), joinedload(UrnOrder.funeral_home))
            .filter(UrnOrder.id == order_id, UrnOrder.tenant_id == tenant_id)
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        jobs = UrnEngravingService.get_jobs_for_order(db, tenant_id, order_id)
        if not jobs:
            raise HTTPException(status_code=400, detail="No engraving jobs for this order")

        form_data = generate_form_data(order, jobs)

        # Populate caller-provided fields
        product = order.urn_product
        fh = order.funeral_home
        for piece in form_data:
            piece["Urn Model"] = product.name if product else ""
            piece["Urn SKU"] = product.sku or "" if product else ""
            piece["Funeral Home"] = fh.name if fh else ""

        # Save snapshot to each job
        for i, job in enumerate(jobs):
            if i < len(form_data):
                job.generated_form_snapshot = dict(form_data[i])
        db.commit()

        pdf_bytes = render_form_pdf(form_data, db=db, company_id=tenant_id)

        return {
            "entries": form_data,
            "pdf_bytes": pdf_bytes,
            "order_id": order_id,
        }

    @staticmethod
    def submit_to_wilbert(
        db: Session, tenant_id: str, order_id: str,
    ) -> UrnOrder:
        """Generate form, email to Wilbert, update status."""
        from app.services.wilbert_utils import build_submission_email

        order = (
            db.query(UrnOrder)
            .options(joinedload(UrnOrder.urn_product), joinedload(UrnOrder.funeral_home))
            .filter(UrnOrder.id == order_id, UrnOrder.tenant_id == tenant_id)
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        form_result = UrnEngravingService.generate_wilbert_form(db, tenant_id, order_id)
        pdf_bytes = form_result["pdf_bytes"]

        # Get decedent name from main engraving job
        main_job = (
            db.query(UrnEngravingJob)
            .filter(
                UrnEngravingJob.urn_order_id == order_id,
                UrnEngravingJob.piece_label == "main",
            )
            .first()
        )
        decedent_name = main_job.engraving_line_1 or "Unknown" if main_job else "Unknown"

        # Get tenant settings for submission email
        settings = db.query(UrnTenantSettings).filter(
            UrnTenantSettings.tenant_id == tenant_id
        ).first()

        if settings and settings.wilbert_submission_email:
            from app.models.company import Company
            tenant = db.query(Company).filter(Company.id == tenant_id).first()
            tenant_slug = tenant.slug if tenant else "unknown"

            email_data = build_submission_email(
                order, pdf_bytes, tenant_slug, decedent_name,
            )
            try:
                from app.services.email_service import EmailService
                svc = EmailService()
                attachment = {
                    "filename": email_data["attachment_name"],
                    "content": base64.b64encode(pdf_bytes).decode(),
                    "content_type": "application/pdf",
                }
                svc.send_email(
                    to=settings.wilbert_submission_email,
                    subject=email_data["subject"],
                    html_body=email_data["body_html"],
                    attachments=[attachment],
                    company_id=tenant_id,
                    db=db,
                )
            except Exception as e:
                logger.error("Failed to email Wilbert submission: %s", e)

        # Update all jobs and order status
        now = datetime.now(timezone.utc)
        jobs = UrnEngravingService.get_jobs_for_order(db, tenant_id, order_id)
        for job in jobs:
            job.submitted_at = now
            job.proof_status = "awaiting_proof"

        order.status = "proof_pending"

        # Compute expected arrival date
        lead_days = settings.supplier_lead_days if settings else 7
        order.expected_arrival_date = (
            now + timedelta(days=lead_days)
        ).date()

        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def upload_proof(
        db: Session, tenant_id: str, job_id: str, file_id: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        job.proof_file_id = file_id
        job.proof_received_at = datetime.now(timezone.utc)
        job.proof_status = "proof_received"
        db.commit()
        db.refresh(job)

        # Auto-send FH approval if email available
        order = db.query(UrnOrder).filter(UrnOrder.id == job.urn_order_id).first()
        if order and order.fh_contact_email:
            try:
                UrnEngravingService.send_fh_approval_email(db, tenant_id, job_id)
                db.refresh(job)
            except Exception as e:
                logger.warning("Could not auto-send FH approval email: %s", e)

        return job

    @staticmethod
    def send_fh_approval_email(
        db: Session, tenant_id: str, job_id: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        order = (
            db.query(UrnOrder)
            .options(joinedload(UrnOrder.urn_product))
            .filter(UrnOrder.id == job.urn_order_id)
            .first()
        )
        if not order or not order.fh_contact_email:
            raise HTTPException(
                status_code=400,
                detail="No FH contact email on this order",
            )

        # Generate token
        settings = db.query(UrnTenantSettings).filter(
            UrnTenantSettings.tenant_id == tenant_id
        ).first()
        expiry_days = settings.fh_approval_token_expiry_days if settings else 3

        token = str(uuid.uuid4())
        job.fh_approval_token = token
        job.fh_approval_token_expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expiry_days)
        )
        job.proof_status = "awaiting_fh_approval"

        # Update order status
        order.status = "awaiting_fh_approval"

        db.commit()

        # Send email
        from app.config import settings as app_settings
        frontend_url = getattr(app_settings, "FRONTEND_URL", "http://localhost:5173")
        approve_url = f"{frontend_url}/proof-approval/{token}"
        changes_url = f"{frontend_url}/proof-approval/{token}?action=changes"

        decedent = job.engraving_line_1 or "Unknown"
        product_name = order.urn_product.name if order.urn_product else "Urn"

        html = (
            f"<h2>Engraving Proof Ready for Review</h2>"
            f"<p><strong>Decedent:</strong> {decedent}</p>"
            f"<p><strong>Urn:</strong> {product_name}</p>"
            f"<p><strong>Piece:</strong> {job.piece_label}</p>"
            f"<p>Please review the attached proof and respond:</p>"
            f'<p><a href="{approve_url}" style="background:#16a34a;color:#fff;'
            f'padding:12px 24px;text-decoration:none;border-radius:6px;'
            f'display:inline-block;margin:8px 4px;">Approve Proof</a>'
            f'<a href="{changes_url}" style="background:#dc2626;color:#fff;'
            f'padding:12px 24px;text-decoration:none;border-radius:6px;'
            f'display:inline-block;margin:8px 4px;">Request Changes</a></p>'
            f"<p><small>This link expires in {expiry_days} days.</small></p>"
        )

        try:
            from app.services.email_service import EmailService
            svc = EmailService()
            svc.send_email(
                to=order.fh_contact_email,
                subject=f"Engraving Proof: {decedent} — {product_name}",
                html_body=html,
                company_id=order.tenant_id,
                db=db,
            )
        except Exception as e:
            logger.error("Failed to send FH approval email: %s", e)

        db.refresh(job)
        return job

    @staticmethod
    def process_fh_approval(
        db: Session, token: str, approved_by_name: str,
        approved_by_email: str | None = None,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job_by_token(db, token)
        now = datetime.now(timezone.utc)

        job.proof_status = "fh_approved"
        job.fh_approved_by_name = approved_by_name
        job.fh_approved_by_email = approved_by_email
        job.fh_approved_at = now
        job.fh_approval_token = None
        job.fh_approval_token_expires_at = None

        # Check if all jobs on this order are FH approved
        all_jobs = (
            db.query(UrnEngravingJob)
            .filter(UrnEngravingJob.urn_order_id == job.urn_order_id)
            .all()
        )
        if all(j.proof_status == "fh_approved" or j.id == job.id for j in all_jobs):
            order = db.query(UrnOrder).filter(UrnOrder.id == job.urn_order_id).first()
            if order:
                order.status = "fh_approved"

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def process_fh_change_request(
        db: Session, token: str, notes: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job_by_token(db, token)
        job.fh_change_request_notes = notes
        job.proof_status = "fh_changes_requested"
        job.fh_approval_token = None
        job.fh_approval_token_expires_at = None

        order = db.query(UrnOrder).filter(UrnOrder.id == job.urn_order_id).first()
        if order:
            order.status = "fh_changes_requested"

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def staff_approve_proof(
        db: Session, tenant_id: str, job_id: str, user_id: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        now = datetime.now(timezone.utc)

        job.approved_by = user_id
        job.approved_at = now
        job.proof_status = "approved"

        # Check if all jobs on this order are staff approved
        all_jobs = (
            db.query(UrnEngravingJob)
            .filter(UrnEngravingJob.urn_order_id == job.urn_order_id)
            .all()
        )
        all_approved = all(
            j.proof_status == "approved" or j.id == job.id for j in all_jobs
        )
        if all_approved:
            order = db.query(UrnOrder).filter(UrnOrder.id == job.urn_order_id).first()
            if order:
                order.status = "proof_approved"

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def staff_reject_proof(
        db: Session, tenant_id: str, job_id: str, rejection_notes: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        job.proof_status = "rejected"
        job.rejection_notes = rejection_notes
        job.resubmission_count += 1
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_correction_summary(
        db: Session, tenant_id: str, job_id: str,
    ) -> dict:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        return {
            "job_id": job.id,
            "piece_label": job.piece_label,
            "original_specs": {
                "engraving_line_1": job.engraving_line_1,
                "engraving_line_2": job.engraving_line_2,
                "engraving_line_3": job.engraving_line_3,
                "engraving_line_4": job.engraving_line_4,
                "font_selection": job.font_selection,
                "color_selection": job.color_selection,
            },
            "rejection_notes": job.rejection_notes,
            "fh_change_request_notes": job.fh_change_request_notes,
            "resubmission_count": job.resubmission_count,
        }

    @staticmethod
    def attach_verbal_approval(
        db: Session, tenant_id: str, job_id: str, transcript_excerpt: str,
    ) -> UrnEngravingJob:
        """Flag verbal approval from call intelligence — does NOT auto-approve."""
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        job.verbal_approval_flagged = True
        job.verbal_approval_transcript_excerpt = transcript_excerpt
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def attach_verbal_change_request(
        db: Session, tenant_id: str, job_id: str, notes: str,
    ) -> UrnEngravingJob:
        job = UrnEngravingService._get_job(db, tenant_id, job_id)
        job.fh_change_request_notes = notes
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def _get_job(db: Session, tenant_id: str, job_id: str) -> UrnEngravingJob:
        job = (
            db.query(UrnEngravingJob)
            .filter(
                UrnEngravingJob.id == job_id,
                UrnEngravingJob.tenant_id == tenant_id,
            )
            .first()
        )
        if not job:
            raise HTTPException(status_code=404, detail="Engraving job not found")
        return job

    @staticmethod
    def _get_job_by_token(db: Session, token: str) -> UrnEngravingJob:
        job = (
            db.query(UrnEngravingJob)
            .filter(UrnEngravingJob.fh_approval_token == token)
            .first()
        )
        if not job:
            raise HTTPException(status_code=404, detail="Invalid or expired approval token")
        if (
            job.fh_approval_token_expires_at
            and job.fh_approval_token_expires_at < datetime.now(timezone.utc)
        ):
            raise HTTPException(status_code=410, detail="Approval token has expired")
        return job

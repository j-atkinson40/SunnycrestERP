"""Social Service Certificate Service — generate, approve, void, and email certificates.

Certificates are auto-generated when an order containing a Social Service Graveliner
product is marked as delivered. They sit in pending_approval until an invoice reviewer
approves (triggering email to the funeral home) or voids them.
"""

import base64
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.social_service_certificate import SocialServiceCertificate
from app.models.user import User
from app.utils.company_name_resolver import resolve_customer_name, resolve_cemetery_name

logger = logging.getLogger(__name__)

# Product name patterns that identify a Social Service Graveliner line item
_SS_PATTERNS = [
    "social service",
    "ss graveliner",
    "social services graveliner",
    "graveliner ss",
]


class SocialServiceCertificateService:

    @staticmethod
    def is_social_service_order(order: SalesOrder) -> bool:
        """Check if any line item on this order is a Social Service Graveliner."""
        for line in order.lines:
            desc = (line.description or "").lower()
            if any(pat in desc for pat in _SS_PATTERNS):
                return True
        return False

    @staticmethod
    def _find_ss_line(order: SalesOrder) -> SalesOrderLine | None:
        """Return the first Social Service Graveliner line on the order."""
        for line in order.lines:
            desc = (line.description or "").lower()
            if any(pat in desc for pat in _SS_PATTERNS):
                return line
        return None

    @staticmethod
    def generate_pending(
        order_id: str,
        db: Session,
        delivered_at: datetime | None = None,
    ) -> SocialServiceCertificate | None:
        """Generate a pending certificate for a just-delivered social service order.

        Called automatically from the delivery completion hook.
        Returns the new certificate, or None if not applicable / already exists.
        """
        order = (
            db.query(SalesOrder)
            .options(
                joinedload(SalesOrder.lines),
                joinedload(SalesOrder.customer),
                joinedload(SalesOrder.cemetery),
                joinedload(SalesOrder.company),
            )
            .filter(SalesOrder.id == order_id)
            .first()
        )
        if not order:
            logger.warning("SSC: order %s not found", order_id)
            return None

        # Check for existing certificate
        existing = (
            db.query(SocialServiceCertificate)
            .filter(SocialServiceCertificate.order_id == order_id)
            .first()
        )
        if existing:
            logger.info("SSC: certificate already exists for order %s", order_id)
            return existing

        # Find the social service line
        ss_line = SocialServiceCertificateService._find_ss_line(order)
        if not ss_line:
            logger.debug("SSC: no social service line on order %s", order_id)
            return None

        certificate_number = f"{order.number}-SSC"
        effective_delivered_at = delivered_at or order.delivered_at or datetime.now(timezone.utc)

        # Resolve display names
        funeral_home_name = resolve_customer_name(order.customer) if order.customer else "Unknown"
        cemetery_name = resolve_cemetery_name(order.cemetery) if order.cemetery else "N/A"
        deceased_name = order.deceased_name or order.ship_to_name or "Unknown"
        product_price = ss_line.unit_price or Decimal("0.00")

        # Build company config for PDF letterhead
        company = order.company
        company_config = {
            "name": company.name if company else "",
            "company_legal_name": getattr(company, "company_legal_name", None) or "",
            "address_street": getattr(company, "address_street", "") or "",
            "address_city": getattr(company, "address_city", "") or "",
            "address_state": getattr(company, "address_state", "") or "",
            "address_zip": getattr(company, "address_zip", "") or "",
            "phone": getattr(company, "phone", "") or getattr(company, "company_phone", "") or "",
            "email": getattr(company, "email", "") or "",
        }

        # Generate PDF
        from app.utils.pdf_generators.social_service_certificate_pdf import (
            generate_social_service_certificate_pdf,
        )

        pdf_bytes = generate_social_service_certificate_pdf(
            certificate_number=certificate_number,
            deceased_name=deceased_name,
            funeral_home_name=funeral_home_name,
            cemetery_name=cemetery_name,
            product_name=ss_line.description,
            product_price=product_price,
            delivered_at=effective_delivered_at,
            company_config=company_config,
            db=db,
            company_id=order.company_id,
        )

        # Upload to R2
        r2_key = f"certificates/social-service/{certificate_number}.pdf"
        try:
            from app.services.legacy_r2_client import upload_bytes
            upload_bytes(pdf_bytes, r2_key, content_type="application/pdf")
        except Exception as exc:
            logger.error("SSC: R2 upload failed for %s: %s", certificate_number, exc)
            r2_key = None  # Still create the record; PDF can be regenerated

        # Create the certificate record
        cert = SocialServiceCertificate(
            company_id=order.company_id,
            certificate_number=certificate_number,
            order_id=order.id,
            status="pending_approval",
            pdf_r2_key=r2_key,
        )
        db.add(cert)
        db.commit()
        db.refresh(cert)

        logger.info(
            "SSC: generated certificate %s for order %s (status: pending_approval)",
            certificate_number,
            order.number,
        )
        return cert

    @staticmethod
    def approve(
        certificate_id: str,
        approved_by_user_id: str,
        db: Session,
    ) -> SocialServiceCertificate:
        """Approve a pending certificate and send it to the funeral home."""
        cert = (
            db.query(SocialServiceCertificate)
            .filter(SocialServiceCertificate.id == certificate_id)
            .first()
        )
        if not cert:
            raise ValueError("Certificate not found")
        if cert.status != "pending_approval":
            raise ValueError(f"Certificate is '{cert.status}', expected 'pending_approval'")

        cert.status = "approved"
        cert.approved_at = datetime.now(timezone.utc)
        cert.approved_by_id = approved_by_user_id
        db.commit()

        # Send email (non-fatal)
        try:
            SocialServiceCertificateService.send_to_funeral_home(cert, db)
        except Exception as exc:
            logger.error("SSC: email send failed for %s: %s", cert.certificate_number, exc)

        db.refresh(cert)
        return cert

    @staticmethod
    def void(
        certificate_id: str,
        voided_by_user_id: str,
        void_reason: str,
        db: Session,
    ) -> SocialServiceCertificate:
        """Void a pending or approved certificate."""
        cert = (
            db.query(SocialServiceCertificate)
            .filter(SocialServiceCertificate.id == certificate_id)
            .first()
        )
        if not cert:
            raise ValueError("Certificate not found")
        if cert.status not in ("pending_approval", "approved"):
            raise ValueError(f"Cannot void a certificate with status '{cert.status}'")

        cert.status = "voided"
        cert.voided_at = datetime.now(timezone.utc)
        cert.voided_by_id = voided_by_user_id
        cert.void_reason = void_reason
        db.commit()
        db.refresh(cert)

        logger.info("SSC: voided certificate %s — reason: %s", cert.certificate_number, void_reason)
        return cert

    @staticmethod
    def send_to_funeral_home(
        cert: SocialServiceCertificate,
        db: Session,
    ) -> None:
        """Email the certificate PDF to the funeral home."""
        order = (
            db.query(SalesOrder)
            .options(joinedload(SalesOrder.customer))
            .filter(SalesOrder.id == cert.order_id)
            .first()
        )
        if not order or not order.customer:
            logger.warning("SSC: no customer for certificate %s", cert.certificate_number)
            return

        customer = order.customer
        # Try billing email first, then primary email
        to_email = (
            getattr(customer, "billing_email", None)
            or getattr(customer, "email", None)
        )
        if not to_email:
            logger.warning("SSC: no email for customer %s", customer.id)
            return

        # Download PDF from R2
        pdf_bytes = None
        if cert.pdf_r2_key:
            try:
                from app.services.legacy_r2_client import download_bytes
                pdf_bytes = download_bytes(cert.pdf_r2_key)
            except Exception as exc:
                logger.error("SSC: R2 download failed for %s: %s", cert.pdf_r2_key, exc)

        if not pdf_bytes:
            logger.error("SSC: cannot send email — no PDF for %s", cert.certificate_number)
            return

        deceased_name = order.deceased_name or order.ship_to_name or "Deceased"
        funeral_home_name = resolve_customer_name(customer)
        company = db.query(Company).filter(Company.id == order.company_id).first()
        tenant_name = company.name if company else "Bridgeable"

        subject = f"Service Delivery Certificate \u2013 {deceased_name}"
        html_body = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <p>Dear {_esc(funeral_home_name)},</p>
  <p>
    Please find attached the Service Delivery Certificate for <strong>{_esc(deceased_name)}</strong>.
    This document confirms delivery of the burial vault product and is provided for your
    government benefit program records.
  </p>
  <p>
    This certificate is <strong>not an invoice</strong>. A separate invoice will be provided
    through your standard billing channel.
  </p>
  <p>
    If you have any questions, please contact us directly.
  </p>
  <p style="color: #666; font-size: 12px; margin-top: 30px;">
    {_esc(tenant_name)}
  </p>
</div>
"""

        attachments = [
            {
                "filename": f"{cert.certificate_number}.pdf",
                "content": base64.b64encode(pdf_bytes).decode(),
            }
        ]

        from app.services.email_service import EmailService

        result = EmailService().send_email(
            to=to_email,
            subject=subject,
            html_body=html_body,
            from_name=f"{tenant_name} via Bridgeable",
            attachments=attachments,
            company_id=order.company_id,
            db=db,
        )

        if result.get("success"):
            cert.status = "sent"
            cert.sent_at = datetime.now(timezone.utc)
            cert.email_sent_to = to_email
            db.commit()
            logger.info("SSC: sent certificate %s to %s", cert.certificate_number, to_email)
        else:
            logger.error("SSC: email failed for %s", cert.certificate_number)

    @staticmethod
    def get_pending(db: Session, company_id: str) -> list[dict]:
        """Return pending certificates with order context for the briefing block."""
        certs = (
            db.query(SocialServiceCertificate)
            .options(
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.customer),
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.cemetery),
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.lines),
            )
            .filter(
                SocialServiceCertificate.company_id == company_id,
                SocialServiceCertificate.status == "pending_approval",
            )
            .order_by(SocialServiceCertificate.generated_at.desc())
            .all()
        )

        results = []
        for cert in certs:
            order = cert.order
            ss_line = SocialServiceCertificateService._find_ss_line(order) if order else None
            results.append({
                "id": cert.id,
                "certificate_number": cert.certificate_number,
                "status": cert.status,
                "deceased_name": order.deceased_name or order.ship_to_name if order else None,
                "funeral_home_name": resolve_customer_name(order.customer) if order and order.customer else None,
                "cemetery_name": resolve_cemetery_name(order.cemetery) if order and order.cemetery else None,
                "product_price": str(ss_line.unit_price) if ss_line and ss_line.unit_price else None,
                "delivered_at": (order.delivered_at or cert.generated_at).isoformat() if order else cert.generated_at.isoformat(),
                "generated_at": cert.generated_at.isoformat(),
            })
        return results

    @staticmethod
    def get_all(db: Session, company_id: str, status_filter: str | None = None) -> list[dict]:
        """Return all certificates for the management page."""
        q = (
            db.query(SocialServiceCertificate)
            .options(
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.customer),
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.cemetery),
                joinedload(SocialServiceCertificate.order)
                .joinedload(SalesOrder.lines),
                joinedload(SocialServiceCertificate.approved_by),
                joinedload(SocialServiceCertificate.voided_by),
            )
            .filter(SocialServiceCertificate.company_id == company_id)
        )
        if status_filter:
            q = q.filter(SocialServiceCertificate.status == status_filter)

        certs = q.order_by(SocialServiceCertificate.generated_at.desc()).all()

        results = []
        for cert in certs:
            order = cert.order
            ss_line = SocialServiceCertificateService._find_ss_line(order) if order else None
            results.append({
                "id": cert.id,
                "certificate_number": cert.certificate_number,
                "status": cert.status,
                "order_id": cert.order_id,
                "order_number": order.number if order else None,
                "deceased_name": order.deceased_name or order.ship_to_name if order else None,
                "funeral_home_name": resolve_customer_name(order.customer) if order and order.customer else None,
                "cemetery_name": resolve_cemetery_name(order.cemetery) if order and order.cemetery else None,
                "product_price": str(ss_line.unit_price) if ss_line and ss_line.unit_price else None,
                "delivered_at": (order.delivered_at or cert.generated_at).isoformat() if order else cert.generated_at.isoformat(),
                "generated_at": cert.generated_at.isoformat(),
                "approved_at": cert.approved_at.isoformat() if cert.approved_at else None,
                "approved_by_name": _user_display(cert.approved_by),
                "voided_at": cert.voided_at.isoformat() if cert.voided_at else None,
                "voided_by_name": _user_display(cert.voided_by),
                "void_reason": cert.void_reason,
                "sent_at": cert.sent_at.isoformat() if cert.sent_at else None,
                "email_sent_to": cert.email_sent_to,
            })
        return results

    @staticmethod
    def get_detail(db: Session, certificate_id: str, company_id: str) -> dict | None:
        """Return a single certificate with full detail."""
        certs = SocialServiceCertificateService.get_all(db, company_id)
        for c in certs:
            if c["id"] == certificate_id:
                return c
        return None


def _user_display(user: User | None) -> str | None:
    if not user:
        return None
    return getattr(user, "full_name", None) or user.email


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

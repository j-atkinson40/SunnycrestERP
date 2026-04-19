"""Native e-signature infrastructure — Phase D-4.

Package layout:
  token_service        — cryptographic token generation for signer links
  signature_service    — envelope lifecycle (create, send, sign, decline, void)
  signature_renderer   — apply signatures to the document PDF
  certificate_service  — generate Certificate of Completion
  notification_service — send emails on envelope lifecycle events

Usage:

    from app.services.signing import signature_service

    envelope = signature_service.create_envelope(
        db,
        document_id=doc.id,
        company_id=company.id,
        created_by_user_id=user.id,
        subject="Disinterment Release Form",
        description="Signed authorization for disinterment of remains",
        parties=[
            signature_service.PartyInput(
                signing_order=1,
                role="funeral_home_director",
                display_name="John Smith",
                email="jsmith@fh.com",
            ),
            # ... more parties
        ],
        fields=[
            signature_service.FieldInput(
                signing_order=1,
                field_type="signature",
                anchor_string="/sig_fh/",
            ),
        ],
    )
    signature_service.send_envelope(db, envelope.id)
"""

from app.services.signing import (
    certificate_service,
    notification_service,
    signature_renderer,
    signature_service,
    token_service,
)

__all__ = [
    "certificate_service",
    "notification_service",
    "signature_renderer",
    "signature_service",
    "token_service",
]

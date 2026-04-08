"""DocuSign e-signature service — stub in dev/test, real credentials via tenant settings.

In production, reads DocuSign credentials from tenant settings_json:
  - docusign_integration_key
  - docusign_account_id
  - docusign_base_url
  - docusign_access_token (via OAuth)

In dev/test (ENVIRONMENT != 'production'), returns fake envelope IDs
and simulates webhook events.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.company import Company

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_docusign_config(db: Session, company_id: str) -> dict:
    """Read DocuSign credentials from tenant settings."""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {}
    s = company.settings or {}
    return {
        "integration_key": s.get("docusign_integration_key", ""),
        "account_id": s.get("docusign_account_id", ""),
        "base_url": s.get("docusign_base_url", "https://demo.docusign.net/restapi"),
        "access_token": s.get("docusign_access_token", ""),
    }


def _is_stub_mode() -> bool:
    """True when running in dev/test — returns fake responses."""
    return getattr(app_settings, "ENVIRONMENT", "dev") != "production"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_envelope(
    db: Session,
    company_id: str,
    *,
    case_id: str,
    case_number: str,
    decedent_name: str,
    funeral_home_email: str | None = None,
    cemetery_email: str | None = None,
    next_of_kin_email: str | None = None,
    manufacturer_email: str | None = None,
    webhook_url: str = "",
) -> str:
    """Create a DocuSign envelope with 4 signers for a disinterment release form.

    Returns the envelope_id (UUID string in stub mode, real envelope ID in production).
    """
    if _is_stub_mode():
        envelope_id = f"stub-{uuid.uuid4().hex[:16]}"
        logger.info(
            "STUB DocuSign: created envelope %s for case %s (%s)",
            envelope_id,
            case_number,
            decedent_name,
        )
        return envelope_id

    # --- Production path ---
    config = _get_docusign_config(db, company_id)
    if not config.get("access_token"):
        raise ValueError(
            "DocuSign credentials not configured. Go to Settings → Disinterment → DocuSign tab."
        )

    try:
        # Import DocuSign SDK (only in production to avoid dev dependency)
        from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, Signer, SignHere, Tabs, Recipients, Document as DSDocument, EventNotification

        api_client = ApiClient()
        api_client.host = config["base_url"]
        api_client.set_default_header("Authorization", f"Bearer {config['access_token']}")

        # Build signers
        signers = []
        signer_idx = 1

        def _add_signer(email: str | None, name: str, role: str) -> None:
            nonlocal signer_idx
            if not email:
                return
            signer = Signer(
                email=email,
                name=name,
                recipient_id=str(signer_idx),
                routing_order=str(signer_idx),
                role_name=role,
                tabs=Tabs(
                    sign_here_tabs=[
                        SignHere(
                            anchor_string=f"/sig_{role}/",
                            anchor_units="pixels",
                            anchor_x_offset="20",
                            anchor_y_offset="10",
                        )
                    ]
                ),
            )
            signers.append(signer)
            signer_idx += 1

        _add_signer(funeral_home_email, "Funeral Director", "funeral_home")
        _add_signer(cemetery_email, "Cemetery Representative", "cemetery")
        _add_signer(next_of_kin_email, "Next of Kin", "next_of_kin")
        _add_signer(manufacturer_email, "Manufacturer", "manufacturer")

        if not signers:
            raise ValueError("At least one signer email is required")

        # Build envelope
        envelope_definition = EnvelopeDefinition(
            email_subject=f"Disinterment Release Form — {decedent_name} ({case_number})",
            documents=[
                DSDocument(
                    document_base64="",  # TODO: Generate PDF from case data
                    name=f"Disinterment Release — {case_number}",
                    file_extension="pdf",
                    document_id="1",
                )
            ],
            recipients=Recipients(signers=signers),
            status="sent",
        )

        # Add webhook notification if URL provided
        if webhook_url:
            envelope_definition.event_notification = EventNotification(
                url=webhook_url,
                require_acknowledgment="true",
                envelope_events=[
                    {"envelope_event_status_code": "sent"},
                    {"envelope_event_status_code": "completed"},
                ],
                recipient_events=[
                    {"recipient_event_status_code": "Completed"},
                    {"recipient_event_status_code": "Declined"},
                ],
            )

        envelopes_api = EnvelopesApi(api_client)
        result = envelopes_api.create_envelope(
            account_id=config["account_id"],
            envelope_definition=envelope_definition,
        )
        logger.info(
            "DocuSign envelope created: %s for case %s",
            result.envelope_id,
            case_number,
        )
        return result.envelope_id

    except ImportError:
        logger.error("docusign-esign package not installed — falling back to stub")
        return f"stub-{uuid.uuid4().hex[:16]}"
    except Exception as e:
        logger.error("DocuSign envelope creation failed: %s", e)
        raise


def get_envelope_status(
    db: Session, company_id: str, envelope_id: str
) -> dict:
    """Get the current status of a DocuSign envelope."""
    if _is_stub_mode():
        return {
            "envelope_id": envelope_id,
            "status": "sent",
            "recipients": [],
        }

    config = _get_docusign_config(db, company_id)
    try:
        from docusign_esign import ApiClient, EnvelopesApi

        api_client = ApiClient()
        api_client.host = config["base_url"]
        api_client.set_default_header("Authorization", f"Bearer {config['access_token']}")

        envelopes_api = EnvelopesApi(api_client)
        result = envelopes_api.get_envelope(
            account_id=config["account_id"],
            envelope_id=envelope_id,
        )
        return {
            "envelope_id": result.envelope_id,
            "status": result.status,
        }
    except ImportError:
        return {"envelope_id": envelope_id, "status": "unknown"}
    except Exception as e:
        logger.error("DocuSign get_envelope_status failed: %s", e)
        return {"envelope_id": envelope_id, "status": "error", "error": str(e)}


def void_envelope(
    db: Session, company_id: str, envelope_id: str, reason: str = "Voided by user"
) -> None:
    """Void a DocuSign envelope."""
    if _is_stub_mode():
        logger.info("STUB DocuSign: voided envelope %s — %s", envelope_id, reason)
        return

    config = _get_docusign_config(db, company_id)
    try:
        from docusign_esign import ApiClient, EnvelopesApi, Envelope

        api_client = ApiClient()
        api_client.host = config["base_url"]
        api_client.set_default_header("Authorization", f"Bearer {config['access_token']}")

        envelopes_api = EnvelopesApi(api_client)
        envelopes_api.update(
            account_id=config["account_id"],
            envelope_id=envelope_id,
            envelope=Envelope(status="voided", voided_reason=reason),
        )
        logger.info("DocuSign envelope voided: %s — %s", envelope_id, reason)
    except ImportError:
        logger.warning("docusign-esign not installed, cannot void envelope")
    except Exception as e:
        logger.error("DocuSign void_envelope failed: %s", e)
        raise


def test_connection(db: Session, company_id: str) -> dict:
    """Test DocuSign API connectivity with stored credentials."""
    if _is_stub_mode():
        return {"success": True, "message": "Stub mode — connection simulated"}

    config = _get_docusign_config(db, company_id)
    if not config.get("access_token"):
        return {"success": False, "message": "No access token configured"}

    try:
        from docusign_esign import ApiClient, AccountsApi

        api_client = ApiClient()
        api_client.host = config["base_url"]
        api_client.set_default_header("Authorization", f"Bearer {config['access_token']}")

        accounts_api = AccountsApi(api_client)
        accounts_api.get_account_information(account_id=config["account_id"])
        return {"success": True, "message": "Connected to DocuSign successfully"}
    except ImportError:
        return {"success": False, "message": "docusign-esign package not installed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

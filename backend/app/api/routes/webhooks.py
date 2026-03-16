"""Inbound webhooks — Twilio SMS, etc."""

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import carrier_sms_service

router = APIRouter()


@router.post("/twilio/sms")
def twilio_inbound_sms(
    From: str = Form(...),
    Body: str = Form(""),
    db: Session = Depends(get_db),
):
    """Handle inbound SMS from Twilio.

    Twilio sends form-encoded data with From (phone) and Body (message).
    We reply with TwiML-compatible plain text.
    """
    reply = carrier_sms_service.process_inbound_sms(db, From, Body)
    # Return TwiML response
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")

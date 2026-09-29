from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Response, HTTPException
from fastapi.responses import PlainTextResponse

from backend.auth import get_current_user_optional
from backend.models import User
from backend.services.integrations_service import (
    get_compliance_calendar_events,
    generate_ical_stream,
    sync_gmail_inbox,
    export_tally_xml,
    export_tally_csv,
    get_integrations_status,
    build_google_calendar_url,
    build_gmail_compose_url,
    build_whatsapp_url,
)

router = APIRouter(prefix="/api/integrations", tags=["Cross-Platform Integrations"])

class GmailDraftRequest(BaseModel):
    to_email: str
    subject: str
    body: str

class WhatsAppRequest(BaseModel):
    phone: str
    message: str

class CalendarEventRequest(BaseModel):
    title: str
    date: str
    details: str
    location: Optional[str] = ""


import imaplib
from backend.database import SessionLocal
from backend.models import ConnectedApp

class GmailConnectRequest(BaseModel):
    email: str
    app_password: str


@router.get("/status")
def api_get_integrations_status(user: Optional[User] = Depends(get_current_user_optional)):
    """Retrieve connectivity status of all connected services and database."""
    user_id = user.id if user else None
    return get_integrations_status(user_id)


@router.get("/calendar/events")
def api_get_calendar_events(user: Optional[User] = Depends(get_current_user_optional)):
    """Retrieve compliance deadlines and invoice due dates with 1-click Google Calendar links."""
    user_id = user.id if user else None
    events = get_compliance_calendar_events(user_id)
    return {
        "count": len(events),
        "events": events
    }


@router.get("/calendar/feed.ics")
def api_get_calendar_ics_feed(user: Optional[User] = Depends(get_current_user_optional)):
    """
    Standard iCalendar feed.
    Users can copy this link into Google Calendar -> "Add calendar from URL"
    to subscribe to real-time deadline updates.
    """
    user_id = user.id if user else None
    events = get_compliance_calendar_events(user_id)
    ics_content = generate_ical_stream(events)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "inline; filename=pattubook_calendar.ics",
            "Cache-Control": "no-cache"
        }
    )


@router.post("/calendar/quick-link")
def api_create_quick_calendar_link(req: CalendarEventRequest):
    """Generate 1-click Google Calendar link for custom dates."""
    url = build_google_calendar_url(req.title, req.date, req.details, req.location or "")
    return {"google_calendar_url": url}


@router.post("/gmail/connect")
def api_connect_gmail(req: GmailConnectRequest, user: Optional[User] = Depends(get_current_user_optional)):
    """Authenticate and link personal Gmail via App Password."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Please sign in to connect your personal Gmail account."
        )

    clean_email = req.email.strip().lower()
    clean_pwd = req.app_password.strip().replace(" ", "")

    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Please provide a valid Gmail address.")

    if not clean_pwd or len(clean_pwd) < 8:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid Google App Password (typically 16 characters)."
        )

    # 1. Test IMAP connection immediately over SSL
    try:
        test_mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=12)
        test_mail.login(clean_email, clean_pwd)
        test_mail.logout()
    except Exception as e:
        err_str = str(e)
        raise HTTPException(
            status_code=400,
            detail=f"Gmail authentication failed: {err_str}. Please verify your Gmail address and 16-character App Password (from myaccount.google.com/apppasswords)."
        )

    # 2. Persist in database for this user
    session = SessionLocal()
    try:
        conn_app = session.query(ConnectedApp).filter(
            ConnectedApp.user_id == user.id,
            ConnectedApp.provider == "gmail"
        ).first()

        if not conn_app:
            conn_app = ConnectedApp(
                user_id=user.id,
                provider="gmail",
                account_email=clean_email,
                access_token=clean_pwd,
                is_active=True
            )
            session.add(conn_app)
        else:
            conn_app.account_email = clean_email
            conn_app.access_token = clean_pwd
            conn_app.is_active = True

        session.commit()
    finally:
        session.close()

    # 3. Trigger initial sync so user's emails appear immediately
    from backend.services.imap_service import fetch_emails_from_imap
    sync_result = fetch_emails_from_imap(max_count=15, user_id=user.id)

    return {
        "status": "success",
        "message": f"Gmail connected successfully for {clean_email}! Initial sync: {sync_result.get('message', '')}",
        "account_email": clean_email,
        "synced_count": sync_result.get("synced_count", 0)
    }


@router.post("/gmail/disconnect")
def api_disconnect_gmail(user: Optional[User] = Depends(get_current_user_optional)):
    """Disconnect and unlink personal Gmail."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    session = SessionLocal()
    try:
        conn_app = session.query(ConnectedApp).filter(
            ConnectedApp.user_id == user.id,
            ConnectedApp.provider == "gmail"
        ).first()

        if conn_app:
            conn_app.is_active = False
            session.commit()
    finally:
        session.close()

    return {
        "status": "success",
        "message": "Gmail account disconnected successfully."
    }


@router.post("/gmail/sync")
def api_sync_gmail(user: Optional[User] = Depends(get_current_user_optional)):
    """Ingest recent emails/invoices from Gmail / Yahoo via IMAP with AI classification."""
    user_id = user.id if user else None
    return sync_gmail_inbox(user_id)


@router.get("/imap/status")
def api_get_imap_status(user: Optional[User] = Depends(get_current_user_optional)):
    """Retrieve live status of the 5-minute IMAP background auto-sync worker."""
    from backend.services.imap_service import get_imap_status_summary
    user_id = user.id if user else None
    return get_imap_status_summary(user_id=user_id)


@router.post("/imap/sync")
def api_trigger_imap_sync(user: Optional[User] = Depends(get_current_user_optional)):
    """Manually trigger immediate IMAP sync cycle."""
    from backend.services.imap_service import fetch_emails_from_imap
    user_id = user.id if user else None
    return fetch_emails_from_imap(max_count=20, user_id=user_id)


@router.post("/gmail/compose")
def api_prepare_gmail_compose(req: GmailDraftRequest):
    """Generate direct Gmail composer link."""
    url = build_gmail_compose_url(req.to_email, req.subject, req.body)
    return {
        "gmail_url": url,
        "message": "Gmail compose link generated successfully"
    }


@router.post("/whatsapp/dispatch")
def api_prepare_whatsapp_dispatch(req: WhatsAppRequest):
    """Generate direct WhatsApp Web click-to-chat link with pre-filled message & UPI link."""
    url = build_whatsapp_url(req.phone, req.message)
    return {
        "whatsapp_url": url,
        "message": "WhatsApp link ready for instant dispatch"
    }


@router.get("/tally/export.xml")
def api_export_tally_xml(user: Optional[User] = Depends(get_current_user_optional)):
    """Export invoices and transactions in Tally Prime / ERP XML format."""
    user_id = user.id if user else None
    xml_content = export_tally_xml(user_id)
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=tally_import.xml"
        }
    )


@router.get("/tally/export.csv")
def api_export_tally_csv(user: Optional[User] = Depends(get_current_user_optional)):
    """Export invoices in CSV format for Tally Day Book / Excel."""
    user_id = user.id if user else None
    csv_content = export_tally_csv(user_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=tally_daybook.csv"
        }
    )

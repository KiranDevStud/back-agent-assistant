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


@router.post("/gmail/sync")
def api_sync_gmail(user: Optional[User] = Depends(get_current_user_optional)):
    """Ingest recent emails/invoices from Gmail / Yahoo via IMAP with AI classification."""
    user_id = user.id if user else None
    return sync_gmail_inbox(user_id)


@router.get("/imap/status")
def api_get_imap_status():
    """Retrieve live status of the 5-minute IMAP background auto-sync worker."""
    from backend.services.imap_service import get_imap_status_summary
    return get_imap_status_summary()


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

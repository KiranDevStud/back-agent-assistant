import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import csv
import io

from backend.database import SessionLocal, IS_POSTGRES, DB_URL, get_all_settings
from backend.models import ComplianceRecord, Invoice, Transaction, EmailItem, ConnectedApp, User
from backend.services.email_summarizer import classify_email

def format_date_for_google_cal(date_str: str) -> str:
    """Format YYYY-MM-DD or parseable date string to YYYYMMDD for Google Calendar URL."""
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
        return dt.strftime("%Y%m%d")
    except Exception:
        # Fallback to tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y%m%d")

def build_google_calendar_url(title: str, date_str: str, details: str, location: str = "") -> str:
    """Build a 1-click Google Calendar Event Template URL."""
    cal_date = format_date_for_google_cal(date_str)
    # Full day event: start YYYYMMDD, end next day YYYYMMDD
    try:
        start_dt = datetime.strptime(cal_date, "%Y%m%d")
        end_dt = start_dt + timedelta(days=1)
        dates_param = f"{start_dt.strftime('%Y%m%d')}/{end_dt.strftime('%Y%m%d')}"
    except Exception:
        dates_param = f"{cal_date}/{cal_date}"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": dates_param,
        "details": details,
        "location": location or "Store / Office"
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

def build_gmail_compose_url(to_email: str, subject: str, body: str) -> str:
    """Build a direct Gmail Web Composer URL."""
    params = {
        "view": "cm",
        "fs": "1",
        "to": to_email,
        "su": subject,
        "body": body
    }
    return f"https://mail.google.com/mail/?{urllib.parse.urlencode(params)}"

def build_whatsapp_url(phone: str, message: str) -> str:
    """Build a direct WhatsApp Web / Mobile click-to-chat URL."""
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    if clean_phone and not clean_phone.startswith("91") and len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"

def get_compliance_calendar_events(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve compliance items and invoice due dates formatted as calendar events."""
    session = SessionLocal()
    events = []
    try:
        # 1. Compliance Deadlines
        comp_records = session.query(ComplianceRecord).all()
        for c in comp_records:
            due_date = c.next_due_date or datetime.now().strftime("%Y-%m-%d")
            details = (
                f"Statutory Deadline: {c.title}\n"
                f"Category: Indian Statutory Return ({c.frequency})\n"
                f"Penalty Info: {c.penalty_info or 'Standard late fees apply'}\n"
                f"Notes: {c.description or ''}"
            )
            gcal_url = build_google_calendar_url(
                title=f"[Tax Due] {c.title}",
                date_str=due_date,
                details=details
            )
            events.append({
                "id": f"comp_{c.id}",
                "title": c.title,
                "type": "compliance",
                "date": due_date,
                "urgency": "high" if "3B" in (c.code or "") else "medium",
                "penalty_info": c.penalty_info,
                "google_calendar_url": gcal_url
            })

        # 2. Invoices with upcoming due dates
        invoices = session.query(Invoice).filter(Invoice.status != "Paid").all()
        for inv in invoices:
            if inv.due_date:
                details = (
                    f"Invoice: #{inv.invoice_number}\n"
                    f"Customer / Vendor: {inv.customer_name or inv.vendor_name}\n"
                    f"Amount: ₹{inv.total_amount:,.2f}\n"
                    f"Status: {inv.status}\n"
                    f"Action: Payment settlement / follow-up"
                )
                gcal_url = build_google_calendar_url(
                    title=f"[Payment Due] #{inv.invoice_number} - {inv.customer_name or inv.vendor_name}",
                    date_str=inv.due_date,
                    details=details
                )
                events.append({
                    "id": f"inv_{inv.id}",
                    "title": f"Inv #{inv.invoice_number} ({inv.customer_name or inv.vendor_name})",
                    "type": "invoice",
                    "date": inv.due_date,
                    "amount": inv.total_amount,
                    "google_calendar_url": gcal_url
                })
        return events
    finally:
        session.close()

def generate_ical_stream(events: List[Dict[str, Any]], calendar_name: str = "PattuBook Business Calendar") -> str:
    """Generate standard iCalendar (.ics) format for calendar subscriptions."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PattuBook//Unified Back Office//EN",
        f"X-WR-CALNAME:{calendar_name}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for ev in events:
        d_str = format_date_for_google_cal(ev["date"])
        uid = f"{ev['id']}-{d_str}@pattubook.com"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{d_str}",
            f"SUMMARY:{ev['title']}",
            f"DESCRIPTION:Generated by PattuBook Back Office Assistant",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)

def sync_gmail_inbox(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Ingests live business communications (bills, bank alerts, tax alerts) from Gmail / Yahoo
    via IMAP over SSL with AI classification for the specific user.
    """
    from backend.services.imap_service import fetch_emails_from_imap, get_imap_credentials
    
    creds = get_imap_credentials(user_id=user_id)
    if creds["is_configured"]:
        return fetch_emails_from_imap(max_count=15, user_id=user_id)

    if not user_id:
        return {
            "status": "guest",
            "synced_count": 0,
            "message": "Please sign in to connect your Gmail inbox and sync communications."
        }

    return {
        "status": "not_configured",
        "synced_count": 0,
        "message": "No Gmail account connected. Please connect your Gmail in Integrations using an App Password."
    }

def export_tally_xml(user_id: Optional[int] = None) -> str:
    """Generate Tally Prime / ERP 9 XML import format for invoices."""
    session = SessionLocal()
    try:
        invoices = session.query(Invoice).all()
        settings = get_all_settings(user_id)
        biz_name = settings.get("business_name", "Om Sai Traders")

        xml_lines = [
            '<ENVELOPE>',
            '  <HEADER>',
            '    <TALLYREQUEST>Import Data</TALLYREQUEST>',
            '  </HEADER>',
            '  <BODY>',
            '    <IMPORTDATA>',
            '      <REQUESTDESC>',
            '        <REPORTNAME>Vouchers</REPORTNAME>',
            '      </REQUESTDESC>',
            '      <REQUESTDATA>'
        ]

        for inv in invoices:
            vch_type = "Purchase" if inv.invoice_type == "purchase" else "Sales"
            party = inv.vendor_name if inv.invoice_type == "purchase" else (inv.customer_name or "Cash")
            inv_date = inv.invoice_date or datetime.now().strftime("%Y%m%d")
            # clean date to YYYYMMDD
            clean_date = "".join(c for c in inv_date if c.isdigit())
            if len(clean_date) != 8:
                clean_date = datetime.now().strftime("%Y%m%d")

            xml_lines.extend([
                '        <TALLYMESSAGE xmlns:UDF="TallyUDF">',
                f'          <VOUCHER VCHTYPE="{vch_type}" ACTION="Create">',
                f'            <DATE>{clean_date}</DATE>',
                f'            <VOUCHERTYPENAME>{vch_type}</VOUCHERTYPENAME>',
                f'            <VOUCHERNUMBER>{inv.invoice_number or "INV-01"}</VOUCHERNUMBER>',
                f'            <PARTYLEDGERNAME>{party}</PARTYLEDGERNAME>',
                f'            <NARRATION>GSTIN: {inv.vendor_gstin or ""} Total: {inv.total_amount}</NARRATION>',
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{party}</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>{inv.total_amount:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>',
                '            <ALLLEDGERENTRIES.LIST>',
                f'              <LEDGERNAME>{vch_type} Account</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'              <AMOUNT>-{inv.subtotal:.2f}</AMOUNT>',
                '            </ALLLEDGERENTRIES.LIST>',
                '          </VOUCHER>',
                '        </TALLYMESSAGE>'
            ])

        xml_lines.extend([
            '      </REQUESTDATA>',
            '    </IMPORTDATA>',
            '  </BODY>',
            '</ENVELOPE>'
        ])

        return "\n".join(xml_lines)
    finally:
        session.close()

def export_tally_csv(user_id: Optional[int] = None) -> str:
    """Generate CSV export formatted for Tally Day Book / Excel reconciliation."""
    session = SessionLocal()
    try:
        invoices = session.query(Invoice).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Invoice Number", "Type", "Party Name", "GSTIN", "Date", "Due Date",
            "Subtotal", "CGST", "SGST", "IGST", "Total Amount", "Status"
        ])
        for inv in invoices:
            writer.writerow([
                inv.invoice_number,
                inv.invoice_type,
                inv.vendor_name if inv.invoice_type == "purchase" else inv.customer_name,
                inv.vendor_gstin or inv.buyer_gstin,
                inv.invoice_date,
                inv.due_date,
                inv.subtotal,
                inv.cgst,
                inv.sgst,
                inv.igst,
                inv.total_amount,
                inv.status
            ])
        return output.getvalue()
    finally:
        session.close()

def get_integrations_status(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve health and configuration status for all supported platforms."""
    from backend.services.imap_service import get_imap_status_summary
    imap_info = get_imap_status_summary(user_id=user_id)
    db_engine_name = "PostgreSQL (Railway Production)" if IS_POSTGRES else "SQLite (Local Development)"

    gmail_status = "connected" if imap_info.get("enabled") else ("guest" if user_id is None else "ready")
    user_display = imap_info.get("user") or ("Sign in to connect Gmail" if user_id is None else "No Gmail connected")

    return {
        "database": {
            "engine": db_engine_name,
            "status": "connected",
            "is_postgres": IS_POSTGRES,
            "railway_ready": True
        },
        "google_calendar": {
            "name": "Google Calendar",
            "status": "connected",
            "features": [
                "1-Click Event Template Add",
                "Live iCal (.ics) Sync Feed",
                "Automatic GST & Payment Due Reminders"
            ],
            "feed_endpoint": "/api/integrations/calendar/feed.ics"
        },
        "gmail": {
            "name": "Gmail & Google Workspace (IMAP)",
            "status": gmail_status,
            "imap_configured": imap_info.get("enabled", False),
            "is_user_connected": imap_info.get("is_user_connected", False),
            "imap_host": imap_info.get("host", "imap.gmail.com"),
            "imap_user": user_display,
            "sync_interval_minutes": imap_info.get("interval_minutes", 5),
            "last_sync": imap_info.get("last_sync_time"),
            "next_sync": imap_info.get("next_sync_time"),
            "sync_status": imap_info.get("last_status"),
            "features": [
                f"Automated background sync worker ({imap_info.get('interval_minutes', 5)}m)",
                "AI email categorization & invoice attachment OCR",
                "Direct Web Composer & Chartered Accountant dispatch"
            ]
        },
        "whatsapp": {
            "name": "WhatsApp Business",
            "status": "connected",
            "features": [
                "1-Click Direct Click-to-Chat API",
                "Pre-filled UPI Instant Pay Links",
                "Multi-Tone Reminder Generation"
            ]
        },
        "tally": {
            "name": "Tally Prime & ERP 9",
            "status": "ready",
            "features": [
                "Standard XML Import Vouchers",
                "Day Book CSV Ledger Export",
                "ITC Reconciliation Support"
            ]
        }
    }

import os
import re
import email
import imaplib
import threading
import time
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from backend.config import BASE_DIR, UPLOADS_DIR
from backend.database import SessionLocal, get_all_settings
from backend.models import EmailItem, Invoice
from backend.services.email_summarizer import classify_email

# Global scheduler state
class ImapSyncState:
    def __init__(self):
        self.is_running = False
        self.last_sync_time: Optional[datetime] = None
        self.next_sync_time: Optional[datetime] = None
        self.last_status: str = "initialized"
        self.last_message: str = "IMAP service initialized. Waiting for first cycle."
        self.last_error: Optional[str] = None
        self.total_synced_count: int = 0
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event: threading.Event = threading.Event()

sync_state = ImapSyncState()


def get_imap_credentials() -> Dict[str, Any]:
    """
    Retrieve IMAP credentials dynamically from environment (.env) with fallback to settings.
    Reloads .env so changes made while server is running take effect immediately.
    """
    load_dotenv(override=True)
    
    # Priority: explicit IMAP vars -> SMTP vars -> general email vars
    host = os.getenv("IMAP_HOST", "imap.gmail.com").strip()
    port = int(os.getenv("IMAP_PORT", "993"))
    user = (
        os.getenv("IMAP_USER", "")
        or os.getenv("SMTP_USER", "")
        or os.getenv("FROM_EMAIL", "")
        or os.getenv("BUSINESS_EMAIL", "")
    ).strip()
    password = (
        os.getenv("IMAP_PASSWORD", "")
        or os.getenv("SMTP_PASSWORD", "")
    ).strip()
    
    interval_minutes = int(os.getenv("IMAP_SYNC_INTERVAL_MINUTES", "5"))
    folder = os.getenv("IMAP_FOLDER", "INBOX").strip()

    # Normalize Google App Password: remove spaces if user copied it with spaces "xxxx xxxx xxxx xxxx"
    if "gmail.com" in host.lower() and password:
        password = password.replace(" ", "")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "interval_minutes": max(1, interval_minutes),
        "folder": folder,
        "is_configured": bool(user and password and password != "your_app_specific_password")
    }


def decode_mime_words(raw_header: Optional[str]) -> str:
    """Decode RFC 2047 encoded email headers."""
    if not raw_header:
        return ""
    try:
        decoded_fragments = decode_header(raw_header)
        text_parts = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                enc = encoding or "utf-8"
                try:
                    text_parts.append(fragment.decode(enc, errors="replace"))
                except Exception:
                    text_parts.append(fragment.decode("latin-1", errors="replace"))
            else:
                text_parts.append(str(fragment))
        return " ".join(text_parts).strip()
    except Exception:
        return str(raw_header)


def extract_email_body_and_attachments(msg: email.message.Message) -> Dict[str, Any]:
    """
    Traverse MIME parts, extract plain text or HTML body, and save any invoice attachments.
    """
    body_text = ""
    html_text = ""
    saved_attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Handle attachments
            filename = part.get_filename()
            if filename:
                decoded_fn = decode_mime_words(filename)
                clean_fn = re.sub(r'[^a-zA-Z0-9_.-]', '_', decoded_fn)
                file_ext = Path(clean_fn).suffix.lower()

                # If it's a PDF or image attachment, save it for invoice processing
                if file_ext in [".pdf", ".png", ".jpg", ".jpeg"]:
                    timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
                    save_name = f"{timestamp_prefix}{clean_fn}"
                    dest_path = UPLOADS_DIR / save_name
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            with open(dest_path, "wb") as f:
                                f.write(payload)
                            saved_attachments.append({
                                "file_name": clean_fn,
                                "file_path": str(dest_path),
                                "size_bytes": len(payload)
                            })
                    except Exception as ex:
                        print(f"[IMAP] Error saving attachment {clean_fn}: {ex}")

            # Handle body parts (skip non-inline attachments)
            if "attachment" not in content_disposition.lower():
                if content_type == "text/plain" and not body_text:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="replace")
                    except Exception:
                        pass
                elif content_type == "text/html" and not html_text:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        html_text = payload.decode(charset, errors="replace")
                    except Exception:
                        pass
    else:
        # Non-multipart message
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body_text = payload.decode(charset, errors="replace")
        except Exception:
            body_text = str(msg.get_payload())

    final_body = body_text.strip()
    if not final_body and html_text:
        # Simple HTML tag stripping
        clean_html = re.sub(r'<style.*?</style>', '', html_text, flags=re.DOTALL)
        clean_html = re.sub(r'<script.*?</script>', '', clean_html, flags=re.DOTALL)
        clean_html = re.sub(r'<[^>]+>', ' ', clean_html)
        final_body = " ".join(clean_html.split()).strip()

    return {
        "body": final_body,
        "attachments": saved_attachments
    }


def parse_email_message(msg: email.message.Message) -> Dict[str, Any]:
    """Parse raw email message into structured business item."""
    # From header
    raw_from = msg.get("From", "")
    decoded_from = decode_mime_words(raw_from)
    real_name, sender_email = parseaddr(decoded_from)
    sender_name = real_name if real_name else (sender_email.split('@')[0] if sender_email else "Unknown Sender")

    # Subject header
    raw_subject = msg.get("Subject", "No Subject")
    subject = decode_mime_words(raw_subject) or "No Subject"

    # Date header
    raw_date = msg.get("Date", "")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if raw_date:
        try:
            parsed_dt = parsedate_to_datetime(raw_date)
            date_str = parsed_dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(raw_date)[:30]

    # Message-ID
    message_id = msg.get("Message-ID", "").strip()

    # Extract Body & Attachments
    extracted = extract_email_body_and_attachments(msg)

    return {
        "message_id": message_id,
        "sender": sender_name,
        "sender_email": sender_email,
        "subject": subject,
        "date": date_str,
        "body": extracted["body"],
        "attachments": extracted["attachments"]
    }


def fetch_emails_from_imap(max_count: int = 15, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Connects to IMAP server, searches for new or recent messages, classifies them,
    and inserts non-duplicate records into the database.
    """
    creds = get_imap_credentials()
    if not creds["is_configured"]:
        return {
            "status": "not_configured",
            "synced_count": 0,
            "message": "IMAP credentials not configured in .env. Please set IMAP_USER and IMAP_PASSWORD (or SMTP_USER and SMTP_PASSWORD)."
        }

    host = creds["host"]
    port = creds["port"]
    user = creds["user"]
    password = creds["password"]
    folder = creds["folder"]

    mail = None
    session = SessionLocal()
    try:
        # 1. Connect over SSL
        mail = imaplib.IMAP4_SSL(host, port, timeout=20)
        mail.login(user, password)
        
        # 2. Select mailbox folder
        status, count_data = mail.select(folder, readonly=False)
        if status != "OK":
            return {"status": "error", "message": f"Could not open IMAP folder: {folder}"}

        total_msgs = 0
        if count_data and count_data[0]:
            try:
                total_msgs = int(count_data[0].decode() if isinstance(count_data[0], bytes) else count_data[0])
            except Exception:
                total_msgs = 0

        # 3. Search: Prefer UNSEEN; if none, grab recent messages via direct sequence range
        search_status, msg_ids = mail.search(None, "UNSEEN")
        id_list = msg_ids[0].split() if search_status == "OK" and msg_ids[0] else []

        if not id_list and total_msgs > 0:
            # Direct sequence numbers: instantaneous, zero latency
            start_seq = max(1, total_msgs - max_count + 1)
            id_list = [str(i).encode() for i in range(start_seq, total_msgs + 1)]
        else:
            id_list = id_list[-max_count:]

        if not id_list:
            return {
                "status": "success",
                "synced_count": 0,
                "message": f"Inbox checked ({user}). No new messages found."
            }

        # 4. Fetch and process messages (oldest to newest so newest gets latest ID)
        added_count = 0
        for m_id in id_list:
            res, data = mail.fetch(m_id, "(RFC822)")
            if res != "OK" or not data or not data[0]:
                continue

            raw_email = data[0][1]
            if not isinstance(raw_email, (bytes, bytearray)):
                continue

            msg = email.message_from_bytes(raw_email)
            parsed = parse_email_message(msg)

            # Avoid duplicates by checking existing records with same subject and sender_email or date
            existing = session.query(EmailItem).filter(
                EmailItem.subject == parsed["subject"],
                EmailItem.sender_email == parsed["sender_email"],
                EmailItem.date == parsed["date"]
            ).first()

            if not existing:
                classified = classify_email(parsed["sender"], parsed["subject"], parsed["body"], parsed.get("attachments", []))
                
                new_item = EmailItem(
                    user_id=user_id,
                    sender=parsed["sender"],
                    sender_email=parsed["sender_email"],
                    subject=parsed["subject"],
                    date=parsed["date"],
                    raw_body=parsed["body"],
                    summary=classified.get("summary", parsed["subject"]),
                    category=classified.get("category", "General"),
                    priority=classified.get("priority", "medium"),
                    action_required=classified.get("action_required", "Review message"),
                    is_read=0
                )
                session.add(new_item)
                added_count += 1

                # If an invoice PDF attachment was downloaded, trigger invoice extraction
                for att in parsed["attachments"]:
                    if att["file_name"].lower().endswith(".pdf"):
                        try:
                            from backend.services.invoice_extractor import extract_invoice_data, save_invoice_to_db
                            inv_data = extract_invoice_data(att["file_path"], att["file_name"])
                            inv_data["notes"] = f"Auto-ingested from email: '{parsed['subject']}' from {parsed['sender']}"
                            save_invoice_to_db(inv_data, att["file_name"], att["file_path"])
                            print(f"[IMAP] Auto-created invoice from email attachment: {att['file_name']}")
                            # Update email item with direct invoice details
                            new_item.category = "Vendor Invoice"
                            new_item.priority = "high"
                            new_item.action_required = f"Review invoice #{inv_data.get('invoice_number', '')} (₹{inv_data.get('total_amount', 0):,.2f}) and schedule payment"
                        except Exception as inv_err:
                            print(f"[IMAP] Could not auto-process attachment invoice {att['file_name']}: {inv_err}")

        session.commit()
        sync_state.total_synced_count += added_count
        
        msg_str = (
            f"Successfully checked {user}. Ingested and categorized {added_count} new communications."
            if added_count > 0
            else f"Inbox checked ({user}). All {len(id_list)} recent messages are already up-to-date."
        )

        return {
            "status": "success",
            "synced_count": added_count,
            "message": msg_str
        }

    except imaplib.IMAP4.error as imap_err:
        err_msg = str(imap_err)
        if "authentication failed" in err_msg.lower() or "invalid credentials" in err_msg.lower():
            hint = "Authentication failed. For Gmail, generate a 16-character App Password at myaccount.google.com/apppasswords."
            return {"status": "auth_error", "message": f"{hint} ({err_msg})"}
        return {"status": "error", "message": f"IMAP Error: {err_msg}"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": f"Failed to sync inbox: {str(e)}"}
    finally:
        session.close()
        if mail:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass


def run_imap_sync_cycle():
    """Execute a single sync cycle and update state metrics."""
    now = datetime.now()
    sync_state.last_sync_time = now
    creds = get_imap_credentials()
    interval_secs = creds["interval_minutes"] * 60
    sync_state.next_sync_time = now + timedelta(seconds=interval_secs)

    if not creds["is_configured"]:
        sync_state.last_status = "waiting_for_credentials"
        sync_state.last_message = "IMAP credentials not configured in .env. Waiting for IMAP_USER and IMAP_PASSWORD."
        return

    sync_state.last_status = "syncing"
    res = fetch_emails_from_imap(max_count=15)
    sync_state.last_status = res.get("status", "unknown")
    sync_state.last_message = res.get("message", "")
    if res.get("status") in ["error", "auth_error"]:
        sync_state.last_error = res.get("message")
        print(f"[IMAP Auto-Sync Warning] {res.get('message')}")
    else:
        sync_state.last_error = None
        print(f"[IMAP Auto-Sync] {res.get('message')}")


def scheduler_worker_loop():
    """Background worker daemon running every N minutes (default 5 mins)."""
    print("[IMAP Scheduler] Background worker loop started.")
    
    # Run first sync 5 seconds after startup
    time.sleep(5)
    
    while not sync_state.stop_event.is_set():
        try:
            run_imap_sync_cycle()
        except Exception as e:
            sync_state.last_status = "error"
            sync_state.last_error = str(e)
            print(f"[IMAP Scheduler Error] Unexpected cycle error: {e}")

        # Sleep for the configured interval (checking stop_event every 2 seconds for clean shutdown)
        creds = get_imap_credentials()
        interval_secs = creds["interval_minutes"] * 60
        elapsed = 0
        while elapsed < interval_secs and not sync_state.stop_event.is_set():
            time.sleep(2)
            elapsed += 2

    print("[IMAP Scheduler] Background worker loop cleanly stopped.")


def start_imap_scheduler():
    """Start the periodic IMAP sync worker thread if not already running."""
    if sync_state.is_running:
        return

    sync_state.stop_event.clear()
    sync_state.is_running = True
    sync_state.worker_thread = threading.Thread(target=scheduler_worker_loop, daemon=True, name="IMAP-Scheduler")
    sync_state.worker_thread.start()
    print("[IMAP Scheduler] Initialized background worker (5-minute timer).")


def stop_imap_scheduler():
    """Signal background worker to stop cleanly."""
    if not sync_state.is_running:
        return
    sync_state.stop_event.set()
    sync_state.is_running = False
    print("[IMAP Scheduler] Stop signal sent.")


def get_imap_status_summary() -> Dict[str, Any]:
    """Return status summary for frontend dashboard & integrations display."""
    creds = get_imap_credentials()
    return {
        "enabled": creds["is_configured"],
        "is_running": sync_state.is_running,
        "host": creds["host"],
        "user": creds["user"],
        "interval_minutes": creds["interval_minutes"],
        "last_sync_time": sync_state.last_sync_time.isoformat() if sync_state.last_sync_time else None,
        "next_sync_time": sync_state.next_sync_time.isoformat() if sync_state.next_sync_time else None,
        "last_status": sync_state.last_status,
        "last_message": sync_state.last_message,
        "last_error": sync_state.last_error,
        "total_synced_count": sync_state.total_synced_count
    }

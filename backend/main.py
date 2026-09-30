import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.config import BASE_DIR, UPLOADS_DIR, SAMPLES_DIR, DEFAULT_SETTINGS
from backend.database import init_db, get_db, get_all_settings, update_settings, IS_POSTGRES
from backend.models import User, Invoice
from backend.auth import get_current_user_optional
from backend.routers.auth_router import router as auth_router
from backend.routers.integrations_router import router as integrations_router
from backend.services.invoice_extractor import extract_invoice_data, save_invoice_to_db
from backend.services.mis_service import parse_spreadsheet, save_transactions_to_db, generate_mis_report
from backend.services.email_summarizer import process_and_save_emails, generate_morning_briefing
from backend.services.compliance_service import get_compliance_status, generate_ca_compliance_email
from backend.services.gemini_service import ask_assistant_with_gemini, is_gemini_active
from backend.services.local_ai_service import is_local_ai_available
from backend.services.date_query_helper import parse_period_from_query, query_period_financials
from backend.services.comms_service import generate_payment_reminder

# Initialize Database tables
init_db()

app = FastAPI(
    title="PattuBook Back Office Assistant",
    description="Unified intelligent back office system for Indian small businesses & retailers with PostgreSQL/SQLite, JWT Auth, and Cross-Platform Integrations.",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount modular routers
app.include_router(auth_router)
app.include_router(integrations_router)

@app.on_event("startup")
def startup_event():
    # Only start global IMAP background worker if explicitly enabled in environment
    if os.getenv("ENABLE_GLOBAL_IMAP_SCHEDULER", "false").lower() == "true":
        try:
            from backend.services.imap_service import start_imap_scheduler
            start_imap_scheduler()
        except Exception as e:
            print(f"[Startup Warning] Could not start IMAP background scheduler: {e}")

@app.on_event("shutdown")
def shutdown_event():
    try:
        from backend.services.imap_service import stop_imap_scheduler
        stop_imap_scheduler()
    except Exception as e:
        print(f"[Shutdown Warning] Could not stop IMAP background scheduler: {e}")


# --- MODELS ---
class SettingsPayload(BaseModel):
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None
    ca_email: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ai_provider: Optional[str] = None
    local_ai_model: Optional[str] = None
    local_ai_endpoint: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[str] = None
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    imap_sync_interval: Optional[str] = None

class ReminderRequest(BaseModel):
    customer_name: str
    invoice_number: str
    amount: float
    due_date: str
    phone: Optional[str] = ""
    tone: Optional[str] = "professional"

class ManualEmailRequest(BaseModel):
    sender: str
    sender_email: Optional[str] = ""
    subject: str
    body: str

class AssistantChatRequest(BaseModel):
    message: str
    store_context: Optional[Dict[str, Any]] = None

# --- ROUTES ---

@app.get("/api/status")
def get_status():
    local_status = is_local_ai_available()
    settings = get_all_settings()
    active_prov = settings.get("ai_provider", "local")
    return {
        "status": "online",
        "system": "PattuBook Back Office Assistant",
        "version": "2.0.0",
        "database": {
            "engine": "PostgreSQL (Railway Production)" if IS_POSTGRES else "SQLite (Local Dev)",
            "is_postgres": IS_POSTGRES,
            "connected": True
        },
        "ai": {
            "active_provider": active_prov,
            "local_ai": local_status,
            "gemini_active": is_gemini_active(),
            "model": local_status.get("active_model", "gemma2:2b") if active_prov == "local" else "gemini-2.5-flash"
        },
        "integrations": ["Google Calendar", "Gmail", "WhatsApp", "Tally Prime"]
    }

@app.get("/api/system/local-ai-status")
def api_get_local_ai_status():
    return is_local_ai_available()

# Settings
@app.get("/api/settings")
def api_get_settings(user: Optional[User] = Depends(get_current_user_optional)):
    if not user:
        return {
            "business_name": "My Store",
            "owner_name": "Guest / Demo Mode",
            "gstin": "",
            "phone": "",
            "email": "",
            "upi_id": "",
            "ca_email": "",
            "currency_symbol": "₹",
            "ai_provider": "local"
        }
    settings = get_all_settings()
    # Overlay user profile details
    settings["business_name"] = user.business_name or "My Business"
    settings["owner_name"] = user.full_name or "Business Owner"
    settings["gstin"] = user.gstin or ""
    settings["phone"] = user.phone or ""
    settings["email"] = user.email or ""
    settings["upi_id"] = user.upi_id or ""
    settings["ca_email"] = user.ca_email or ""
    return settings

@app.post("/api/settings")
def api_update_settings(payload: SettingsPayload, user: Optional[User] = Depends(get_current_user_optional)):
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    if user:
        conn = get_db()
        cursor = conn.cursor()
        if "business_name" in updates:
            cursor.execute("UPDATE users SET business_name = ? WHERE id = ?", (updates["business_name"], user.id))
        if "owner_name" in updates:
            cursor.execute("UPDATE users SET full_name = ? WHERE id = ?", (updates["owner_name"], user.id))
        if "gstin" in updates:
            cursor.execute("UPDATE users SET gstin = ? WHERE id = ?", (updates["gstin"], user.id))
        if "phone" in updates:
            cursor.execute("UPDATE users SET phone = ? WHERE id = ?", (updates["phone"], user.id))
        if "upi_id" in updates:
            cursor.execute("UPDATE users SET upi_id = ? WHERE id = ?", (updates["upi_id"], user.id))
        if "ca_email" in updates:
            cursor.execute("UPDATE users SET ca_email = ? WHERE id = ?", (updates["ca_email"], user.id))
        conn.commit()
        conn.close()
    else:
        update_settings(updates)
    return {"message": "Settings saved successfully", "settings": api_get_settings(user)}

# Invoices
@app.get("/api/invoices")
def api_get_invoices(user: Optional[User] = Depends(get_current_user_optional)):
    if not user:
        return []
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE user_id = ? ORDER BY id DESC", (user.id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/invoices/upload")
async def api_upload_invoice(file: UploadFile = File(...), user: Optional[User] = Depends(get_current_user_optional)):
    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    data = extract_invoice_data(str(file_path), file.filename)
    user_id = user.id if user else None
    inv_id = save_invoice_to_db(data, file.filename, str(file_path), user_id=user_id)

    data["id"] = inv_id
    return {"message": "Invoice processed successfully", "data": data}

@app.post("/api/invoices/process-sample")
def api_process_sample_invoice(filename: str = Form(...), user: Optional[User] = Depends(get_current_user_optional)):
    sample_path = SAMPLES_DIR / filename
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample invoice not found")
        
    data = extract_invoice_data(str(sample_path), filename)
    user_id = user.id if user else None
    inv_id = save_invoice_to_db(data, filename, str(sample_path), user_id=user_id)
    data["id"] = inv_id
    return {"message": f"Sample invoice {filename} extracted successfully", "data": data}

@app.put("/api/invoices/{inv_id}/status")
def api_toggle_invoice_status(inv_id: int, status: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_number, vendor_name, total_amount FROM invoices WHERE id = ?", (inv_id,))
    inv = cursor.fetchone()
    
    cursor.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, inv_id))
    
    if inv:
        txn_status = "settled" if status.lower() == "paid" else "pending"
        cursor.execute(
            "UPDATE transactions SET status = ? WHERE reference_no = ? OR (party_name = ? AND amount = ?)",
            (txn_status, inv["invoice_number"], inv["vendor_name"], inv["total_amount"])
        )
    
    conn.commit()
    conn.close()
    return {"message": f"Invoice status updated to {status}"}

@app.delete("/api/invoices/{inv_id}")
def api_delete_invoice(inv_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_number, vendor_name, total_amount FROM invoices WHERE id = ?", (inv_id,))
    inv = cursor.fetchone()
    if inv:
        cursor.execute(
            "DELETE FROM transactions WHERE reference_no = ? OR (party_name = ? AND amount = ?)",
            (inv["invoice_number"], inv["vendor_name"], inv["total_amount"])
        )
    cursor.execute("DELETE FROM invoices WHERE id = ?", (inv_id,))
    conn.commit()
    conn.close()
    return {"message": "Invoice deleted"}

# MIS & Analytics
@app.get("/api/mis/report")
def api_get_mis_report(user: Optional[User] = Depends(get_current_user_optional)):
    return generate_mis_report(user_id=user.id if user else None)

@app.post("/api/mis/upload")
async def api_upload_spreadsheet(file: UploadFile = File(...), user: Optional[User] = Depends(get_current_user_optional)):
    dest_path = UPLOADS_DIR / file.filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    records = parse_spreadsheet(str(dest_path))
    stats = save_transactions_to_db(records, user_id=user.id if user else None)
    if stats["inserted"] > 0:
        msg = f"Processed {stats['inserted']} new transaction entries ({stats['skipped']} existing skipped)."
    else:
        msg = f"All {stats['skipped']} transactions in this spreadsheet are already recorded. No duplicates added."
        
    return {
        "message": msg,
        "count": stats["inserted"],
        "skipped": stats["skipped"],
        "total": stats["total"]
    }

@app.post("/api/mis/load-sample")
def api_load_sample_ledger(user: Optional[User] = Depends(get_current_user_optional)):
    sample_path = SAMPLES_DIR / "retail_sales_september.xlsx"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample excel not found")
    records = parse_spreadsheet(str(sample_path))
    stats = save_transactions_to_db(records, user_id=user.id if user else None)
    return {
        "message": f"Loaded {stats['inserted']} sample transactions ({stats['skipped']} skipped)",
        "count": stats["inserted"],
        "skipped": stats["skipped"]
    }

# Emails & Morning Briefing
@app.get("/api/emails")
def api_get_emails(user: Optional[User] = Depends(get_current_user_optional)):
    if not user:
        return []
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emails WHERE user_id = ? ORDER BY date DESC, id DESC", (user.id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.get("/api/emails/briefing")
def api_get_morning_briefing(user: Optional[User] = Depends(get_current_user_optional)):
    return generate_morning_briefing(user_id=user.id if user else None)

@app.post("/api/emails/add")
def api_add_email(req: ManualEmailRequest, user: Optional[User] = Depends(get_current_user_optional)):
    process_and_save_emails([{
        "sender": req.sender,
        "sender_email": req.sender_email or "",
        "subject": req.subject,
        "body": req.body,
        "user_id": user.id if user else None
    }])
    return {"message": "Email ingested and categorized successfully"}

# Compliance Calendar
@app.get("/api/compliance/list")
def api_get_compliance_list():
    return get_compliance_status()

@app.get("/api/compliance/draft-email")
def api_get_compliance_email(code: str = "GSTR_3B"):
    return generate_ca_compliance_email(code)

# Communications & Reminders
@app.post("/api/comms/generate-reminder")
def api_generate_reminder(req: ReminderRequest):
    return generate_payment_reminder(
        customer_name=req.customer_name,
        invoice_number=req.invoice_number,
        amount=req.amount,
        due_date=req.due_date,
        phone=req.phone or "",
        tone=req.tone or "professional"
    )

# Gemini Interactive Assistant Chat
@app.post("/api/assistant/chat")
def api_assistant_chat(req: AssistantChatRequest, user: Optional[User] = Depends(get_current_user_optional)):
    settings = get_all_settings()
    ctx = req.store_context or {}
    if not ctx:
        ctx = {
            "business_name": (user.business_name if user and user.business_name else settings.get("business_name", "Our Store")),
            "owner_name": (user.full_name if user and user.full_name else settings.get("owner_name", "Proprietor")),
            "gstin": (user.gstin if user and user.gstin else settings.get("gstin", "")),
            "upi_id": (user.upi_id if user and user.upi_id else settings.get("upi_id", ""))
        }
    
    # Enrich with live real-time MIS metrics
    try:
        mis = generate_mis_report(skip_commentary=True, user_id=user.id if user else None)
        ctx["total_sales"] = mis.get("total_sales", 0.0)
        ctx["total_expenses"] = mis.get("total_expenses", 0.0)
        ctx["net_cash_flow"] = mis.get("net_cash_flow", 0.0)
        ctx["total_receivables"] = mis.get("total_receivables", 0.0)
        ctx["top_debtors"] = mis.get("top_debtors", [])
        ctx["aging"] = mis.get("aging", {})
    except Exception as e:
        print(f"[AssistantChat] MIS metrics enrich error: {e}")

    # Enrich with live unpaid invoices & payables (bills user owes to vendors)
    try:
        if user:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT vendor_name, customer_name, invoice_number, total_amount, due_date, status, invoice_type FROM invoices WHERE user_id = ? AND status != 'Paid' ORDER BY id DESC LIMIT 20", (user.id,))
            unpaid = [dict(r) for r in cursor.fetchall()]
            conn.close()
        else:
            unpaid = []

        payables = [inv for inv in unpaid if inv.get("invoice_type") == "purchase" or not inv.get("invoice_type")]
        total_payables = sum(p.get("total_amount", 0.0) for p in payables)
        
        ctx["total_payables"] = round(total_payables, 2)
        ctx["unpaid_invoices_summary"] = [
            {
                "party": inv.get("vendor_name") or inv.get("customer_name") or "Vendor",
                "invoice_number": inv.get("invoice_number"),
                "amount": inv.get("total_amount"),
                "due_date": inv.get("due_date"),
                "type": "Supplier Bill (Payable/Debt)" if (inv.get("invoice_type") == "purchase" or not inv.get("invoice_type")) else "Customer Bill (Receivable)"
            }
            for inv in unpaid[:10]
        ]
    except Exception as e:
        print(f"[AssistantChat] Invoices enrich error: {e}")

    # Check if the query asks about a specific date or period (e.g. 16-09-2020, September 2020)
    try:
        period_info = parse_period_from_query(req.message)
        if period_info:
            conn = get_db()
            period_data = query_period_financials(period_info, conn)
            conn.close()
            if period_data:
                ctx["queried_period"] = period_data
    except Exception as e:
        print(f"[AssistantChat] Period query enrich error: {e}")

    reply = ask_assistant_with_gemini(req.message, ctx)
    return {"reply": reply}

# Production Data Management: Purge Dummy / Test Data
@app.post("/api/system/reset-data")
def api_reset_data():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM invoices")
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM emails")
    conn.commit()
    conn.close()
    return {"message": "All operational invoices, transactions, and email records have been purged successfully."}

# Samples List
@app.get("/api/samples/list")
def api_list_samples():
    files = []
    if SAMPLES_DIR.exists():
        for f in SAMPLES_DIR.iterdir():
            files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "type": "pdf" if f.name.endswith(".pdf") else ("excel" if f.name.endswith(".xlsx") else "file")
            })
    return files

# Serve static frontend files
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/manifest.json")
def serve_manifest():
    manifest_file = FRONTEND_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(str(manifest_file), media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/sw.js")
def serve_service_worker():
    sw_file = FRONTEND_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(
            str(sw_file),
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="sw.js not found")

@app.get("/login")
@app.get("/signup")
@app.get("/auth")
def serve_auth_page():
    auth_file = FRONTEND_DIR / "login.html"
    if auth_file.exists():
        return FileResponse(str(auth_file))
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Login page initializing."}

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Back Office Assistant API is running. Frontend static directory initializing."}

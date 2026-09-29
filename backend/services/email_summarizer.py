import re
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database import get_db, get_all_settings

def clean_email_text(raw: str) -> str:
    """Strip HTML markup, scripts, styles and extraneous whitespaces."""
    if not raw:
        return ""
    text = re.sub(r'<style.*?</style>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split())

def classify_email(sender: str, subject: str, body: str, attachments: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Classify email category, priority, and extracted action items using instant heuristics."""
    clean_body = clean_email_text(body)
    clean_subject = clean_email_text(subject)
    clean_sender = clean_email_text(sender)
    search_text = f"{clean_sender} {clean_subject} {clean_body}".lower()
    
    has_pdf_or_image_att = bool(
        attachments and any(
            str(a.get("file_name", "") if isinstance(a, dict) else a).lower().endswith((".pdf", ".png", ".jpg", ".jpeg"))
            for a in attachments
        )
    )

    category = None
    priority = "medium"
    action_required = "Review message"
    
    # 1. Account & Security Alerts
    if re.search(r'\b(security alert|app password|sign-in|verification code|2-step verification|unauthorized access|login alert|password reset)\b', search_text):
        category = "Security Alert"
        priority = "high"
        action_required = "Review account security activity"

    # 2. Bank Credit / Debit alerts & Loan Repayment
    elif re.search(r'\b(loan repayment|repayment of your loan|loan reminder|emi reminder|loan emi)\b', search_text):
        category = "Bank Alert"
        priority = "high"
        action_required = "Verify bank balance for scheduled loan EMI repayment"

    elif re.search(r'\b(credited|debited|neft|rtgs|imps|upi txn|hdfc bank|sbi alert|icici bank|axis bank|account credited)\b', search_text):
        category = "Bank Alert"
        priority = "high" if re.search(r'\b(debited|credited)\b', search_text) else "medium"
        action_required = "Reconcile with bank passbook and update ledger"
        
    # 3. Statutory / GST / Tax alerts
    elif re.search(r'\b(gst|gstin|gstr-1|gstr-3b|income tax|challan|e-way bill|cbic|advance tax|tds return)\b', search_text):
        category = "Statutory / GST"
        priority = "high"
        action_required = "Forward to Chartered Accountant (CA) or verify filing"

    # 4. Vendor Payment Demand / Overdue Bills
    elif re.search(r'\b(payment reminder|overdue invoice|outstanding payment|pending bill|pay immediately|due date crossed|process the payment|payment of goods|payment for the goods|kindly process the payment|payment due|clear the bill)\b', search_text):
        category = "Payment Demand"
        priority = "high"
        action_required = "Verify supplier invoice and schedule payment or confirm clearance"

    # 5. Vendor Invoices & Bills
    elif (
        has_pdf_or_image_att
        or re.search(r'\b(attached invoice|invoice attached|tax invoice|bill of supply|invoice copy|purchase bill|find the attached invoice|invoice for your reference|vendor bill|supplier invoice|attached bill|bill attached)\b', search_text)
        or (re.search(r'\binvoice\b', search_text) and re.search(r'\b(payment|bill|purchased|goods|supplier|vendor)\b', search_text))
    ):
        category = "Vendor Invoice"
        priority = "high" if any(k in search_text for k in ["payment", "due", "pay", "pending", "attached"]) else "medium"
        action_required = "Review attached vendor bill and verify payment clearance"

    # 6. Logistics / Dispatch
    elif re.search(r'\b(dispatch|consignment|lr copy|courier|v-trans|tci express|shipped|out for delivery)\b', search_text):
        category = "Vendor Dispatch"
        priority = "medium"
        action_required = "Notify godown/store manager to receive consignment and inspect goods"

    # 7. Customer Order / Quotation
    elif re.search(r'\b(quotation|rate enquiry|rate inquiry|price inquiry|bulk requirement)\b', search_text):
        category = "Customer Inquiry"
        priority = "medium"
        action_required = "Draft quotation / respond to pricing inquiry"

    summary = clean_body[:130].strip() if clean_body else clean_subject
    if summary and not summary.endswith('.'):
        summary += '...'

    if category:
        return {
            "category": category,
            "priority": priority,
            "action_required": action_required,
            "summary": summary or clean_subject
        }

    return {
        "category": "General",
        "priority": "low",
        "action_required": "Review when time permits",
        "summary": summary or clean_subject
    }

def process_and_save_emails(email_list: List[Dict[str, str]]):
    """Process a batch of incoming emails and save to database."""
    conn = get_db()
    cursor = conn.cursor()
    
    for em in email_list:
        classification = classify_email(em.get("sender", ""), em.get("subject", ""), em.get("body", ""))
        cursor.execute('''
            INSERT INTO emails (sender, sender_email, subject, date, raw_body, summary, category, priority, action_required)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            em.get("sender", "Unknown"),
            em.get("sender_email", ""),
            em.get("subject", "No Subject"),
            em.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
            em.get("body", ""),
            classification["summary"],
            classification["category"],
            classification["priority"],
            classification["action_required"]
        ))
    conn.commit()
    conn.close()

def generate_morning_briefing(user_id: Optional[int] = None) -> Dict[str, Any]:
    """Compile a synthesized Morning Briefing for the business owner using Gemini AI or fallback."""
    if not user_id:
        return {
            "headline": "Welcome to PattuBook! Sign in or register to view your daily communications & financial briefing.",
            "urgent_actions": [],
            "highlights": [],
            "total_emails": 0,
            "high_priority_count": 0
        }

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emails WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 20", (user_id,))
    emails = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    if not emails:
        return {
            "headline": "No unread communications today.",
            "urgent_actions": [],
            "highlights": [],
            "total_emails": 0,
            "high_priority_count": 0
        }

    high_priority = [e for e in emails if e.get("priority") == "high"]
    settings = get_all_settings()
    owner_name = settings.get("owner_name", "Business Owner")
    business_name = settings.get("business_name", "Our Business")

    real_urgent_actions = [
        {"id": e["id"], "sender": e["sender"], "subject": e["subject"], "action": e["action_required"], "category": e["category"]}
        for e in high_priority
    ]

    # Try Gemini AI synthesis for headline
    headline = f"Good morning, {owner_name}! Here is your operational briefing for {business_name} today."
    highlights = [
        f"**{e['category']}** from {e['sender']}: {e['summary']}"
        for e in emails[:6]
    ]

    try:
        from backend.services.gemini_service import generate_morning_briefing_with_gemini
        ai_brief = generate_morning_briefing_with_gemini(emails, {"high_priority_count": len(high_priority)})
        if ai_brief and isinstance(ai_brief, dict):
            if ai_brief.get("headline"):
                headline = ai_brief.get("headline")
            if ai_brief.get("highlights"):
                highlights = ai_brief.get("highlights")
    except Exception as e:
        print(f"[MorningBriefing] Gemini synthesis error, falling back: {e}")

    return {
        "headline": headline,
        "urgent_actions": real_urgent_actions,
        "highlights": highlights,
        "total_emails": len(emails),
        "high_priority_count": len(high_priority)
    }

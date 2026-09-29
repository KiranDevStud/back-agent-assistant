import os
import json
import re
from typing import Dict, Any, List, Optional
from backend.database import get_all_settings
from backend.services.local_ai_service import (
    is_local_ai_available,
    extract_invoice_with_local_ai,
    analyze_email_with_local_ai,
    generate_morning_briefing_with_local_ai,
    generate_mis_commentary_with_local_ai,
    generate_payment_reminder_with_local_ai,
    ask_assistant_with_local_ai
)

def get_ai_provider() -> str:
    """Return 'local' as the dedicated AI provider."""
    return "local"

def is_gemini_active() -> bool:
    """Gemini cloud is completely disabled."""
    return False

def get_model(model_name: str = ""):
    """Gemini cloud models are not used."""
    return None

def clean_json_response(text: str) -> str:
    """Clean markdown code fences from AI responses before JSON parsing."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

# --- 1. INVOICE EXTRACTION ---
def extract_invoice_with_gemini(raw_text: str, filename: str) -> Optional[Dict[str, Any]]:
    """Extract structured GST invoice details using 100% Local AI and offline heuristics."""
    return extract_invoice_with_local_ai(raw_text, filename)

# --- 2. EMAIL CLASSIFICATION & MORNING BRIEFING ---
def analyze_email_with_gemini(subject: str, sender: str, body: str) -> Optional[Dict[str, Any]]:
    """Analyze and categorize business emails using 100% Local AI."""
    return analyze_email_with_local_ai(subject, sender, body)

def generate_morning_briefing_with_gemini(emails: List[Dict[str, Any]], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesize daily executive morning digest using 100% Local AI."""
    return generate_morning_briefing_with_local_ai(emails, stats)

# --- 3. MIS FINANCIAL COMMENTARY ---
def generate_mis_commentary_with_gemini(metrics: Dict[str, Any]) -> Optional[str]:
    """Generate executive business commentary using 100% Local AI and financial heuristics."""
    return generate_mis_commentary_with_local_ai(metrics)

# --- 4. SMART PAYMENT REMINDERS ---
def generate_payment_reminder_with_gemini(
    customer_name: str,
    invoice_number: str,
    amount: float,
    due_date: str,
    store_name: str,
    upi_id: str,
    tone: str = "professional"
) -> Optional[Dict[str, str]]:
    """Draft tailored payment collection notices using 100% Local AI."""
    return generate_payment_reminder_with_local_ai(
        customer_name=customer_name,
        invoice_no=invoice_number,
        amount=amount,
        days_overdue=7,
        tone=tone,
        business_name=store_name,
        upi_id=upi_id
    )

# --- 5. INTERACTIVE BACK OFFICE ASSISTANT (CHAT / Q&A) ---
def ask_assistant_with_gemini(user_message: str, store_context: Optional[Dict[str, Any]] = None) -> str:
    """Interactive Back Office AI assistant running 100% locally and privately."""
    return ask_assistant_with_local_ai(user_message, store_context)

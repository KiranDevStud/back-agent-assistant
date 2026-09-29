import json
import os
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.database import get_all_settings

DEFAULT_ENDPOINT = "http://localhost:11434"
DEFAULT_MODEL = "gemma2:2b"

def get_local_ai_settings() -> Dict[str, str]:
    """Retrieve local AI configuration from database settings or environment."""
    try:
        settings = get_all_settings()
    except Exception:
        settings = {}
    return {
        "endpoint": settings.get("local_ai_endpoint", os.getenv("LOCAL_AI_ENDPOINT", DEFAULT_ENDPOINT)).rstrip("/"),
        "model": settings.get("local_ai_model", os.getenv("LOCAL_AI_MODEL", DEFAULT_MODEL)),
        "provider": settings.get("ai_provider", os.getenv("AI_PROVIDER", "local"))
    }

def ensure_ollama_running(endpoint: str = DEFAULT_ENDPOINT) -> bool:
    """Check if Ollama is running; if not, attempt to start it in the background."""
    try:
        req = urllib.request.Request(
            f"{endpoint}/api/tags",
            headers={"User-Agent": "PattuBook-Local", "ngrok-skip-browser-warning": "true"}
        )
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.status == 200
    except Exception:
        pass

    # Try starting Ollama in background on Windows
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        import time
        for _ in range(5):
            time.sleep(1)
            try:
                with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=2) as res:
                    if res.status == 200:
                        return True
            except Exception:
                continue
    except Exception as e:
        print(f"[LocalAIService] Could not auto-start ollama serve: {e}")

    return False

def is_local_ai_available() -> Dict[str, Any]:
    """Check if Ollama local AI server is active and return available models."""
    cfg = get_local_ai_settings()
    endpoint = cfg["endpoint"]
    try:
        req = urllib.request.Request(
            f"{endpoint}/api/tags",
            headers={"User-Agent": "PattuBook-Local", "ngrok-skip-browser-warning": "true"}
        )
        with urllib.request.urlopen(req, timeout=3) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                active_model = cfg["model"] if cfg["model"] in models else (models[0] if models else cfg["model"])
                return {
                    "available": True,
                    "endpoint": endpoint,
                    "models": models,
                    "active_model": active_model,
                    "provider": cfg["provider"]
                }
    except Exception as e:
        # Check if we can auto-start it
        if ensure_ollama_running(endpoint):
            return is_local_ai_available()
        return {
            "available": False,
            "endpoint": endpoint,
            "models": [],
            "active_model": cfg["model"],
            "provider": cfg["provider"],
            "error": str(e)
        }

def clean_json_fence(text: str) -> str:
    """Clean markdown code fences from model response."""
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def call_local_model(
    prompt: str,
    system_prompt: str = "",
    model_name: Optional[str] = None,
    json_mode: bool = False,
    timeout: int = 90,
    num_predict: int = 250
) -> Optional[str]:
    """Send prompt to local Ollama instance and return completion text."""
    cfg = get_local_ai_settings()
    endpoint = cfg["endpoint"]
    model = model_name or cfg["model"]

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "24h",
        "options": {
            "temperature": 0.2 if json_mode else 0.4,
            "num_predict": num_predict,
            "num_thread": 6,
            "num_ctx": 768
        }
    }
    if system_prompt:
        payload["system"] = system_prompt
    if json_mode:
        payload["format"] = "json"

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{endpoint}/api/generate",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PattuBook-Local",
                "ngrok-skip-browser-warning": "true"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            resp_data = json.loads(res.read().decode("utf-8"))
            return resp_data.get("response", "").strip()
    except Exception as e:
        print(f"[LocalAIService] Ollama call error with model {model}: {e}")
        return None

# ==============================================================================
# 1. LOCAL INVOICE EXTRACTION
# ==============================================================================
def extract_invoice_with_local_ai(raw_text: str, filename: str) -> Optional[Dict[str, Any]]:
    """Extract structured GST invoice data using local model."""
    system_prompt = (
        "You are an Indian GST invoice data extractor. "
        "Extract invoice details from text and return strictly valid JSON."
    )
    prompt = f"""Extract GST invoice details from this text:
Filename: {filename}
Text:
\"\"\"
{raw_text[:2500]}
\"\"\"

Return strictly valid JSON:
{{
  "invoice_number": "string",
  "invoice_type": "purchase",
  "vendor_name": "string",
  "customer_name": "string",
  "vendor_gstin": "15-char GSTIN string or empty",
  "buyer_gstin": "15-char GSTIN string or empty",
  "invoice_date": "DD-MM-YYYY",
  "due_date": "DD-MM-YYYY",
  "subtotal": 0.0,
  "cgst": 0.0,
  "sgst": 0.0,
  "igst": 0.0,
  "total_tax": 0.0,
  "total_amount": 0.0,
  "line_items": [
    {{
      "description": "item name",
      "quantity": 1,
      "rate": 0.0,
      "amount": 0.0
    }}
  ]
}}
"""
    raw_response = call_local_model(prompt, system_prompt=system_prompt, json_mode=True, timeout=10)
    if not raw_response:
        return None

    try:
        clean_txt = clean_json_fence(raw_response)
        data = json.loads(clean_txt)
        data["extraction_method"] = "local_ai_ollama"
        if not data.get("invoice_number"):
            data["invoice_number"] = f"INV-{datetime.now().strftime('%Y%m%d%H%M')}"
        return data
    except Exception as e:
        print(f"[LocalAIService] JSON parse failed on invoice: {e}")
        return None

# ==============================================================================
# 2. LOCAL EMAIL / MESSAGE CLASSIFICATION
# ==============================================================================
def analyze_email_with_local_ai(sender: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
    """Classify incoming business communications and extract action items."""
    system_prompt = (
        "You are an AI back office assistant for Indian business owners. "
        "Categorize communications and extract urgent action items in strictly valid JSON format."
    )
    prompt = f"""Analyze this store message:
Sender: {sender}
Subject: {subject}
Body: {body[:1500]}

Return strictly valid JSON:
{{
  "category": "Vendor Dispatch" | "Statutory / GST" | "Bank Alert" | "Customer Order" | "General Inquiry",
  "priority": "high" | "medium" | "low",
  "summary": "1 concise sentence summary in Indian business context",
  "action_required": "Exact immediate step the store owner or accountant must take"
}}
"""
    raw_response = call_local_model(prompt, system_prompt=system_prompt, json_mode=True, timeout=8, num_predict=50)
    if not raw_response:
        return None

    try:
        clean_txt = clean_json_fence(raw_response)
        return json.loads(clean_txt)
    except Exception as e:
        print(f"[LocalAIService] Email analysis JSON parse error: {e}")
        return None

# ==============================================================================
# 3. LOCAL MORNING BRIEFING DIGEST
# ==============================================================================
def generate_morning_briefing_with_local_ai(emails: List[Dict[str, Any]], stats: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesize daily executive morning briefing using local model."""
    system_prompt = (
        "You are an executive Chief of Staff for an Indian store owner. "
        "Produce an encouraging, professional, and actionable morning digest in valid JSON."
    )
    brief_data = [
        {"sender": e.get("sender"), "subject": e.get("subject"), "action": e.get("action_required")}
        for e in emails[:6]
    ]
    prompt = f"""Generate a store morning briefing:
Business Metrics: {json.dumps(stats)}
Recent Inbound Communications: {json.dumps(brief_data)}

Return strictly valid JSON:
{{
  "headline": "Empowering, concise morning greeting (e.g. Good morning! 2 priority vendor dispatches and GST filing today)",
  "actions": [
    "Clear, bulleted action item 1",
    "Clear, bulleted action item 2"
  ]
}}
"""
    raw_response = call_local_model(prompt, system_prompt=system_prompt, json_mode=True, timeout=6, num_predict=120)
    if not raw_response:
        return None

    try:
        clean_txt = clean_json_fence(raw_response)
        return json.loads(clean_txt)
    except Exception as e:
        print(f"[LocalAIService] Briefing JSON parse error: {e}")
        return None

# ==============================================================================
# 4. LOCAL MIS COMMENTARY & FINANCIAL HEALTH
# ==============================================================================
def synthesize_mis_commentary(metrics: Dict[str, Any]) -> str:
    sales = metrics.get('total_sales', 0.0)
    expenses = metrics.get('total_expenses', 0.0)
    net_cash = metrics.get('net_cash', 0.0)
    receivables = metrics.get('total_receivables', 0.0)
    debtors = metrics.get('top_debtors', [])
    
    margin = ((sales - expenses) / sales * 100) if sales > 0 else 0
    top_debtor = debtors[0].get('party_name', 'pending accounts') if debtors else "pending customer accounts"
    
    return (
        f"<div>• <b>Cash Velocity & Margins:</b> Recorded sales of ₹{sales:,.2f} against ₹{expenses:,.2f} expenses yields an operating margin of {margin:.1f}% (Net Cash: ₹{net_cash:,.2f}).</div>"
        f"<div>• <b>Working Capital & Debtors:</b> Market credit stands at ₹{receivables:,.2f}. Regular collection reminders for {top_debtor} will optimize cash conversion.</div>"
        f"<div>• <b>Treasury Recommendation:</b> Reconcile input tax credits (ITC) on all purchase bills and encourage instant UPI settlements for daily sales.</div>"
    )

def generate_mis_commentary_with_local_ai(metrics: Dict[str, Any]) -> str:
    """Generate concise financial takeaways from sales and expense figures."""
    system_prompt = (
        "You are an experienced Indian Chartered Financial Analyst and Retail Consultant. "
        "Analyze the business ledger figures and provide 3 HTML bullet points (<div>• ...</div>) of operational advice."
    )
    prompt = f"""Review these financial figures for our retail store:
• Total Sales Turnover: ₹{metrics.get('total_sales', 0):,.2f}
• Total Purchases & Expenses: ₹{metrics.get('total_expenses', 0):,.2f}
• Net Cash Position: ₹{metrics.get('net_cash', 0):,.2f}
• Customer Market Credit (Debtors): ₹{metrics.get('total_receivables', 0):,.2f}

Provide 3 bullet points (<div>• ...</div>) of sharp commentary:
• Cash Velocity & Margins
• Working Capital & Debtors
• Actionable Treasury Recommendation
Keep under 100 words."""

    res = call_local_model(prompt, system_prompt=system_prompt, json_mode=False, timeout=6, num_predict=120)
    if res and len(res.strip()) > 20:
        return res
    return synthesize_mis_commentary(metrics)

# ==============================================================================
# 5. LOCAL SMART PAYMENT REMINDERS
# ==============================================================================
def generate_payment_reminder_with_local_ai(
    customer_name: str,
    invoice_no: str,
    amount: float,
    days_overdue: int,
    tone: str,
    business_name: str,
    upi_id: str
) -> Dict[str, str]:
    """Draft customized payment reminders using local model."""
    system_prompt = (
        "You are a professional business communication assistant in India. "
        "Draft payment collection notices tailored for WhatsApp and formal Email."
    )
    prompt = f"""Draft a {tone} payment reminder:
Customer: {customer_name}
Invoice: {invoice_no or 'Outstanding Balance'}
Amount Due: ₹{amount:,.2f}
Days Overdue: {days_overdue} days
Store: {business_name}
UPI ID: {upi_id}

Return strictly valid JSON:
{{
  "subject": "Professional email subject line",
  "message": "Complete polite formal letter and payment request with UPI details",
  "whatsapp": "Concise friendly WhatsApp text with UPI handle"
}}
"""
    raw_response = call_local_model(prompt, system_prompt=system_prompt, json_mode=True, timeout=5, num_predict=100)
    if raw_response:
        try:
            clean_txt = clean_json_fence(raw_response)
            parsed = json.loads(clean_txt)
            subject = parsed.get("subject") or parsed.get("email_subject")
            message = parsed.get("message") or parsed.get("email_body") or parsed.get("whatsapp")
            whatsapp = parsed.get("whatsapp") or message
            if subject and message:
                return {
                    "subject": subject,
                    "message": message,
                    "whatsapp": whatsapp,
                    "email_subject": subject,
                    "email_body": message
                }
        except Exception:
            pass

    # High quality fallback template
    upi_part = f"\nKindly settle via UPI ID: {upi_id}" if upi_id else ""
    default_sub = f"Payment Reminder: Invoice #{invoice_no or 'Balance'} - {business_name}"
    default_msg = (
        f"Dear {customer_name},\n\n"
        f"This is a reminder regarding the outstanding balance of ₹{amount:,.2f} for your account with {business_name}.\n\n"
        f"Kindly process the payment at your earliest convenience.{upi_part}\n\n"
        f"Warm regards,\n{business_name}"
    )
    return {
        "subject": default_sub,
        "message": default_msg,
        "whatsapp": f"Namaste {customer_name}, gentle reminder regarding outstanding payment of ₹{amount:,.2f} due to {business_name}.{upi_part}\nThank you!",
        "email_subject": default_sub,
        "email_body": default_msg
    }

# ==============================================================================
# 6. LOCAL BACK OFFICE ASSISTANT CHAT
# ==============================================================================
def synthesize_store_fallback(user_message: str, ctx: Optional[Dict[str, Any]]) -> str:
    """Generate intelligent live database response when model is busy or times out."""
    if not ctx:
        return "I am currently running in offline local mode. No database records are loaded yet."
    
    # 1. Check if user asked about a specific date or period
    queried = ctx.get("queried_period") if ctx else None
    if queried:
        q_label = queried.get("label") or queried.get("iso", "selected date")
        q_sales = queried.get("total_sales", 0.0)
        q_exp = queried.get("total_expenses", 0.0)
        q_net = queried.get("net_profit", 0.0)
        q_items = queried.get("items", [])

        if not queried.get("has_data"):
            return f"According to your records, there were no sales or expense transactions recorded on {q_label}."

        lines = [
            f"Financials for {q_label}:",
            f"• Total Sales: ₹{q_sales:,.2f}",
            f"• Total Expenses: ₹{q_exp:,.2f}",
            f"• Net Profit / Cash Flow: ₹{q_net:,.2f}"
        ]
        if q_items:
            lines.append("\nTransaction Details:")
            for it in q_items[:6]:
                ttype = it.get('type', 'Item').capitalize()
                party = it.get('party_name') or it.get('category') or 'General'
                mode = it.get('payment_mode') or 'UPI'
                lines.append(f"• {ttype}: ₹{it.get('amount', 0):,.2f} - {party} ({mode})")
        return "\n".join(lines)

    msg = user_message.lower()
    payables = ctx.get("total_payables", 0.0)
    receivables = ctx.get("total_receivables", 0.0)
    sales = ctx.get("total_sales", 0.0)
    expenses = ctx.get("total_expenses", 0.0)
    cash = ctx.get("net_cash_flow", 0.0)
    unpaid = ctx.get("unpaid_invoices_summary", [])
    debtors = ctx.get("top_debtors", [])

    if any(w in msg for w in ["debt", "owe", "payable", "supplier", "vendor", "bills", "dues"]):
        if payables > 0:
            lines = [f"Based on your live store records, your total outstanding supplier debt is ₹{payables:,.2f}."]
            supplier_bills = [u for u in unpaid if "Supplier" in u.get("type", "")]
            if supplier_bills:
                lines.append("\nPending supplier bills:")
                for u in supplier_bills[:5]:
                    lines.append(f"• {u.get('party')}: ₹{u.get('amount', 0):,.2f} (Due: {u.get('due_date') or 'Immediate'})")
            return "\n".join(lines)
        else:
            return (
                f"Based on your live store database, you currently have ₹0.00 in outstanding supplier debt. "
                f"You do not owe any money to vendors at this moment.\n"
                f"(Customer receivables owed to your store: ₹{receivables:,.2f})"
            )

    if any(w in msg for w in ["receivable", "customer", "credit", "market debt", "who owes"]):
        if receivables > 0:
            lines = [f"Total customer receivables owed to your business: ₹{receivables:,.2f}."]
            if debtors:
                lines.append("\nTop customer balances:")
                for d in debtors[:5]:
                    lines.append(f"• {d.get('party_name')}: ₹{d.get('amount', 0):,.2f}")
            return "\n".join(lines)
        else:
            return "According to your records, there are ₹0.00 in outstanding customer receivables."

    if any(w in msg for w in ["sale", "revenue", "expense", "profit", "cash"]):
        return (
            f"Here is your current store financial snapshot:\n"
            f"• Total Sales: ₹{sales:,.2f}\n"
            f"• Total Expenses: ₹{expenses:,.2f}\n"
            f"• Net Cash Flow: ₹{cash:,.2f}"
        )

    return (
        f"Store Accounting Summary:\n"
        f"• Total Recorded Sales: ₹{sales:,.2f}\n"
        f"• Total Expenses: ₹{expenses:,.2f}\n"
        f"• Net Cash Flow: ₹{cash:,.2f}\n"
        f"• Outstanding Supplier Debt: ₹{payables:,.2f}\n"
        f"• Customer Receivables: ₹{receivables:,.2f}"
    )

def ask_assistant_with_local_ai(user_message: str, store_context: Optional[Dict[str, Any]] = None) -> str:
    """Answer conversational questions about store sales, invoices, and GST rules."""
    system_prompt = (
        "You are PattuBook, an intelligent Indian retail store back office assistant running locally. "
        "Use the provided Store Financial Snapshot to answer the owner's questions directly, accurately, and concisely. "
        "All currency values are in Indian Rupees (₹). Keep answers clear, direct, and under 100 words."
    )
    
    context_lines = []
    if store_context:
        # Check if user asked about a specific date or period
        queried = store_context.get("queried_period")
        if queried:
            q_label = queried.get("label") or queried.get("iso", "selected period")
            q_sales = queried.get("total_sales", 0.0)
            q_exp = queried.get("total_expenses", 0.0)
            q_net = queried.get("net_profit", 0.0)
            q_items = queried.get("items", [])
            
            if queried.get("has_data"):
                items_desc = ""
                if q_items:
                    items_desc = " (" + ", ".join([f"{it['type'].title()}: ₹{it['amount']:,.0f} for {it.get('party_name', it.get('category'))}" for it in q_items[:4]]) + ")"
                context_lines.append(f"*** EXACT DATE REQUESTED BY OWNER: {q_label} ***")
                context_lines.append(f"- Sales on {q_label}: ₹{q_sales:,.2f}")
                context_lines.append(f"- Expenses on {q_label}: ₹{q_exp:,.2f}")
                context_lines.append(f"- Net Profit on {q_label}: ₹{q_net:,.2f}{items_desc}")
                context_lines.append(f"CRITICAL INSTRUCTION: The user is specifically asking about {q_label}. You MUST answer with the exact sales (₹{q_sales:,.2f}) and expenses (₹{q_exp:,.2f}) for {q_label}. Do NOT quote lifetime total sales or total expenses.")
            else:
                context_lines.append(f"*** EXACT DATE REQUESTED BY OWNER: {q_label} ***")
                context_lines.append(f"- Sales on {q_label}: ₹0.00 (No transactions recorded in database)")
                context_lines.append(f"- Expenses on {q_label}: ₹0.00")
                context_lines.append(f"CRITICAL INSTRUCTION: State clearly that no transactions were recorded on {q_label}.")

        sales = store_context.get("total_sales", 0.0)
        expenses = store_context.get("total_expenses", 0.0)
        cash = store_context.get("net_cash_flow", 0.0)
        payables = store_context.get("total_payables", 0.0)
        receivables = store_context.get("total_receivables", 0.0)
        unpaid = store_context.get("unpaid_invoices_summary", [])
        debtors = store_context.get("top_debtors", [])
        
        context_lines.append(f"- Store: {store_context.get('business_name', 'My Store')}")
        context_lines.append(f"- Overall Lifetime Sales: ₹{sales:,.2f}")
        context_lines.append(f"- Overall Lifetime Expenses: ₹{expenses:,.2f}")
        context_lines.append(f"- Lifetime Net Cash Flow: ₹{cash:,.2f}")
        context_lines.append(f"- Total Debt / Money You Owe to Suppliers: ₹{payables:,.2f}")
        if unpaid:
            unpaid_str = ", ".join([f"{u.get('party')}: ₹{u.get('amount', 0):,.2f}" for u in unpaid[:5]])
            context_lines.append(f"- Unpaid Supplier Invoices: {unpaid_str}")
        else:
            context_lines.append("- Unpaid Supplier Invoices: None (No supplier debt)")
        context_lines.append(f"- Total Receivables / Money Customers Owe You: ₹{receivables:,.2f}")
        if debtors:
            debtors_str = ", ".join([f"{d.get('party_name')}: ₹{d.get('amount', 0):,.2f}" for d in debtors[:5]])
            context_lines.append(f"- Overdue Customers: {debtors_str}")

    context_str = "\n".join(context_lines)
    prompt = f"""Live Store Financial Snapshot:
{context_str}

Store Owner Question: {user_message}

Direct Answer:"""

    response = call_local_model(prompt, system_prompt=system_prompt, json_mode=False, timeout=30, num_predict=80)
    if response and len(response.strip()) > 5:
        return response

    return synthesize_store_fallback(user_message, store_context)

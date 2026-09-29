import urllib.parse
from typing import Dict, Any, List
from backend.database import get_db, get_all_settings

def generate_payment_reminder(
    customer_name: str,
    invoice_number: str,
    amount: float,
    due_date: str,
    phone: str = "",
    tone: str = "professional"
) -> Dict[str, str]:
    """Generate multi-tone payment reminder messages with embedded UPI quick-pay link."""
    settings = get_all_settings()
    biz_name = settings.get("business_name") or "Our Business"
    upi_id = settings.get("upi_id") or ""
    
    upi_pay_link = f"upi://pay?pa={upi_id}&pn={urllib.parse.quote(biz_name)}&am={amount:.2f}&tn=Inv_{invoice_number}&cu=INR" if upi_id else ""
    
    # Try Gemini AI reminder generation first
    subject = None
    msg = None
    try:
        from backend.services.gemini_service import generate_payment_reminder_with_gemini
        ai_reminder = generate_payment_reminder_with_gemini(
            customer_name=customer_name,
            invoice_number=invoice_number,
            amount=amount,
            due_date=due_date,
            store_name=biz_name,
            upi_id=upi_id,
            tone=tone
        )
        if ai_reminder and isinstance(ai_reminder, dict):
            subject = ai_reminder.get("subject") or ai_reminder.get("email_subject")
            msg = ai_reminder.get("message") or ai_reminder.get("email_body") or ai_reminder.get("whatsapp")
    except Exception as e:
        print(f"[CommsService] AI reminder error, using template: {e}")

    if not subject or not msg:
        if tone == "gentle":
            subject = f"Gentle Reminder: Invoice #{invoice_number} from {biz_name}"
            msg = f"""Hello {customer_name},

Hope you are doing well!

This is a gentle reminder regarding Invoice #{invoice_number} for ₹{amount:,.2f} due on {due_date}.

For quick settlement, you can pay directly via UPI:
{upi_pay_link or upi_id}
(UPI ID: {upi_id})

If you have already processed this payment, please disregard this note. Thank you for your business!

Warm regards,
{biz_name}"""

        elif tone == "firm":
            subject = f"OVERDUE NOTICE: Immediate Settlement Required - Invoice #{invoice_number}"
            msg = f"""ATTENTION: {customer_name}

Your payment of ₹{amount:,.2f} for Invoice #{invoice_number} was due on {due_date} and is currently OVERDUE.

Please arrange immediate settlement today to avoid suspension of credit terms and further delivery holds.

Instant UPI Payment Link:
{upi_pay_link or upi_id}
(UPI ID: {upi_id})

Kindly share the transaction UTR number once completed.

Sincerely,
Accounts Dept - {biz_name}"""

        elif tone == "hinglish":
            subject = f"Payment Reminder: Invoice #{invoice_number} - {biz_name}"
            msg = f"""Namaste {customer_name} ji,

Aapka bill #{invoice_number} ka amount ₹{amount:,.2f} pending hai (Due date: {due_date}).

Kripya time par clear kar dijiye taki aage ka dispatch seamlessly ho sake. Aap neeche diye gaye UPI link se direct pay kar sakte hain:

UPI Link: {upi_pay_link or upi_id}
(UPI ID: {upi_id})

Payment hone par screenshot ya UTR zaroor share karein. Dhanyawaad!

Regard,
{biz_name}"""

        else: # professional (default)
            subject = f"Payment Reminder: Invoice #{invoice_number} - {biz_name}"
            msg = f"""Dear {customer_name},

This is a reminder that payment for Invoice #{invoice_number} amounting to ₹{amount:,.2f} is scheduled for settlement by {due_date}.

Please process the payment through our registered UPI ID or direct bank transfer:
• UPI Payment Link: {upi_pay_link or upi_id}
• UPI ID: {upi_id}

Kindly forward the payment confirmation or reference number upon completion.

Thank you for your cooperation.

Best regards,
Finance Team
{biz_name}"""

    encoded_text = urllib.parse.quote(msg)
    clean_phone = "".join(filter(str.isdigit, phone)) if phone else ""
    wa_url = f"https://api.whatsapp.com/send?text={encoded_text}"
    if clean_phone:
        if not clean_phone.startswith("91") and len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
        wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

    mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&body={encoded_text}"

    return {
        "customer_name": customer_name,
        "invoice_number": invoice_number,
        "amount": amount,
        "due_date": due_date,
        "subject": subject,
        "message": msg,
        "tone": tone,
        "whatsapp_url": wa_url,
        "mailto_url": mailto_url,
        "upi_link": upi_pay_link
    }

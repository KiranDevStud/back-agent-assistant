from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.database import get_db, get_all_settings

def get_compliance_status() -> List[Dict[str, Any]]:
    """Retrieve all statutory compliance deadlines with live days countdown."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM compliance_records ORDER BY next_due_date ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    today = datetime.now().date()
    updated_records = []
    
    for r in rows:
        try:
            due = datetime.strptime(r["next_due_date"], "%Y-%m-%d").date()
            days_left = (due - today).days
        except Exception:
            days_left = 10
            
        if days_left < 0:
            urgency = "OVERDUE"
            badge = "danger"
        elif days_left <= 3:
            urgency = "CRITICAL"
            badge = "danger"
        elif days_left <= 7:
            urgency = "UPCOMING"
            badge = "warning"
        else:
            urgency = "ON_TRACK"
            badge = "success"
            
        r["days_left"] = days_left
        r["urgency"] = urgency
        r["badge"] = badge
        updated_records.append(r)
        
    return updated_records

def generate_ca_compliance_email(compliance_code: str, period_label: str = "") -> Dict[str, str]:
    """Generate ready-to-send draft email to Chartered Accountant."""
    settings = get_all_settings()
    biz_name = settings.get("business_name", "Our Business")
    owner_name = settings.get("owner_name", "Proprietor")
    gstin = settings.get("gstin", "27AAPCG1234F1Z8")
    ca_email = settings.get("ca_email", "ca.kapoorandassociates@gmail.com")
    
    now = datetime.now()
    month_name = now.strftime("%B %Y")
    
    conn = get_db()
    cursor = conn.cursor()
    # Compute quick sales & purchase stats from DB
    cursor.execute("SELECT SUM(amount) as sales FROM transactions WHERE type='sale'")
    row_sales = cursor.fetchone()
    total_sales = row_sales["sales"] or 0.0
    
    cursor.execute("SELECT SUM(subtotal) as inv_sub, SUM(total_tax) as inv_tax, SUM(total_amount) as inv_tot FROM invoices")
    row_inv = cursor.fetchone()
    inv_tax = row_inv["inv_tax"] or 0.0
    conn.close()

    if "GSTR_1" in compliance_code:
        subject = f"[GST Compliance] Outward Supplies / Sales Data for GSTR-1 ({month_name}) - {biz_name}"
        body = f"""Dear Sir/Madam,

Hope you are doing well.

Please find below the consolidated outward supplies (sales) details for {biz_name} (GSTIN: {gstin}) for filing GSTR-1 for the period {month_name}:

• Total Taxable Turnover: ₹{total_sales:,.2f}
• Estimated Outward GST: ₹{(total_sales * 0.18):,.2f}
• Total Active Customer Accounts: Reconciled

We have verified our sales register and attached the sales summary report. Kindly initiate the GSTR-1 draft and verify customer B2B invoice uploads so our clients can claim eligible ITC without delay.

Please let us know if any further invoices or debit/credit notes are needed.

Warm regards,
{owner_name}
{biz_name}
GSTIN: {gstin}
Phone: {settings.get('phone', '')}
"""
    elif "GSTR_3B" in compliance_code:
        subject = f"[GST Return & Challan] GSTR-3B Monthly Filing Data ({month_name}) - {biz_name}"
        body = f"""Dear Sir/Madam,

Please find attached our monthly sales & purchase registers for {biz_name} (GSTIN: {gstin}) for filing GSTR-3B for the month of {month_name}:

1. Total Outward Supplies (Sales): ₹{total_sales:,.2f}
2. Eligible Input Tax Credit (ITC from Purchase Invoices): ₹{inv_tax:,.2f}
3. Estimated Net GST Liability: ₹{max(0.0, (total_sales * 0.18) - inv_tax):,.2f}

Kindly reconcile the 2B statement on the GST Portal, compute the exact net cash payable challan amount (PMT-06), and share the challan details with us before the 20th deadline to avoid late fees and 18% interest.

Best regards,
{owner_name}
{biz_name}
GSTIN: {gstin}
"""
    else:
        subject = f"[Statutory Compliance Update] {compliance_code} Filing Data - {biz_name}"
        body = f"""Dear Sir/Madam,

Regarding our upcoming statutory compliance for {compliance_code}, we have consolidated our financial accounts and ledgers for {biz_name} (GSTIN: {gstin}).

Kindly advise on the necessary return preparation, due taxes, and required annexures.

Regards,
{owner_name}
{biz_name}
"""

    return {
        "recipient": ca_email,
        "subject": subject,
        "body": body
    }

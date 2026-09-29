import os
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from backend.config import SAMPLES_DIR
from backend.services.email_summarizer import process_and_save_emails
from backend.database import get_db

def generate_sample_pdf_invoice(filename: str, vendor_info: dict, items: list, inv_no: str, is_interstate: bool = False):
    """Generate a realistic Indian Tax Invoice PDF."""
    pdf_path = SAMPLES_DIR / filename
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "TAX INVOICE")
    
    # Vendor Block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 75, vendor_info["name"])
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 90, vendor_info["address"])
    c.drawString(50, height - 105, f"GSTIN: {vendor_info['gstin']}")
    c.drawString(50, height - 120, f"Email: {vendor_info['email']} | Phone: {vendor_info['phone']}")
    
    # Invoice Metadata (Right side)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 50, height - 75, f"Invoice No: {inv_no}")
    c.setFont("Helvetica", 9)
    inv_date = (datetime.now() - timedelta(days=5)).strftime("%d-%m-%Y")
    due_date = (datetime.now() + timedelta(days=10)).strftime("%d-%m-%Y")
    c.drawRightString(width - 50, height - 90, f"Date: {inv_date}")
    c.drawRightString(width - 50, height - 105, f"Due Date: {due_date}")
    c.drawRightString(width - 50, height - 120, f"Place of Supply: {'State Outside' if is_interstate else 'Maharashtra (27)'}")
    
    # Horizontal line
    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#334155"))
    c.line(50, height - 135, width - 50, height - 135)
    
    # Bill To
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 155, "Billed To:")
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 170, "Om Sai Traders & Enterprises")
    c.drawString(50, height - 185, "Shop #14, APMC Market Yard, Vashi, Navi Mumbai - 400703")
    c.drawString(50, height - 200, "GSTIN: 27AAPCG1234F1Z8")
    
    # Items Table Header
    y = height - 230
    c.setFillColor(colors.HexColor("#f1f5f9"))
    c.rect(50, y - 5, width - 100, 20, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(60, y, "Item Description")
    c.drawString(280, y, "HSN")
    c.drawString(340, y, "Qty")
    c.drawString(400, y, "Rate (₹)")
    c.drawRightString(width - 60, y, "Amount (₹)")
    
    # Line items
    y -= 25
    c.setFont("Helvetica", 9)
    subtotal = 0.0
    for item in items:
        amt = item["qty"] * item["rate"]
        subtotal += amt
        c.drawString(60, y, item["desc"])
        c.drawString(280, y, str(item.get("hsn", "8536")))
        c.drawString(340, y, str(item["qty"]))
        c.drawString(400, y, f"{item['rate']:,.2f}")
        c.drawRightString(width - 60, y, f"{amt:,.2f}")
        y -= 20
        
    c.line(50, y - 5, width - 50, y - 5)
    
    # Totals block
    y -= 25
    c.setFont("Helvetica", 9)
    c.drawString(320, y, "Sub Total:")
    c.drawRightString(width - 60, y, f"₹ {subtotal:,.2f}")
    
    if not is_interstate:
        cgst = round(subtotal * 0.09, 2)
        sgst = round(subtotal * 0.09, 2)
        total = round(subtotal + cgst + sgst, 2)
        
        y -= 18
        c.drawString(320, y, "CGST (9%):")
        c.drawRightString(width - 60, y, f"₹ {cgst:,.2f}")
        
        y -= 18
        c.drawString(320, y, "SGST (9%):")
        c.drawRightString(width - 60, y, f"₹ {sgst:,.2f}")
    else:
        igst = round(subtotal * 0.18, 2)
        total = round(subtotal + igst, 2)
        y -= 18
        c.drawString(320, y, "IGST (18%):")
        c.drawRightString(width - 60, y, f"₹ {igst:,.2f}")
        
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(320, y, "Grand Total:")
    c.drawRightString(width - 60, y, f"₹ {total:,.2f}")
    
    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(50, 40, "Thank you for your business. Terms: 15 Days payment credit. Subject to Mumbai Jurisdiction.")
    c.drawRightString(width - 50, 40, "Authorized Signatory: ___________________")
    
    c.showPage()
    c.save()
    return str(pdf_path)

def generate_sample_excel_ledger() -> str:
    """Generate sample retail sales & expense ledger (.xlsx)."""
    excel_path = SAMPLES_DIR / "retail_sales_september.xlsx"
    
    today = datetime.now()
    records = []
    
    parties = [
        ("Sharma Hardware Store", "sale", "Electrical Fittings", 34500, "pending"),
        ("Gupta Building Materials", "sale", "Cables & Wires", 58000, "settled"),
        ("Metro Tech Works", "sale", "Industrial Switches", 72000, "pending"),
        ("Walk-in Retail Counter", "sale", "Lighting Fixtures", 12500, "settled"),
        ("Kavita Interiors", "sale", "Designer Modular Switches", 41200, "pending"),
        ("Superfast Express Logistics", "expense", "Freight & Transport", 4800, "settled"),
        ("Apex Industrial Cables Ltd", "purchase", "Raw Material Copper Cables", 85000, "settled"),
        ("Maharashtra State Electricity", "expense", "Shop Utility Power", 6200, "settled"),
        ("Modern Packaging Ltd", "expense", "Cardboard Cartons", 3500, "settled"),
        ("Vikas Electrical Contractors", "sale", "Circuit Breakers (MCB)", 29000, "pending"),
        ("Walk-in Retail Counter", "sale", "LED Bulbs 9W", 8400, "settled"),
        ("Shree Ganesh Transporters", "expense", "Unloading Labor", 2200, "settled")
    ]
    
    for idx, (party, ttype, cat, amt, status) in enumerate(parties):
        txn_date = (today - timedelta(days=(12 - idx))).strftime("%Y-%m-%d")
        mode = "UPI" if idx % 2 == 0 else ("Credit" if status == "pending" else "Bank Transfer")
        records.append({
            "Date": txn_date,
            "Party Name": party,
            "Type": ttype,
            "Category": cat,
            "Amount": amt,
            "Payment Mode": mode,
            "Status": status
        })
        
    df = pd.DataFrame(records)
    df.to_excel(str(excel_path), index=False, engine="openpyxl")
    return str(excel_path)

def seed_sample_data_if_empty():
    """Seed sample PDFs, Excel ledger, and realistic emails."""
    # 1. Generate PDF 1: Sharma Electrical Supplies
    p1 = generate_sample_pdf_invoice(
        "Invoice_Sharma_Electricals_942.pdf",
        {
            "name": "Sharma Electrical & Industrial Supplies",
            "address": "Gala No 4, MIDC Industrial Estate, Andheri East, Mumbai 400093",
            "gstin": "27AAACS1827K1Z4",
            "email": "billing@sharmaelectricals.in",
            "phone": "+91 98210 99441"
        },
        [
            {"desc": "Havells 2.5 sq mm Copper House Wire 90m", "hsn": "8544", "qty": 15, "rate": 1850.0},
            {"desc": "Philips 20W LED Batten Tube Light Cool Day", "hsn": "8539", "qty": 40, "rate": 220.0},
            {"desc": "Schneider 16A Single Pole MCB C-Curve", "hsn": "8536", "qty": 50, "rate": 140.0}
        ],
        "INV-2024-942",
        is_interstate=False
    )
    
    # 2. Generate PDF 2: Apex Power Grid (Interstate IGST)
    p2 = generate_sample_pdf_invoice(
        "Invoice_Apex_Power_810.pdf",
        {
            "name": "Apex Power Tech Systems Pvt Ltd",
            "address": "Plot 18, Electronic City Phase 1, Bengaluru, Karnataka 560100",
            "gstin": "29AABCA9918M1ZQ",
            "email": "accounts@apexpowertech.com",
            "phone": "+91 80 4421 8899"
        },
        [
            {"desc": "Microtek Heavy Duty Sine Wave Inverter 1100VA", "hsn": "8504", "qty": 4, "rate": 6200.0},
            {"desc": "Exide Tubuler Inverter Battery 150AH", "hsn": "8507", "qty": 4, "rate": 11500.0}
        ],
        "APT-INV-810",
        is_interstate=True
    )
    
    # 3. Generate Excel
    generate_sample_excel_ledger()
    
    # 4. Seed Emails
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM emails")
    row = cursor.fetchone()
    count = list(row.values())[0] if isinstance(row, dict) else row[0]
    conn.close()
    
    if count == 0:
        sample_emails = [
            {
                "sender": "HDFC Bank Alert",
                "sender_email": "alerts@hdfcbank.net",
                "subject": "NEFT Credit Alert: ₹58,000.00 received in A/C **4921",
                "body": "Dear Customer, INR 58,000.00 has been credited to your account **4921 on 17-Sep-2026 by Gupta Building Materials via NEFT UTR HDFCN00918239. Current clear balance is INR 2,45,210.00."
            },
            {
                "sender": "Sharma Electrical & Industrial Supplies",
                "sender_email": "billing@sharmaelectricals.in",
                "subject": "Urgent: Payment reminder for Bill #INV-2024-942",
                "body": "Dear Ramesh ji, Greetings. This is to remind you that payment of ₹43,500 for invoice #INV-2024-942 is due on 20th September. Please arrange RTGS or UPI transfer at your earliest so we can process your new shipment."
            },
            {
                "sender": "Kavita Interiors & Architecture",
                "sender_email": "projects@kavitainteriors.in",
                "subject": "Bulk Rate Enquiry: 50 sets Modular Gold Switches for Villa Project",
                "body": "Hi Ramesh, We need immediate pricing quotation for 50 sets of 8-module gold finish switch plates and 200 dimmable switches for our upcoming Lonavala project. Can you provide your best wholesale rate and delivery date?"
            },
            {
                "sender": "GST Return Filing Portal",
                "sender_email": "donotreply@gst.gov.in",
                "subject": "Statutory Notice: GSTR-3B return filing due on 20th",
                "body": "Taxpayer Alert: Kindly ensure filing of Form GSTR-3B for the preceding tax period before 20th of this month to avoid late fee under section 47 of CGST Act and interest on delayed tax."
            },
            {
                "sender": "V-Trans Logistics India",
                "sender_email": "dispatch@vtrans.co.in",
                "subject": "Consignment Dispatched: Tracking LR #VT-881920",
                "body": "Your consignment consisting of 8 boxes electrical hardware shipped from Ahmedabad has reached Bhiwandi hub and is scheduled for store delivery tomorrow between 11 AM and 2 PM."
            }
        ]
        process_and_save_emails(sample_emails)

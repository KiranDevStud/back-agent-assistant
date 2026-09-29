import re
import sqlite3
from typing import Dict, Any, Optional, List

MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9, 'oct': 10,
    'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
}

def parse_period_from_query(text: str) -> Optional[Dict[str, str]]:
    """Extract specific dates or month periods from user queries."""
    text_lower = text.lower()
    
    # 1. YYYY-MM-DD
    m = re.search(r'\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b', text_lower)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return {'type': 'date', 'iso': f'{y:04d}-{mo:02d}-{d:02d}', 'display': f'{d:02d}-{mo:02d}-{y:04d}'}
        
    # 2. DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b', text_lower)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if mo > 12 and d <= 12:
            d, mo = mo, d
        return {'type': 'date', 'iso': f'{y:04d}-{mo:02d}-{d:02d}', 'display': f'{d:02d}-{mo:02d}-{y:04d}'}
        
    # 3. 16th September 2020 or 16-Sep-2020
    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?[\s\-_]+([a-z]{3,9})[\s\-_]+(\d{2,4})\b', text_lower)
    if m:
        d = int(m.group(1))
        mname = m.group(2)[:3]
        y = int(m.group(3))
        if y < 100:
            y += 2000
        if mname in MONTHS:
            mo = MONTHS[mname]
            return {'type': 'date', 'iso': f'{y:04d}-{mo:02d}-{d:02d}', 'display': f'{d:02d}-{mo:02d}-{y:04d}'}

    # 4. September 16, 2020
    m = re.search(r'\b([a-z]{3,9})[\s\-_]+(\d{1,2})(?:st|nd|rd|th)?[\s\-_,]+(\d{2,4})\b', text_lower)
    if m:
        mname = m.group(1)[:3]
        d = int(m.group(2))
        y = int(m.group(3))
        if y < 100:
            y += 2000
        if mname in MONTHS:
            mo = MONTHS[mname]
            return {'type': 'date', 'iso': f'{y:04d}-{mo:02d}-{d:02d}', 'display': f'{d:02d}-{mo:02d}-{y:04d}'}
            
    # 5. Month + Year e.g. 'september 2020', 'sep 2020'
    m = re.search(r'\b([a-z]{3,9})[\s\-_]+(\d{4})\b', text_lower)
    if m:
        mname = m.group(1)[:3]
        y = int(m.group(2))
        if mname in MONTHS:
            mo = MONTHS[mname]
            return {'type': 'month', 'iso': f'{y:04d}-{mo:02d}', 'display': f'{m.group(1).title()} {y}'}

    # 6. Specific Year e.g. "for 2020", "in 2020", "year 2020"
    m = re.search(r'\b(?:in|year|for)\s+(\d{4})\b', text_lower)
    if m:
        y = m.group(1)
        return {'type': 'year', 'iso': y, 'display': f'Year {y}'}
            
    return None

def query_period_financials(period_info: Dict[str, str], conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """Query transactions and invoices matching the extracted period."""
    cursor = conn.cursor()
    ptype = period_info['type']
    iso_val = period_info['iso']
    display_label = period_info['display']

    if ptype == 'date':
        cursor.execute("""
            SELECT type, party_name, category, amount, payment_mode, reference_no
            FROM transactions
            WHERE date = ?
            ORDER BY id ASC
        """, (iso_val,))
        rows = [dict(r) for r in cursor.fetchall()]
        
        # Also check invoices for that date
        cursor.execute("""
            SELECT invoice_number, vendor_name, customer_name, total_amount, invoice_type
            FROM invoices
            WHERE invoice_date = ?
            LIMIT 10
        """, (iso_val,))
        inv_rows = [dict(r) for r in cursor.fetchall()]

    elif ptype == 'month':
        cursor.execute("""
            SELECT type, party_name, category, amount, payment_mode, reference_no
            FROM transactions
            WHERE date LIKE ?
            ORDER BY date ASC, id ASC
        """, (f"{iso_val}%",))
        rows = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT invoice_number, vendor_name, customer_name, total_amount, invoice_type
            FROM invoices
            WHERE invoice_date LIKE ?
            LIMIT 10
        """, (f"{iso_val}%",))
        inv_rows = [dict(r) for r in cursor.fetchall()]

    elif ptype == 'year':
        cursor.execute("""
            SELECT type, party_name, category, amount, payment_mode, reference_no
            FROM transactions
            WHERE date LIKE ?
            ORDER BY date ASC, id ASC
        """, (f"{iso_val}%",))
        rows = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT invoice_number, vendor_name, customer_name, total_amount, invoice_type
            FROM invoices
            WHERE invoice_date LIKE ?
            LIMIT 10
        """, (f"{iso_val}%",))
        inv_rows = [dict(r) for r in cursor.fetchall()]
    else:
        return None

    sales = sum(r['amount'] for r in rows if r.get('type') == 'sale')
    expenses = sum(r['amount'] for r in rows if r.get('type') == 'expense')
    net_profit = sales - expenses

    return {
        'type': ptype,
        'label': display_label,
        'iso': iso_val,
        'has_data': len(rows) > 0 or len(inv_rows) > 0,
        'total_sales': round(sales, 2),
        'total_expenses': round(expenses, 2),
        'net_profit': round(net_profit, 2),
        'transaction_count': len(rows),
        'items': rows[:15],
        'invoices': inv_rows
    }

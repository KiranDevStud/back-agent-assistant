import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.database import get_db, get_all_settings

from collections import Counter
from typing import Dict, Any, List, Optional

def parse_df_section(df: pd.DataFrame, default_type: str = "sale") -> List[Dict[str, Any]]:
    """Parse a single rectangular table/block from a spreadsheet."""
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        return []

    # Clean initial column names
    orig_cols = [str(c).strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
    df.columns = orig_cols

    # Detect if section represents expenses or sales
    section_type = default_type
    for c in df.columns:
        if "expense" in c or "exp" in c:
            section_type = "expense"
            break
        elif "sale" in c:
            section_type = "sale"
            break

    # Header promotion if columns are unnamed (e.g. title banner in row 0)
    unnamed_cols = [c for c in df.columns if c.startswith("unnamed")]
    if len(unnamed_cols) >= len(df.columns) / 2 and len(df) > 0:
        first_row_vals = [str(v).strip().lower() for v in df.iloc[0].values if pd.notna(v)]
        header_keywords = ["date", "day", "party", "customer", "amount", "sales", "sale", "expense", "expenses", "exp", "no", "item", "total"]
        if any(any(k in v for k in header_keywords) for v in first_row_vals):
            df.columns = [str(c).strip().lower().replace(" ", "_").replace("/", "_") for c in df.iloc[0].values]
            df = df[1:].copy()

    for c in df.columns:
        if "expense" in c or "exp" in c:
            section_type = "expense"
            break

    col_map = {}
    for col in df.columns:
        if "unnamed" in col or col == "nan":
            continue
        if any(term in col for term in ["date", "dt", "txn_date"]):
            col_map["date"] = col
        elif any(term in col for term in ["day", "days"]):
            if "day" not in col_map:
                col_map["day"] = col
        elif any(term in col for term in ["party", "customer", "vendor", "client", "particular"]) or (col == "name" or col.endswith("_name")):
            col_map["party_name"] = col
        elif any(term in col for term in ["type", "txn_type", "trans_type"]):
            col_map["type"] = col
        elif any(term in col for term in ["category", "head", "item"]):
            col_map["category"] = col
        elif any(term in col for term in ["amount", "total", "value", "amt", "net", "sales", "sale", "expense", "expenses", "exp", "revenue", "turnover"]):
            col_map["amount"] = col
        elif any(term in col for term in ["mode", "payment_mode", "method"]):
            col_map["payment_mode"] = col
        elif any(term in col for term in ["status", "payment_status"]):
            col_map["status"] = col

    # If this section is explicitly an expense block, ensure amount maps to the expense column
    if section_type == "expense":
        for col in df.columns:
            if "expense" in col or "exp" in col:
                col_map["amount"] = col
                break

    records = []
    total_rows = len(df)
    now = datetime.now()

    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            raw_amt = row.get(col_map.get("amount", ""), 0)
            if pd.isna(raw_amt):
                continue
            if isinstance(raw_amt, str):
                cleaned_str = raw_amt.replace(",", "").replace("₹", "").replace("Rs.", "").strip()
                if not cleaned_str or cleaned_str.lower() in ["sales", "amount", "total", "expense", "expenses", "exp"]:
                    continue
                raw_amt = float(cleaned_str)
            else:
                raw_amt = float(raw_amt)

            if raw_amt <= 0:
                continue

            if "date" in col_map:
                raw_date = row.get(col_map["date"])
                if pd.isna(raw_date):
                    date_str = now.strftime("%Y-%m-%d")
                elif hasattr(raw_date, "strftime"):
                    date_str = raw_date.strftime("%Y-%m-%d")
                else:
                    date_str = str(raw_date)[:10]
            elif "day" in col_map:
                day_offset = total_rows - 1 - idx
                date_str = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            else:
                date_str = now.strftime("%Y-%m-%d")

            txn_type = str(row.get(col_map.get("type", ""), section_type)).strip().lower()
            if "exp" in txn_type:
                std_type = "expense"
            elif "purch" in txn_type:
                std_type = "purchase"
            elif "sale" in txn_type or "credit" in txn_type or "income" in txn_type:
                std_type = "sale"
            else:
                std_type = section_type

            day_name = str(row.get(col_map.get("day", ""), "")).strip()
            if std_type == "expense":
                default_party = f"Store Expense ({day_name})" if day_name and day_name.lower() != "nan" else "Store Expense"
                category = "General Store Expense"
            else:
                default_party = f"Counter Sales ({day_name})" if day_name and day_name.lower() != "nan" else "Walk-in Customer"
                category = "General Retail"

            party = str(row.get(col_map.get("party_name", ""), default_party)).strip()
            if party.lower() in ["nan", "none", ""]:
                party = default_party

            records.append({
                "date": date_str,
                "type": std_type,
                "party_name": party,
                "category": category,
                "amount": raw_amt,
                "payment_mode": "Cash" if std_type == "expense" else "UPI",
                "status": "settled"
            })
        except Exception:
            continue

    return records

def parse_spreadsheet(file_path: str) -> List[Dict[str, Any]]:
    """Parse Excel (.xlsx/.xls) or CSV supporting multi-sheet and side-by-side tables."""
    all_records = []
    
    if file_path.lower().endswith(".csv"):
        dfs = [pd.read_csv(file_path)]
    else:
        xl = pd.ExcelFile(file_path)
        dfs = [xl.parse(sheet) for sheet in xl.sheet_names]

    for raw_df in dfs:
        if raw_df.empty:
            continue
        
        # Check if the dataframe contains multiple side-by-side table blocks
        cols = list(raw_df.columns)
        non_empty_indices = [i for i, c in enumerate(cols) if raw_df[c].dropna().shape[0] > 0]
        
        if not non_empty_indices:
            continue
            
        blocks = []
        current_block = [non_empty_indices[0]]
        for idx in non_empty_indices[1:]:
            # If gap between non-empty columns is > 2, treat as a separate table block
            if idx <= current_block[-1] + 2:
                current_block.append(idx)
            else:
                blocks.append(current_block)
                current_block = [idx]
        blocks.append(current_block)

        for b in blocks:
            sub_df = raw_df.iloc[:, b].copy()
            recs = parse_df_section(sub_df)
            all_records.extend(recs)

    return all_records

def save_transactions_to_db(records: List[Dict[str, Any]], user_id: Optional[int] = None) -> Dict[str, int]:
    """
    Store parsed records in database, intelligently deduplicating against existing transactions.
    If the same spreadsheet is re-uploaded with additional rows, only the new rows are inserted.
    """
    if not records:
        return {"inserted": 0, "skipped": 0, "total": 0}

    conn = get_db()
    cursor = conn.cursor()

    # Load existing transaction signatures
    if user_id:
        cursor.execute("SELECT date, type, party_name, amount FROM transactions WHERE user_id = ?", (user_id,))
    else:
        cursor.execute("SELECT date, type, party_name, amount FROM transactions")

    existing_counts = Counter()
    for row in cursor.fetchall():
        sig = (str(row["date"]), str(row["type"]), str(row["party_name"]), round(float(row["amount"]), 2))
        existing_counts[sig] += 1

    inserted = 0
    skipped = 0

    for r in records:
        sig = (str(r["date"]), str(r["type"]), str(r["party_name"]), round(float(r["amount"]), 2))
        if existing_counts[sig] > 0:
            existing_counts[sig] -= 1
            skipped += 1
            continue

        # Insert new unique transaction
        cursor.execute('''
            INSERT INTO transactions (date, type, party_name, category, amount, payment_mode, status, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r["date"],
            r["type"],
            r["party_name"],
            r["category"],
            r["amount"],
            r["payment_mode"],
            r["status"],
            user_id
        ))
        inserted += 1

    conn.commit()
    conn.close()

    return {"inserted": inserted, "skipped": skipped, "total": len(records)}

def generate_mis_report(skip_commentary: bool = False) -> Dict[str, Any]:
    """Calculate executive MIS summary, charts, debtors list, and aging analysis."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM transactions ORDER BY date ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    if not rows:
        return {
            "total_sales": 0,
            "total_purchases": 0,
            "total_expenses": 0,
            "net_cash_flow": 0,
            "total_receivables": 0,
            "aging": {"0_15": 0, "16_30": 0, "31_60": 0, "60_plus": 0},
            "top_debtors": [],
            "daily_trends": {"labels": [], "sales": [], "expenses": []},
            "ai_commentary": "No transaction records found. Please upload a daily sales spreadsheet or ledger."
        }

    total_sales = sum(r["amount"] for r in rows if r["type"] == "sale")
    total_purchases = sum(r["amount"] for r in rows if r["type"] == "purchase")
    total_expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    pending_payables = sum(r["amount"] for r in rows if r["type"] == "purchase" and r["status"] == "pending")
    settled_purchases = sum(r["amount"] for r in rows if r["type"] == "purchase" and r["status"] == "settled")
    net_cash_flow = total_sales - (total_purchases + total_expenses)
    
    # Debtors calculation (unsettled sales)
    debtor_map = {}
    aging = {"0_15": 0.0, "16_30": 0.0, "31_60": 0.0, "60_plus": 0.0}
    
    now = datetime.now()
    for r in rows:
        if r["type"] == "sale" and r["status"] == "pending":
            party = r["party_name"] or "Unknown Customer"
            debtor_map[party] = debtor_map.get(party, 0.0) + r["amount"]
            
            # Age calculation
            try:
                txn_date = datetime.strptime(r["date"], "%Y-%m-%d")
                days_diff = (now - txn_date).days
            except Exception:
                days_diff = 10
                
            if days_diff <= 15:
                aging["0_15"] += r["amount"]
            elif days_diff <= 30:
                aging["16_30"] += r["amount"]
            elif days_diff <= 60:
                aging["31_60"] += r["amount"]
            else:
                aging["60_plus"] += r["amount"]

    total_receivables = sum(debtor_map.values())
    
    # Sort top debtors
    sorted_debtors = sorted(
        [{"party_name": k, "amount": round(v, 2)} for k, v in debtor_map.items()],
        key=lambda x: x["amount"],
        reverse=True
    )[:5]

    # Daily trends (group by date)
    from backend.services.invoice_extractor import normalize_date_iso
    date_groups = {}
    for r in rows:
        d = normalize_date_iso(str(r["date"]))
        if d not in date_groups:
            date_groups[d] = {"sales": 0.0, "expenses": 0.0}
        if r["type"] == "sale":
            date_groups[d]["sales"] += r["amount"]
        else:
            date_groups[d]["expenses"] += r["amount"]

    def parse_sort_key(dt_str):
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d")
        except Exception:
            return datetime.min

    sorted_dates = sorted(date_groups.keys(), key=parse_sort_key)[-14:] # Last 14 days chronologically
    trends = {
        "labels": sorted_dates,
        "sales": [round(date_groups[d]["sales"], 2) for d in sorted_dates],
        "expenses": [round(date_groups[d]["expenses"], 2) for d in sorted_dates]
    }

    # Recent Purchases & Vendor Invoices (Outflows)
    purchases_rows = [r for r in rows if r["type"] == "purchase"]
    purchases_rows.sort(key=lambda r: (str(r.get("date") or ""), int(r.get("id") or 0)), reverse=True)
    recent_purchases = []
    for r in purchases_rows[:15]:
        recent_purchases.append({
            "id": r.get("id"),
            "date": normalize_date_iso(str(r.get("date") or "")),
            "party_name": r.get("party_name") or "Vendor",
            "amount": round(float(r.get("amount", 0.0) or 0.0), 2),
            "status": r.get("status", "pending"),
            "reference_no": r.get("reference_no") or "-",
            "payment_mode": r.get("payment_mode") or "Bank/NEFT"
        })

    # Generate Smart Executive Commentary via AI if requested
    metrics_context = {
        "total_sales": total_sales,
        "total_expenses": (total_purchases + total_expenses),
        "net_cash": net_cash_flow,
        "total_receivables": total_receivables,
        "top_debtors": sorted_debtors,
        "high_risk_receivables": (aging["31_60"] + aging["60_plus"])
    }
    
    health = "Healthy Cash Surplus" if net_cash_flow > 0 else "Tight Liquidity / Deficit"
    high_risk_amount = aging["31_60"] + aging["60_plus"]
    top_name = sorted_debtors[0]["party_name"] if sorted_debtors else "None"
    top_amt = sorted_debtors[0]["amount"] if sorted_debtors else 0
    margin_pct = ((total_sales - (total_purchases + total_expenses)) / total_sales * 100) if total_sales > 0 else 0
    
    payable_text = f"\n• Accounts Payable (Pending Bills): ₹{pending_payables:,.2f} in unpaid vendor invoices awaiting payment clearance." if pending_payables > 0 else "\n• Accounts Payable: All recorded vendor bills are fully settled."
    
    commentary = (
        f"• Cash Position & Velocity ({health}): Total recorded revenue of ₹{total_sales:,.2f} against ₹{(total_purchases + total_expenses):,.2f} outflows delivers an operating margin of {margin_pct:.1f}% (Net Cash: ₹{net_cash_flow:,.2f}).\n"
        f"• Receivables & Working Capital: Currently ₹{total_receivables:,.2f} is outstanding across customer ledgers, with ₹{high_risk_amount:,.2f} exceeding the 30-day credit period."
        f"{payable_text}\n"
        f"• Priority Collection Follow-Up: Highest individual exposure is with {top_name} (₹{top_amt:,.2f}). Direct WhatsApp payment reminder with UPI quick-pay link recommended.\n"
        f"• Statutory & Tax Action: Reconcile all purchase bills for timely GSTR-2B input tax credit (ITC) claims before upcoming monthly GST return filing."
    )

    return {
        "total_sales": round(total_sales, 2),
        "total_purchases": round(total_purchases, 2),
        "total_expenses": round(total_expenses, 2),
        "total_payables": round(pending_payables, 2),
        "settled_purchases": round(settled_purchases, 2),
        "recent_purchases": recent_purchases,
        "net_cash_flow": round(net_cash_flow, 2),
        "total_receivables": round(total_receivables, 2),
        "aging": {k: round(v, 2) for k, v in aging.items()},
        "top_debtors": sorted_debtors,
        "daily_trends": trends,
        "ai_commentary": commentary
    }

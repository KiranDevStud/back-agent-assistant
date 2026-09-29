# PattuBook Back Office Assistant - Production System Architecture & Operations Guide

## 1. Executive Summary

PattuBook is an intelligent, production-ready back-office operating system engineered specifically for Indian small-to-medium enterprises (MSMEs), retailers, wholesalers, and trade businesses. 

The system unifies:
- Multimodal GST tax invoice extraction powered by Google Gemini AI and an offline heuristic fallback engine.
- Executive morning operational briefings that synthesize unread bank alerts, overdue payment notices, supplier consignments, and customer inquiries.
- Daily Management Information System (MIS) reports, cash velocity analytics, and receivables aging (0-15, 16-30, 31-60, 60+ days) with AI-generated commentary.
- Multi-tone payment reminder generation (Gentle, Professional, Firm, Hinglish) with instant UPI Quick-Pay links and one-click WhatsApp/Email dispatch.
- Indian Statutory Compliance Guardian tracking GSTR-1, GSTR-3B, TDS Challan 281, Advance Tax (Section 234B/C), and GSTR-9 annual returns.
- Interactive Gemini Back Office AI Assistant for real-time consultation on tax rules, debtor recovery, credit terms, and cash flow strategies.
- Dual-engine database architecture: SQLite for local offline development, and auto-detecting PostgreSQL with connection pooling for Railway cloud deployments.
- JWT authentication with optional email verification, Argon2/bcrypt password hashing, and user-scoped data segregation.

---

## 2. Core System Architecture & Functioning

### 2.1 Technology Stack
- **Backend Framework**: Python 3.10+, FastAPI, Uvicorn (ASGI).
- **Database Layer**: SQLAlchemy dual-engine abstraction:
  - Local / Offline: SQLite (`data/backoffice.db`).
  - Production Cloud: PostgreSQL (automatically provisioned when `DATABASE_URL` is set, e.g. Railway, Neon, AWS RDS).
- **AI Engine**: Google Gemini Generative AI SDK (`gemini-2.5-flash`) via `google-generativeai` with automated fallback to robust local heuristic parsers.
- **Document & Spreadsheet Processing**: PyPDF2, pdfplumber, Tesseract OCR wrapper, and Pandas with openpyxl.
- **Security & Authentication**: OAuth2 Password Bearer flow, JWT tokens (`python-jose`), and passlib with bcrypt.
- **Frontend Architecture**: Pure Vanilla HTML5, CSS3 Custom Design System (responsive desktop and tablet layouts, dark/light theme toggle), and modular Vanilla JavaScript. No bloated dependencies or build steps required.

### 2.2 Dual Database Architecture
The database manager (`backend/database.py`) inspects the environment at boot:
```
DATABASE_URL exists?
* YES -> Connect to PostgreSQL via psycopg2 / SQLAlchemy. Set IS_POSTGRES = True.
* NO  -> Connect to SQLite (data/backoffice.db) using sqlite3.Row factory. Set IS_POSTGRES = False.
```
Parameter syntax is automatically standardized across queries (`?` for SQLite, `%s` for PostgreSQL), enabling seamless migration from laptop development to cloud containers without code modification.

---

## 3. Gemini AI Integration & Workflows

PattuBook centralizes all AI workflows inside `backend/services/gemini_service.py`. The system operates seamlessly whether an API key is provided or not:
- When `GEMINI_API_KEY` is present in the environment or configured in Settings, the system uses `gemini-2.5-flash` for deep semantic reasoning.
- When no key is set or internet connectivity is absent, the system automatically falls back to deterministic rule-based algorithms, ensuring zero downtime.

### 3.1 Multimodal Invoice Extraction (`extract_invoice_with_gemini`)
- Ingests scanned or digital vendor/buyer tax invoices (PDF, PNG, JPG).
- Extracts seller GSTIN, buyer GSTIN, invoice number, invoice date, due date, taxable value, CGST, SGST, IGST, total amount, and itemized line items.
- Performs checksum and format validation on Indian GSTIN numbers (State Code + PAN + Entity Code + Z + Check Digit).

### 3.2 Morning Briefing Synthesis (`generate_morning_briefing_with_gemini`)
- Analyzes incoming business communications (bank credit/debit alerts, supplier overdue notices, quotation requests, dispatch LR copies).
- Compiles an executive morning digest for the business owner highlighting urgent action items, financial credits, and supply chain flags.

### 3.3 MIS Executive Commentary (`generate_mis_commentary_with_gemini`)
- Analyzes daily sales, purchase outlays, operational expenses, net cash surplus, and overdue receivables.
- Generates 3 to 4 actionable bullet points highlighting liquidity health, debtor concentration risk, and working capital recommendations.

### 3.4 Smart Multi-Tone Payment Reminders (`generate_payment_reminder_with_gemini`)
- Generates customized collection notices tailored to customer relationships:
  - **Professional**: Formal accounts receivable phrasing for corporate accounts.
  - **Gentle**: Polite reminders for long-standing regular clients.
  - **Firm**: Assertive warnings citing credit suspension for accounts overdue beyond 30 days.
  - **Hinglish**: Natural bilingual Indian business phrasing commonly used in wholesale trade.
- Embeds standardized Indian UPI deep links (`upi://pay?pa=...&pn=...&am=...&tn=...&cu=INR`) for instant settlement.

### 3.5 Interactive Back Office AI Advisor (`ask_assistant_with_gemini`)
- Direct chat consultation embedded in the dashboard.
- Domain expertise covering Indian GST (GSTR-2B ITC reconciliation, reverse charge mechanism, e-way bills), debtor recovery, commercial lease terms, and statutory deadlines.
- Automatically receives store profile context (business name, GSTIN, active compliance schedule) to deliver tailored answers.

---

## 4. Module Breakdown & Operational Features

### 4.1 Daily Briefing View (`#briefing-view`)
- **Executive Summary Banner**: Real-time operational headline and count of urgent communications.
- **Urgent Action Items**: High-priority tasks color-coded by category (Bank Alert, Payment Demand, Statutory, Customer Order).
- **Communication Stream**: Chronological feed of ingested messages with quick action buttons.
- **Manual Ingestion**: Ability to log customer messages or vendor emails directly into the feed.

### 4.2 Invoices & Bills View (`#invoices-view`)
- **Drag & Drop Upload Zone**: Ingest PDF and scanned invoices for automatic AI extraction.
- **Processed Invoices Register**: Searchable and filterable table displaying Invoice Number, Vendor Name, GSTIN, Taxable Value, CGST/SGST/IGST breakdown, Total Amount, and Payment Status.
- **Status Toggling**: Toggle invoices between "Unpaid" and "Paid" to update working capital ledgers.
- **Invoice Inspection Modal**: Detailed line-item breakdown showing HSN codes, quantity, rate, and total tax.

### 4.3 MIS & Cash Flow Intelligence (`#mis-view`)
- **Metric Cards**: Total Sales, Purchases & Expenses, Net Cash Surplus/Deficit, and Market Credit (Debtors).
- **Cash Velocity Chart**: 14-day interactive visualization of daily revenue vs. expenditures.
- **AI Business Commentary**: Automated financial controller insights.
- **Receivables Aging Matrix**:
  - 0 - 15 Days (Current)
  - 16 - 30 Days (Due Soon)
  - 31 - 60 Days (Attention Required)
  - 60+ Days (High Risk Exposure)
- **Top 5 Debtors Table**: Displays customers with highest outstanding balances and 1-click payment reminder triggers.
- **Spreadsheet Ingestion**: Supports standard `.xlsx`, `.xls`, and `.csv` sales and expense ledgers.

### 4.4 Payment Reminders View (`#comms-view`)
- **Reminder Generator**: Input customer name, invoice reference, pending balance, due date, and mobile number.
- **Tone Selector**: Professional, Gentle, Firm, or Hinglish.
- **One-Click Dispatch**:
  - **WhatsApp**: Pre-formatted message with embedded UPI link sent directly to the customer's phone.
  - **Email**: Pre-filled email draft with subject line and payment coordinates.
  - **Copy Message**: Direct clipboard copy for SMS or alternative messaging channels.

### 4.5 Indian Statutory & GST Compliance Guardian (`#compliance-view`)
Monitors mandatory Indian tax filings with live countdown clocks and status badges:
- **GSTR-1**: Monthly outward supplies due by the 11th of each month.
- **GSTR-3B**: Monthly summary return and tax payment due by the 20th of each month.
- **TDS Challan ITNS 281**: Monthly withholding tax deposit due by the 7th of each month.
- **Advance Tax (Income Tax Section 234B/C)**: Quarterly tax installments (June 15, Sept 15, Dec 15, March 15).
- **GSTR-9 & 9C**: Annual GST return and reconciliation due by December 31.
- **CA Compliance Email Generator**: 1-click draft email summarizing sales, input credit, and turnover for forwarding to the firm's Chartered Accountant.

### 4.6 Interactive AI Assistant (`#assistant-view`)
- Dedicated chat interface connected to Google Gemini.
- Pre-configured prompt chips for common business challenges (ITC reconciliation, overdue letters, freight GST, cash flow planning).
- Full conversation history with clean markdown rendering and instant clear-chat functionality.

### 4.7 Connected Apps Hub (`#integrations-view`)
- **Google Calendar**: Synchronizes GST, TDS, and advance tax deadlines to prevent late fees.
- **Gmail**: Syncs bank transaction emails, supplier invoices, and vendor reminders.
- **WhatsApp Business**: Connects accounts receivable notifications directly to customer numbers.
- **Tally Prime & ERP**: Exports extracted invoices and transactions in Tally XML/CSV format.
- **Railway Cloud Database**: Status indicator verifying active PostgreSQL cloud synchronization.

### 4.8 Store Profile & Settings View (`#settings-view`)
- **Business Profile**: Store Name, Proprietor Name, GSTIN, Phone, Email, UPI ID, and CA Email.
- **Gemini AI Configuration**: Live API key management with status badge and link to Google AI Studio.
- **Production Data Management**: "Purge Test Records" tool allowing store owners to reset operational data (invoices, transactions, communications) while keeping statutory compliance schedules intact.

---

## 5. Environment Variables & Configuration

Configure the following variables in your `.env` file for local development or in Railway Dashboard under Variables:

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Optional | `None` (SQLite used) | PostgreSQL connection string (auto-provided by Railway PostgreSQL). |
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API Key. Can also be set in Settings UI. |
| `BUSINESS_NAME` | Optional | `"Enterprise Retail Store"` | Default store or company name. |
| `OWNER_NAME` | Optional | `"Proprietor"` | Default proprietor or manager name. |
| `BUSINESS_GSTIN`| Optional | `""` | 15-character GSTIN tax identification number. |
| `BUSINESS_UPI_ID`| Optional | `""` | Merchant UPI ID for embedded quick-pay links. |
| `BUSINESS_PHONE` | Optional | `""` | Store contact number. |
| `BUSINESS_CA_EMAIL`| Optional | `""` | Email of your Chartered Accountant. |
| `SECRET_KEY` | Optional | Auto-generated | 256-bit encryption key for signing JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | `1440` (24 Hours) | JWT session lifetime. |
| `PORT` | Optional | `8000` | HTTP port used by Uvicorn. |

---

## 6. Railway Cloud Deployment Guide

PattuBook is pre-configured for one-click deployment to Railway.

### 6.1 Railway Deployment Steps
1. Push your repository to GitHub.
2. In Railway, click **New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. Click **New** -> **Database** -> **Add PostgreSQL**.
5. In your service's **Variables** tab, Railway automatically links `DATABASE_URL`.
6. Add `GEMINI_API_KEY` with your Google Gemini key.
7. Railway will detect `railway.json` and `Procfile`:
   ```Procfile
   web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
8. Under **Networking**, click **Generate Domain** to access your live production HTTPS URL.

### 6.2 Verifying Production Health
Navigate to `/api/status` on your live domain. The response will confirm:
```json
{
  "status": "online",
  "system": "PattuBook Back Office Assistant",
  "version": "2.0.0",
  "database": {
    "engine": "PostgreSQL (Railway Production)",
    "is_postgres": true,
    "connected": true
  },
  "ai": {
    "gemini_active": true,
    "model": "gemini-2.5-flash"
  },
  "integrations": ["Google Calendar", "Gmail", "WhatsApp", "Tally Prime"]
}
```

---

## 7. Data Reset & Production Readiness Verification

The system includes zero hardcoded dummy invoices or sample transactions upon clean installation:
- `data/backoffice.db` contains no sample invoices, fake transactions, or mock emails.
- Seeding routines on startup have been removed.
- All empty states provide clear instructions on uploading genuine bills or ledgers.
- If test records are ever created during testing, clicking **Purge Test Records** in the Store Profile tab instantly purges all invoices, transactions, and email entries.
- The UI strictly enforces the zero-emoji design standard across all views, preserving only the dark/light theme switch icons.

---

## 8. Automated IMAP Email Reception & 5-Minute Timer

The system includes a built-in background scheduler daemon that polls configured email inboxes (Gmail, Yahoo, Outlook, custom domains) every **5 minutes** over SSL (Port 993).

### Features
1. **Universal Protocol:** Uses Python standard library `imaplib` + `email` over TLS/SSL (zero external heavy dependencies).
2. **AI Categorization:** Automatically passes incoming text to `classify_email()` (Gemini AI or fallback) into:
   - Bank Alerts (NEFT / RTGS / UPI credits & debits)
   - Statutory / GST Notices
   - Vendor Invoices & Payment Demands
   - Customer Inquiries
3. **Automated Attachment Ingestion:** Detects PDF invoice attachments, downloads them to `data/uploads/`, and automatically triggers `extract_invoice_data()` to populate the Invoices & Bills ledger.
4. **Non-blocking Background Daemon:** Runs in a separate thread started on FastAPI startup without blocking web requests.
5. **Dynamic Configuration:** Supports live `.env` reloads so adding an App Password takes effect immediately without manual server reboot.

### Environment Configuration
```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_16_char_google_app_password
IMAP_SYNC_INTERVAL_MINUTES=5
IMAP_FOLDER=INBOX
```


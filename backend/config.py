import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
SAMPLES_DIR = DATA_DIR / "samples"
DB_PATH = DATA_DIR / "backoffice.db"

# Create directories if they do not exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Default Business Profile (Configured via environment variables or Settings UI)
DEFAULT_SETTINGS = {
    "business_name": os.getenv("BUSINESS_NAME", "Enterprise Retail Store"),
    "owner_name": os.getenv("OWNER_NAME", "Proprietor"),
    "gstin": os.getenv("BUSINESS_GSTIN", ""),
    "phone": os.getenv("BUSINESS_PHONE", ""),
    "email": os.getenv("BUSINESS_EMAIL", ""),
    "upi_id": os.getenv("BUSINESS_UPI_ID", ""),
    "ca_email": os.getenv("BUSINESS_CA_EMAIL", ""),
    "currency_symbol": os.getenv("CURRENCY_SYMBOL", "₹"),
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "ai_provider": os.getenv("AI_PROVIDER", "local"),
    "local_ai_model": os.getenv("LOCAL_AI_MODEL", "gemma2:2b"),
    "local_ai_endpoint": os.getenv("LOCAL_AI_ENDPOINT", "http://localhost:11434"),
    "imap_host": os.getenv("IMAP_HOST", "imap.gmail.com"),
    "imap_port": os.getenv("IMAP_PORT", "993"),
    "imap_sync_interval": os.getenv("IMAP_SYNC_INTERVAL_MINUTES", "5")
}

# Automated IMAP Settings
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", os.getenv("SMTP_USER", ""))
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
IMAP_SYNC_INTERVAL_MINUTES = int(os.getenv("IMAP_SYNC_INTERVAL_MINUTES", "5"))
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")


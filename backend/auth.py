import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
if not hasattr(bcrypt, "__about__"):
    class BcryptAbout:
        __version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = BcryptAbout()

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.models import User
from backend.database import get_db_session

# Secret configurations
JWT_SECRET = os.getenv("JWT_SECRET", "pattubook_assistant_jwt_production_secret_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# SMTP configuration for real email delivery (Railway / Production)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@pattubook.com")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Hash plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_verification_token() -> tuple[str, datetime]:
    """Generate a secure verification token and 24-hour expiration timestamp."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    return token, expires_at


def send_verification_email(to_email: str, full_name: str, token: str, host_url: str = "") -> Dict[str, Any]:
    """
    Sends email verification to user.
    If SMTP credentials are provided, dispatches via SMTP.
    Otherwise, returns simulation data so local and dev deployments can 1-click verify.
    """
    verify_url = f"{host_url.rstrip('/')}/#verify?token={token}&email={to_email}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #090d16; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 540px; margin: 0 auto; background: #0f172a; border-radius: 12px; border: 1px solid #1e293b; padding: 32px; }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .brand {{ font-size: 22px; font-weight: 700; color: #6366f1; }}
        .title {{ font-size: 18px; margin: 16px 0; color: #f8fafc; }}
        .body-text {{ font-size: 14px; line-height: 1.6; color: #94a3b8; }}
        .button-box {{ text-align: center; margin: 30px 0; }}
        .verify-btn {{ background: #6366f1; color: #ffffff !important; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; }}
        .token-box {{ background: #1e293b; padding: 12px; border-radius: 8px; word-break: break-all; font-family: monospace; font-size: 13px; color: #38bdf8; margin-top: 16px; }}
        .footer {{ text-align: center; font-size: 12px; color: #64748b; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="brand">PattuBook</div>
        <div class="title">Verify Your Email Address</div>
        <p class="body-text">Hello {full_name},</p>
        <p class="body-text">Thank you for signing up for PattuBook Back Office Assistant. Please verify your email address to activate your account and start managing your store, GST compliance, invoices, and payment reminders.</p>
        
        <div class="button-box">
          <a href="{verify_url}" class="verify-btn">Verify Email Address</a>
        </div>
        
        <p class="body-text">Or enter this verification token directly in the app:</p>
        <div class="token-box">{token}</div>
        
        <div class="footer">
          This link will expire in 24 hours. If you did not request this, please disregard this email.
        </div>
      </div>
    </body>
    </html>
    """

    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Verify your email for PattuBook Back Office Assistant"
            msg["From"] = FROM_EMAIL
            msg["To"] = to_email

            part_text = MIMEText(f"Hello {full_name},\n\nPlease verify your email: {verify_url}\nToken: {token}", "plain")
            part_html = MIMEText(html_content, "html")
            msg.attach(part_text)
            msg.attach(part_html)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
                
            return {"sent": True, "method": "smtp", "message": f"Verification email sent to {to_email}"}
        except Exception as e:
            print(f"[send_verification_email] SMTP failure ({e}). Falling back to direct token delivery.")

    # In local or preview mode without SMTP credentials, log the token and provide the 1-click verify link
    print("==================================================")
    print(f" [EMAIL VERIFICATION DISPATCH]")
    print(f" To: {to_email}")
    print(f" Link: {verify_url}")
    print(f" Token: {token}")
    print("==================================================")

    return {
        "sent": True,
        "method": "dev_preview",
        "verify_url": verify_url,
        "token": token,
        "message": f"Verification token generated for {to_email} (Ready to verify)"
    }


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session)
) -> Optional[User]:
    """Retrieves authenticated user from Bearer token if present; else None."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db_session)
) -> User:
    """Enforces valid authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user

import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.database import get_db_session
from backend.models import User
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    generate_verification_token,
    send_verification_email,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    business_name: Optional[str] = "Om Sai Traders & Enterprises"
    gstin: Optional[str] = "27AAPCG1234F1Z8"
    phone: Optional[str] = "+91 98200 12345"

class LoginRequest(BaseModel):
    email: str
    password: str

class VerifyEmailRequest(BaseModel):
    token: str
    email: Optional[str] = None

class ResendVerificationRequest(BaseModel):
    email: str

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    business_name: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    ca_email: Optional[str] = None


@router.post("/signup")
def signup(req: SignupRequest, request: Request, db: Session = Depends(get_db_session)):
    email_clean = req.email.strip().lower()
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please log in or use another email."
        )

    # Generate token
    token, expires_at = generate_verification_token()
    
    # Check if SMTP is configured for real delivery; otherwise auto-verify
    smtp_configured = bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))
    auto_verify = os.getenv("AUTO_VERIFY_SIGNUP", "true" if not smtp_configured else "false").lower() == "true"

    user = User(
        email=email_clean,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        business_name=req.business_name.strip() if req.business_name else "Enterprise Store",
        gstin=req.gstin.strip() if req.gstin else "27AAPCG1234F1Z8",
        phone=req.phone.strip() if req.phone else "",
        is_verified=auto_verify,
        verification_token=None if auto_verify else token,
        verification_token_expires_at=None if auto_verify else expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Base URL for verification link
    host_url = str(request.base_url)
    dispatch_res = send_verification_email(user.email, user.full_name, token, host_url)

    # Issue signed JWT token immediately so registration signs the user in seamlessly
    access_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "message": "Account created successfully! Welcome to PattuBook.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict(),
        "verification": dispatch_res
    }


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db_session)):
    token_clean = req.token.strip()
    
    query = db.query(User).filter(User.verification_token == token_clean)
    if req.email:
        query = query.filter(User.email == req.email.strip().lower())
    
    user = query.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used verification token."
        )

    if user.verification_token_expires_at and user.verification_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please request a new verification email."
        )

    # Mark as verified
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    db.commit()
    db.refresh(user)

    # Issue access token so user is automatically logged in!
    access_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "message": "Email verified successfully! You are now logged in.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.post("/resend-verification")
def resend_verification(req: ResendVerificationRequest, request: Request, db: Session = Depends(get_db_session)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if user.is_verified:
        return {"message": "Your account is already verified! You can log in directly."}

    token, expires_at = generate_verification_token()
    user.verification_token = token
    user.verification_token_expires_at = expires_at
    db.commit()

    host_url = str(request.base_url)
    dispatch_res = send_verification_email(user.email, user.full_name, token, host_url)

    return {
        "message": f"Verification email resent to {user.email}",
        "verification": dispatch_res
    }


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db_session)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    smtp_configured = bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))
    auto_verify = os.getenv("AUTO_VERIFY_SIGNUP", "true" if not smtp_configured else "false").lower() == "true"

    if not user.is_verified:
        if auto_verify:
            user.is_verified = True
            db.commit()
            db.refresh(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please verify your email before logging in. You can click 'Resend Verification' if you need a new link."
            )

    access_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@router.get("/me")
def get_current_user_profile(user: User = Depends(get_current_user)):
    return {
        "user": user.to_dict(),
        "is_authenticated": True
    }


@router.post("/profile")
def update_profile(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db_session)):
    if req.full_name is not None:
        user.full_name = req.full_name
    if req.business_name is not None:
        user.business_name = req.business_name
    if req.gstin is not None:
        user.gstin = req.gstin
    if req.phone is not None:
        user.phone = req.phone
    if req.upi_id is not None:
        user.upi_id = req.upi_id
    if req.ca_email is not None:
        user.ca_email = req.ca_email

    db.commit()
    db.refresh(user)
    return {
        "message": "Store profile updated successfully",
        "user": user.to_dict()
    }


@router.post("/logout")
def logout():
    return {"message": "Logged out successfully"}

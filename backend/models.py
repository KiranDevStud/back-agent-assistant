from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    business_name = Column(String(255), default="My Business")
    gstin = Column(String(50), default="")
    phone = Column(String(50), default="")
    upi_id = Column(String(100), default="")
    ca_email = Column(String(255), default="")
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(255), nullable=True, index=True)
    verification_token_expires_at = Column(DateTime, nullable=True)
    reset_token = Column(String(255), nullable=True)
    role = Column(String(50), default="owner")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    compliance_records = relationship("ComplianceRecord", back_populates="user", cascade="all, delete-orphan")
    emails = relationship("EmailItem", back_populates="user", cascade="all, delete-orphan")
    connected_apps = relationship("ConnectedApp", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "business_name": self.business_name,
            "gstin": self.gstin,
            "phone": self.phone,
            "upi_id": self.upi_id,
            "ca_email": self.ca_email,
            "is_verified": self.is_verified,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name = Column(String(255))
    file_path = Column(String(500))
    invoice_number = Column(String(100), index=True)
    invoice_type = Column(String(50), default="purchase")
    vendor_name = Column(String(255))
    customer_name = Column(String(255))
    vendor_gstin = Column(String(50))
    buyer_gstin = Column(String(50))
    invoice_date = Column(String(50))
    due_date = Column(String(50))
    subtotal = Column(Float, default=0.0)
    cgst = Column(Float, default=0.0)
    sgst = Column(Float, default=0.0)
    igst = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    line_items = Column(Text, default="[]")
    status = Column(String(50), default="Unpaid")
    extraction_method = Column(String(50), default="rule_based")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="invoices")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "invoice_number": self.invoice_number,
            "invoice_type": self.invoice_type,
            "vendor_name": self.vendor_name,
            "customer_name": self.customer_name,
            "vendor_gstin": self.vendor_gstin,
            "buyer_gstin": self.buyer_gstin,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "subtotal": self.subtotal,
            "cgst": self.cgst,
            "sgst": self.sgst,
            "igst": self.igst,
            "total_tax": self.total_tax,
            "total_amount": self.total_amount,
            "line_items": self.line_items,
            "status": self.status,
            "extraction_method": self.extraction_method,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    date = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)  # 'sale', 'purchase', 'expense'
    party_name = Column(String(255))
    category = Column(String(100))
    amount = Column(Float, nullable=False, default=0.0)
    payment_mode = Column(String(50), default="UPI")
    status = Column(String(50), default="settled")  # 'settled', 'pending'
    due_date = Column(String(50))
    reference_no = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date,
            "type": self.type,
            "party_name": self.party_name,
            "category": self.category,
            "amount": self.amount,
            "payment_mode": self.payment_mode,
            "status": self.status,
            "due_date": self.due_date,
            "reference_no": self.reference_no,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(100), index=True)
    title = Column(String(255), nullable=False)
    frequency = Column(String(50), nullable=False)
    due_day = Column(Integer)
    next_due_date = Column(String(50))
    description = Column(Text)
    status = Column(String(50), default="pending")
    penalty_info = Column(Text)
    action_template = Column(Text)
    last_checked = Column(String(50))

    user = relationship("User", back_populates="compliance_records")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "code": self.code,
            "title": self.title,
            "frequency": self.frequency,
            "due_day": self.due_day,
            "next_due_date": self.next_due_date,
            "description": self.description,
            "status": self.status,
            "penalty_info": self.penalty_info,
            "action_template": self.action_template,
            "last_checked": self.last_checked
        }


class EmailItem(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    sender = Column(String(255))
    sender_email = Column(String(255))
    subject = Column(String(500))
    date = Column(String(100))
    raw_body = Column(Text)
    summary = Column(Text)
    category = Column(String(100))
    priority = Column(String(50), default="medium")
    action_required = Column(Text)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="emails")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "date": self.date,
            "raw_body": self.raw_body,
            "summary": self.summary,
            "category": self.category,
            "priority": self.priority,
            "action_required": self.action_required,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ConnectedApp(Base):
    __tablename__ = "connected_apps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False)  # 'google_calendar', 'gmail', 'whatsapp', 'tally'
    account_email = Column(String(255), default="")
    access_token = Column(Text, default="")
    refresh_token = Column(Text, default="")
    token_expires_at = Column(DateTime, nullable=True)
    settings_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="connected_apps")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "account_email": self.account_email,
            "is_active": self.is_active,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, default="")

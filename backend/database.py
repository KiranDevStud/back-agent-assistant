import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.config import DB_PATH, DEFAULT_SETTINGS
from backend.models import Base, Setting, ComplianceRecord, User

# Resolve Database URL (Postgres when deployed on Railway, fallback to SQLite locally)
RAW_DB_URL = os.getenv("DATABASE_URL", "").strip()

if RAW_DB_URL:
    # Railway passes postgres:// which SQLAlchemy >=1.4 expects as postgresql://
    if RAW_DB_URL.startswith("postgres://"):
        DB_URL = RAW_DB_URL.replace("postgres://", "postgresql://", 1)
    else:
        DB_URL = RAW_DB_URL
    IS_POSTGRES = True
    engine = create_engine(DB_URL, pool_pre_ping=True)
    PG_CONNECT_URL = DB_URL.replace("postgresql+psycopg2://", "postgresql://")
else:
    DB_URL = f"sqlite:///{DB_PATH}"
    IS_POSTGRES = False
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    PG_CONNECT_URL = ""

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class PostgresCursorWrapper:
    """
    Wraps psycopg2 RealDictCursor to provide transparent compatibility with
    standard DB-API SQLite syntax:
    1. Automatically translates '?' parameter markers to '%s'.
    2. Implements .lastrowid for INSERT statements via RETURNING id.
    """
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self.lastrowid = None

    def _convert_placeholders(self, query: str) -> str:
        in_single = False
        in_double = False
        out = []
        for ch in query:
            if ch == "'" and not in_double:
                in_single = not in_single
                out.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                out.append(ch)
            elif ch == '?' and not in_single and not in_double:
                out.append('%s')
            else:
                out.append(ch)
        return "".join(out)

    def execute(self, query: str, params=None):
        converted = self._convert_placeholders(query)
        trimmed = converted.strip()
        is_insert = trimmed.upper().startswith("INSERT INTO")
        has_returning = "RETURNING" in trimmed.upper()

        if is_insert and not has_returning:
            returning_query = f"{converted.rstrip().rstrip(';')} RETURNING id"
            try:
                if params is not None:
                    self._cursor.execute(returning_query, params)
                else:
                    self._cursor.execute(returning_query)
                row = self._cursor.fetchone()
                if row and "id" in row:
                    self.lastrowid = row["id"]
                return self
            except Exception:
                # If RETURNING id isn't supported on this specific entity, fall through
                pass

        if params is not None:
            self._cursor.execute(converted, params)
        else:
            self._cursor.execute(converted)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class PostgresConnectionWrapper:
    """Wraps psycopg2 connection to return PostgresCursorWrapper."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_session():
    """FastAPI dependency for yielding SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db():
    """
    Returns a connection compatible with raw cursor executions.
    Supports SQLite Row factory and PostgreSQL RealDictCursor with seamless adapter.
    """
    if IS_POSTGRES:
        conn = psycopg2.connect(PG_CONNECT_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return PostgresConnectionWrapper(conn)
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Initializes tables, migrates missing columns, and seeds default records."""
    # 1. Create all SQLAlchemy models
    Base.metadata.create_all(bind=engine)

    # 2. Add user_id column if upgrading from earlier legacy schema
    tables_to_check = ["invoices", "transactions", "compliance_records", "emails"]
    if not IS_POSTGRES:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        for t in tables_to_check:
            try:
                cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})").fetchall()]
                if cols and "user_id" not in cols:
                    c.execute(f"ALTER TABLE {t} ADD COLUMN user_id INTEGER")
            except Exception as ex:
                pass
        conn.commit()
        conn.close()

    # 3. Seed initial compliance & settings data if empty
    session: Session = SessionLocal()
    try:
        # Check settings
        existing_keys = {s.key for s in session.query(Setting).all()}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in existing_keys:
                session.add(Setting(key=k, value=str(v)))

        # Check compliance records
        count_comp = session.query(ComplianceRecord).count()
        if count_comp == 0:
            compliance_items = [
                ("GSTR_1", "GSTR-1 (Outward Supplies Return)", "Monthly", 11, "Details of all outward sales supplies. Crucial for customer Input Tax Credit (ITC).", "Late fee: ₹50/day (₹20/day for Nil return)"),
                ("GSTR_3B", "GSTR-3B (Summary Return & Tax Payment)", "Monthly", 20, "Summary return declaring outward supplies, eligible ITC, and cash tax liability payment.", "Late fee: ₹50/day + 18% annual interest on delayed tax"),
                ("TDS_DEPOSIT", "TDS Deposit for Prev Month", "Monthly", 7, "Challan ITNS 281 deposit for Tax Deducted at Source on contractor/rent/professional fees.", "Interest of 1.5% per month for late deposit"),
                ("ADVANCE_TAX_Q3", "Advance Tax (3rd Instalment - 75%)", "Quarterly", 15, "Payment of 75% of total estimated income tax liability for current fiscal year.", "Interest under Sec 234B & 234C applies for shortfall"),
                ("GSTR_9", "Annual Return (GSTR-9 / 9C)", "Annual", 31, "Comprehensive reconciliation return for the financial year.", "Late fee: ₹200/day")
            ]

            now = datetime.now()
            for code, title, freq, due_day, desc, penalty in compliance_items:
                year = now.year
                month = now.month
                if code == "GSTR_9":
                    # Annual return is due on 31st December
                    due_date_str = f"{year:04d}-12-31" if (now.month < 12 or (now.month == 12 and now.day <= 31)) else f"{year + 1:04d}-12-31"
                elif code == "ADVANCE_TAX_Q3":
                    # Advance Tax Q3 instalment is due on 15th December
                    due_date_str = f"{year:04d}-12-15" if (now.month < 12 or (now.month == 12 and now.day <= 15)) else f"{year + 1:04d}-12-15"
                else:
                    # Monthly returns (GSTR-1 on 11th, GSTR-3B on 20th, TDS on 7th)
                    if due_day < now.day:
                        month = month + 1 if month < 12 else 1
                        if month == 1:
                            year += 1
                    due_date_str = f"{year:04d}-{month:02d}-{due_day:02d}"

                rec = ComplianceRecord(
                    code=code,
                    title=title,
                    frequency=freq,
                    due_day=due_day,
                    next_due_date=due_date_str,
                    description=desc,
                    penalty_info=penalty,
                    status="pending"
                )
                session.add(rec)

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[init_db] Seed error: {e}")
    finally:
        session.close()

def get_all_settings(user_id: Optional[int] = None) -> Dict[str, str]:
    """Retrieve settings dictionary."""
    session: Session = SessionLocal()
    try:
        rows = session.query(Setting).all()
        result = {r.key: r.value for r in rows}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in result:
                result[k] = str(v)
        return result
    finally:
        session.close()

def update_settings(updates: Dict[str, str], user_id: Optional[int] = None):
    """Upsert settings."""
    session: Session = SessionLocal()
    try:
        for k, v in updates.items():
            existing = session.query(Setting).filter(Setting.key == k).first()
            if existing:
                existing.value = str(v)
            else:
                session.add(Setting(key=k, value=str(v)))
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

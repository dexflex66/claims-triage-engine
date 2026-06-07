"""Service dependencies."""
from __future__ import annotations

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from shared.models import Student, StudentCategory
from shared.store import load_hostel


def confirm_retention(student: Student, now: datetime) -> Student:
    """Confirm retention for a returning student and issue a deterministic receipt."""
    if student.category is not StudentCategory.RETURNING:
        raise ValueError("only returning students can confirm retention")
    if student.retention_confirmed and student.retention_receipt_id:
        return student

    payload = student.model_dump()
    payload.update(
        {
            "retention_confirmed": True,
            "retention_confirmed_at": now,
            "retention_receipt_id": f"RET-{_hostel_id()}-{_receipt_suffix(student, now)}",
        }
    )
    return Student.model_validate(payload)


def _hostel_id() -> str:
    try:
        return load_hostel().id.upper()
    except Exception:
        return "HOSTEL"


def _receipt_suffix(student: Student, now: datetime) -> str:
    seed = f"{student.id}|{now.isoformat()}".encode()
    return sha256(seed).hexdigest()[:6]

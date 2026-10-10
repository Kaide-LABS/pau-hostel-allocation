from __future__ import annotations

import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from engine.explain import REASON_CODES, build_explanation, explain_code, fmt_dt
from engine.retention import confirm_retention
from shared.models import Student, StudentCategory
from shared.store import load_students


def test_template_exactness_for_every_reason_code() -> None:
    ctx = {
        "room": "A101",
        "confirmed_at": datetime(2026, 7, 2, 10, 14),
        "receipt": "RET-PALM-3f9a1c",
        "deadline": datetime(2026, 7, 15, 23, 59),
        "reserved": 5,
        "pct": 40,
        "base": 14,
        "base_label": "vacated beds",
        "general": 9,
        "applied_at": datetime(2026, 6, 11, 14, 5),
        "pos": 3,
        "type": "quad",
    }
    expected = {
        "RETAINED_CONFIRMED": "You kept room A101. You confirmed retention on 02 Jul 2026 10:14 (receipt RET-PALM-3f9a1c).",
        "RETENTION_NOT_CONFIRMED": "Your room was released because no retention confirmation was recorded.",
        "RETENTION_AFTER_DEADLINE": "Your confirmation on 02 Jul 2026 10:14 came after the deadline of 15 Jul 2026 23:59.",
        "FRESHER_RESERVED_SEAT": "You received one of 5 seats reserved for new students (40% of 14 vacated beds).",
        "FRESHER_RESERVATION_FULL": "All 5 seats reserved for new students were filled. You are #3 on the waitlist.",
        "NO_OFFER_LETTER": "Reserved seats require a valid Offer of Provisional Admission letter, and none is on record.",
        "GENERAL_POOL_ALLOCATED": "You were allocated from the 9 general beds, in application order (applied 11 Jun 2026 14:05).",
        "GENERAL_POOL_FULL": "All 9 general beds were filled before your application (11 Jun 2026 14:05). You are #3 on the waitlist.",
        "PREFERENCE_UNAVAILABLE": "Your preferred room type was full, so you were placed in a quad room.",
    }

    assert REASON_CODES == tuple(expected)
    for code, sentence in expected.items():
        actual = explain_code(code, ctx)
        assert actual == sentence
        assert "{" not in actual
        assert "}" not in actual


def test_retained_confirmed_variant_when_confirmation_not_required() -> None:
    ctx = {"room": "A101", "confirmed_at": None}

    assert explain_code("RETAINED_CONFIRMED", ctx) == (
        "You kept room A101. Retention confirmation was not required under the current rules."
    )


def test_datetime_format_unknown_code_missing_key_empty_codes_and_joining() -> None:
    ctx = {
        "reserved": 5,
        "pct": 40,
        "base": 14,
        "base_label": "vacated beds",
        "pos": 2,
    }

    assert fmt_dt(datetime(2026, 7, 2, 10, 14)) == "02 Jul 2026 10:14"
    assert build_explanation(
        ["FRESHER_RESERVED_SEAT", "FRESHER_RESERVATION_FULL"], ctx
    ) == (
        "You received one of 5 seats reserved for new students (40% of 14 vacated beds). "
        "All 5 seats reserved for new students were filled. You are #2 on the waitlist."
    )
    with pytest.raises(ValueError):
        explain_code("NOT_A_CODE", ctx)
    with pytest.raises(KeyError):
        explain_code("GENERAL_POOL_FULL", ctx)
    with pytest.raises(KeyError):
        explain_code("RETAINED_CONFIRMED", {"room": "A101"})
    with pytest.raises(ValueError):
        build_explanation([], ctx)


def test_confirm_retention_happy_path_uses_fixture_hostel_and_does_not_mutate_input() -> None:
    student = _student("R02")
    before = student.model_dump()
    now = datetime(2026, 7, 12, 9, 30)

    confirmed = confirm_retention(student, now)

    assert student.model_dump() == before
    assert confirmed.retention_confirmed is True
    assert confirmed.retention_confirmed_at == now
    assert confirmed.retention_receipt_id is not None
    assert confirmed.retention_receipt_id.startswith("RET-PALM-")
    assert re.fullmatch(r"RET-[A-Z0-9]+-[0-9a-f]{6}", confirmed.retention_receipt_id)
    assert Student.model_validate(confirmed.model_dump()) == confirmed
    assert confirmed is not student


def test_confirm_retention_uses_fallback_hostel_when_load_hostel_fails(monkeypatch) -> None:
    def raise_load_error():
        raise RuntimeError("fixture unavailable")

    monkeypatch.setattr("engine.retention.load_hostel", raise_load_error)

    confirmed = confirm_retention(_student("R02"), datetime(2026, 7, 12, 9, 30))

    assert confirmed.retention_receipt_id is not None
    assert confirmed.retention_receipt_id.startswith("RET-HOSTEL-")
    assert re.fullmatch(r"RET-[A-Z0-9]+-[0-9a-f]{6}", confirmed.retention_receipt_id)


def test_confirm_retention_rejects_transfer_and_fresher() -> None:
    for student_id in ("T01", "F01"):
        with pytest.raises(ValueError):
            confirm_retention(_student(student_id), datetime(2026, 7, 12, 9, 30))


def test_confirm_retention_is_idempotent_for_already_confirmed_student() -> None:
    student = _student("R01")

    confirmed = confirm_retention(student, datetime(2026, 8, 1, 9, 30))

    assert confirmed == student
    assert confirmed.retention_confirmed_at == student.retention_confirmed_at
    assert confirmed.retention_receipt_id == student.retention_receipt_id


def test_confirm_retention_issues_receipt_for_confirmed_student_without_receipt() -> None:
    student = Student.model_validate(
        {
            **_student("R01").model_dump(),
            "retention_receipt_id": None,
        }
    )
    now = datetime(2026, 7, 12, 9, 30)

    confirmed = confirm_retention(student, now)

    assert confirmed is not student
    assert confirmed.retention_confirmed is True
    assert confirmed.retention_confirmed_at == now
    assert confirmed.retention_receipt_id is not None
    assert re.fullmatch(r"RET-[A-Z0-9]+-[0-9a-f]{6}", confirmed.retention_receipt_id)


def test_confirm_retention_is_deterministic_and_changes_with_now() -> None:
    student = _student("R02")
    now = datetime(2026, 7, 12, 9, 30)
    later = datetime(2026, 7, 12, 9, 31)

    first = confirm_retention(student, now)
    second = confirm_retention(student, now)
    third = confirm_retention(student, later)

    assert first.retention_receipt_id == second.retention_receipt_id
    assert first.retention_receipt_id != third.retention_receipt_id


def test_fixture_student_categories_used_by_retention_tests() -> None:
    assert _student("R02").category is StudentCategory.RETURNING
    assert _student("T01").category is StudentCategory.TRANSFER
    assert _student("F01").category is StudentCategory.FRESHER


# Phase 2 allocation tests belong below this marker.


def _student(student_id: str):
    return next(student for student in load_students() if student.id == student_id)

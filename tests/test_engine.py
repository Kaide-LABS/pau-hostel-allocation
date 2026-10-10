from __future__ import annotations

import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from engine.explain import REASON_CODES, TEMPLATES, build_explanation, explain_code, fmt_dt
from engine.allocate import allocate
from engine.retention import confirm_retention
from shared.models import Hostel, OutcomeStatus, Room, Rules, Student, StudentCategory
from shared.store import load_default_rules, load_hostel, load_students


def test_template_exactness_for_every_reason_code() -> None:
    ctx = {
        "room": "A101",
        "confirmed_at": datetime(2026, 7, 2, 10, 14),
        "receipt": "RET-PALM-3f9a1c",
        "deadline": datetime(2026, 7, 15, 23, 59),
        "reserved": 5,
        "pct": 40,
        "base": 14,
        "base_label": "available beds",
        "general": 9,
        "applied_at": datetime(2026, 6, 11, 14, 5),
        "pos": 3,
        "type": "quad",
    }
    expected = {
        "RETAINED_CONFIRMED": "You kept room A101. You confirmed retention on 02 Jul 2026 10:14 (receipt RET-PALM-3f9a1c).",
        "RETENTION_NOT_CONFIRMED": "Your room was released because no retention confirmation was recorded.",
        "RETENTION_AFTER_DEADLINE": "Your confirmation on 02 Jul 2026 10:14 came after the deadline of 15 Jul 2026 23:59.",
        "FRESHER_RESERVED_SEAT": "You received one of 5 seats reserved for new students (40% of 14 available beds).",
        "FRESHER_RESERVATION_FULL": "All 5 seats reserved for new students were filled. You are #3 on the waitlist.",
        "NO_OFFER_LETTER": "Reserved seats require a valid Offer of Provisional Admission letter, and none is on record.",
        "GENERAL_POOL_ALLOCATED": "You were allocated from the 9 general beds, in application order (applied 11 Jun 2026 14:05).",
        "GENERAL_POOL_FULL": "All 9 general beds were filled before your application (11 Jun 2026 14:05). You are #3 on the waitlist.",
        "PREFERENCE_UNAVAILABLE": "Your preferred room type was full, so you were placed in a quad room.",
    }

    assert REASON_CODES == tuple(expected)
    assert tuple(TEMPLATES) == REASON_CODES
    for code, sentence in expected.items():
        actual = explain_code(code, ctx)
        assert actual == sentence
        assert "{" not in actual
        assert "}" not in actual


def test_retained_confirmed_variant_when_confirmation_not_required() -> None:
    ctx = {"room": "A101", "confirmed_at": None, "confirmation_required": False}

    assert explain_code("RETAINED_CONFIRMED", ctx) == (
        "You kept room A101. Retention confirmation was not required under the current rules."
    )


def test_retained_confirmed_variants_do_not_leak_none() -> None:
    assert explain_code(
        "RETAINED_CONFIRMED",
        {
            "room": "A101",
            "confirmed_at": datetime(2026, 7, 2, 10, 14),
            "receipt": None,
        },
    ) == "You kept room A101. You confirmed retention on 02 Jul 2026 10:14."
    assert explain_code(
        "RETAINED_CONFIRMED",
        {
            "room": "A101",
            "confirmed_at": None,
            "receipt": "RET-PALM-3f9a1c",
        },
    ) == "You kept room A101. Your retention confirmation is on record (receipt RET-PALM-3f9a1c)."
    assert explain_code(
        "RETAINED_CONFIRMED",
        {
            "room": "A101",
            "confirmed_at": None,
            "receipt": None,
        },
    ) == "You kept room A101. Your retention confirmation is on record."


def test_datetime_format_unknown_code_missing_key_empty_codes_and_joining() -> None:
    ctx = {
        "reserved": 5,
        "pct": 40,
        "base": 14,
        "base_label": "available beds",
        "pos": 2,
    }

    assert fmt_dt(datetime(2026, 7, 2, 10, 14)) == "02 Jul 2026 10:14"
    assert build_explanation(
        ["FRESHER_RESERVED_SEAT", "FRESHER_RESERVATION_FULL"], ctx
    ) == (
        "You received one of 5 seats reserved for new students (40% of 14 available beds). "
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


def test_fixture_allocation_matches_40_percent_acceptance_numbers() -> None:
    result = _allocation()
    by_id = _outcomes_by_id(result)

    assert result.summary.model_dump() == {
        "total_beds": 24,
        "retained": 10,
        "available_beds": 14,
        "reserved_for_freshers": 5,
        "freshers_allocated": 5,
        "general_allocated": 9,
        "waitlisted": 6,
        "rejected": 2,
    }
    assert [sid for sid, outcome in by_id.items() if "FRESHER_RESERVED_SEAT" in outcome.reason_codes] == [
        "F01",
        "F02",
        "F03",
        "F04",
        "F05",
    ]
    assert [sid for sid, outcome in by_id.items() if outcome.status is OutcomeStatus.REJECTED] == [
        "F11",
        "F12",
    ]
    assert [
        (outcome.student_id, outcome.waitlist_position)
        for outcome in result.outcomes
        if outcome.status is OutcomeStatus.WAITLISTED
    ] == [("R08", 6), ("F06", 1), ("F07", 2), ("F08", 3), ("F09", 4), ("F10", 5)]
    assert by_id["R08"].reason_codes == ["RETENTION_AFTER_DEADLINE", "GENERAL_POOL_FULL"]
    for student_id in ("R02", "R06", "R14"):
        assert by_id[student_id].reason_codes[0] == "RETENTION_NOT_CONFIRMED"
        assert by_id[student_id].reason_codes[1] == "GENERAL_POOL_ALLOCATED"


def test_fixture_allocation_invariants_and_room_capacity() -> None:
    hostel = load_hostel()
    students = load_students()
    result = allocate(hostel, students, load_default_rules(), _now())
    by_id = _outcomes_by_id(result)

    assert len(by_id) == len(students)
    assert set(by_id) == {student.id for student in students}
    allocated = [outcome for outcome in result.outcomes if outcome.status is OutcomeStatus.ALLOCATED]
    assert len(allocated) <= result.summary.total_beds

    occupancy = {room.id: 0 for room in hostel.rooms}
    for outcome in allocated:
        assert outcome.room_id is not None
        occupancy[outcome.room_id] += 1
    capacities = {room.id: room.capacity for room in hostel.rooms}
    assert all(count <= capacities[room_id] for room_id, count in occupancy.items())

    valid_codes = set(REASON_CODES)
    for outcome in result.outcomes:
        assert outcome.reason_codes
        assert set(outcome.reason_codes) <= valid_codes
        assert "{" not in outcome.explanation
        assert "}" not in outcome.explanation
        assert "None" not in outcome.explanation

    deadline = load_default_rules().retention_deadline
    assert deadline is not None
    for student in students:
        if (
            student.category is StudentCategory.RETURNING
            and student.current_room_id
            and student.retention_confirmed
            and student.retention_confirmed_at is not None
            and student.retention_confirmed_at <= deadline
        ):
            assert by_id[student.id].status is OutcomeStatus.ALLOCATED
            assert by_id[student.id].room_id == student.current_room_id
            assert by_id[student.id].reason_codes == ["RETAINED_CONFIRMED"]

    fresher_reserved = sum(
        1 for outcome in result.outcomes if "FRESHER_RESERVED_SEAT" in outcome.reason_codes
    )
    assert fresher_reserved <= result.summary.reserved_for_freshers


def test_fixture_allocation_is_deterministic_even_when_input_order_changes() -> None:
    hostel = load_hostel()
    students = load_students()
    rules = load_default_rules()

    first = allocate(hostel, students, rules, _now())
    second = allocate(hostel, students, rules, _now())
    shuffled = allocate(hostel, list(reversed(students)), rules, _now())

    assert first.summary == second.summary
    assert [outcome.model_dump() for outcome in first.outcomes] == [
        outcome.model_dump() for outcome in second.outcomes
    ]
    assert {
        outcome.student_id: outcome.model_dump(exclude={"student_id"})
        for outcome in first.outcomes
    } == {
        outcome.student_id: outcome.model_dump(exclude={"student_id"})
        for outcome in shuffled.outcomes
    }


def test_30_percent_rule_changes_reserved_general_and_outcomes() -> None:
    rules = load_default_rules().model_copy(update={"fresher_reservation_pct": 30})
    forty = _allocation()
    thirty = _allocation(rules)
    forty_by_id = _outcomes_by_id(forty)
    thirty_by_id = _outcomes_by_id(thirty)

    assert forty.summary.reserved_for_freshers == 5
    assert thirty.summary.reserved_for_freshers == 4
    assert thirty.summary.general_allocated == 10
    assert thirty_by_id["R08"].status is OutcomeStatus.ALLOCATED
    assert thirty_by_id["F05"].status is OutcomeStatus.WAITLISTED
    assert forty_by_id["F05"].explanation != thirty_by_id["F05"].explanation


def test_all_reason_codes_are_exercised_across_40_and_30_percent_runs() -> None:
    codes = set()
    for result in (_allocation(), _allocation(load_default_rules().model_copy(update={"fresher_reservation_pct": 30}))):
        for outcome in result.outcomes:
            codes.update(outcome.reason_codes)

    assert codes == set(REASON_CODES)


def test_allocate_does_not_mutate_inputs() -> None:
    hostel = load_hostel()
    students = load_students()
    rules = load_default_rules()
    before = (hostel.model_dump(), [student.model_dump() for student in students], rules.model_dump())

    allocate(hostel, students, rules, _now())

    assert (hostel.model_dump(), [student.model_dump() for student in students], rules.model_dump()) == before


def test_edge_rules_reservation_base_pct_release_and_fresher_general_pool() -> None:
    hostel = _small_hostel()
    students = [
        _make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 7, 1), "single"),
        _make_student("F1", StudentCategory.FRESHER, None, False, datetime(2026, 6, 1), "single", True),
        _make_student("F2", StudentCategory.FRESHER, None, False, datetime(2026, 6, 2), "single", True),
        _make_student("F3", StudentCategory.FRESHER, None, False, datetime(2026, 6, 3), "single", True),
    ]

    capped = allocate(hostel, students, _rules(fresher_reservation_pct=100, reservation_base="total_beds"), _now())
    assert capped.summary.reserved_for_freshers == 2
    assert capped.summary.freshers_allocated == 2

    zero = allocate(hostel, students, _rules(fresher_reservation_pct=0), _now())
    assert zero.summary.reserved_for_freshers == 0
    assert zero.summary.general_allocated == 0

    release_students = [
        students[0],
        students[1],
        _make_student("T1", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 4), "double"),
    ]
    released = allocate(hostel, release_students, _rules(fresher_reservation_pct=100, unused_reservation_released=True), _now())
    unreleased = allocate(hostel, release_students, _rules(fresher_reservation_pct=100, unused_reservation_released=False), _now())
    assert released.summary.general_allocated == 1
    assert unreleased.summary.general_allocated == 0

    competing = allocate(
        hostel,
        students,
        _rules(fresher_reservation_pct=50, freshers_may_compete_for_general_pool=True),
        _now(),
    )
    by_id = _outcomes_by_id(competing)
    assert by_id["F3"].reason_codes == ["FRESHER_RESERVATION_FULL", "GENERAL_POOL_FULL"]


def test_edge_rules_offer_letter_retention_deadline_and_preferences() -> None:
    hostel = _small_hostel()
    no_offer = _make_student("F1", StudentCategory.FRESHER, None, False, datetime(2026, 6, 1), "single", False)
    assert _outcomes_by_id(allocate(hostel, [no_offer], _rules(fresher_requires_offer_letter=False), _now()))["F1"].status is OutcomeStatus.ALLOCATED

    unconfirmed = _make_student("R1", StudentCategory.RETURNING, "A1", False, datetime(2026, 6, 1), "single")
    no_confirmation_required = allocate(hostel, [unconfirmed], _rules(retention_requires_confirmation=False), _now())
    outcome = no_confirmation_required.outcomes[0]
    assert outcome.reason_codes == ["RETAINED_CONFIRMED"]
    assert "not required" in outcome.explanation

    deadline_none = allocate(hostel, [unconfirmed], _rules(retention_deadline=None), _now())
    assert deadline_none.outcomes[0].status is OutcomeStatus.ALLOCATED
    assert deadline_none.outcomes[0].reason_codes == [
        "RETENTION_NOT_CONFIRMED",
        "GENERAL_POOL_ALLOCATED",
    ]

    confirmed_no_time = _make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), "single")
    confirmed_no_time = Student.model_validate({**confirmed_no_time.model_dump(), "retention_confirmed_at": None})
    assert allocate(hostel, [confirmed_no_time], _rules(), _now()).outcomes[0].reason_codes == [
        "RETENTION_NOT_CONFIRMED",
        "GENERAL_POOL_ALLOCATED",
    ]

    returning_no_room = _make_student("R1", StudentCategory.RETURNING, None, False, datetime(2026, 6, 1), None)
    assert allocate(hostel, [returning_no_room], _rules(), _now()).outcomes[0].reason_codes == [
        "GENERAL_POOL_ALLOCATED"
    ]
    assert allocate(hostel, [], _rules(), _now()).summary.total_beds == 3

    preference_students = [
        _make_student("F1", StudentCategory.FRESHER, None, False, datetime(2026, 6, 1), "single", True),
        _make_student("F2", StudentCategory.FRESHER, None, False, datetime(2026, 6, 2), "single", True),
        _make_student("F3", StudentCategory.FRESHER, None, False, datetime(2026, 6, 3), None, True),
    ]
    preference_result = allocate(hostel, preference_students, _rules(fresher_reservation_pct=100), _now())
    preference_by_id = _outcomes_by_id(preference_result)
    assert "PREFERENCE_UNAVAILABLE" in preference_by_id["F2"].reason_codes
    assert "PREFERENCE_UNAVAILABLE" not in preference_by_id["F3"].reason_codes


def test_retained_confirmed_allocation_variants_do_not_leak_none() -> None:
    hostel = _small_hostel()
    with_no_receipt = Student.model_validate(
        {
            **_make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), "single").model_dump(),
            "retention_receipt_id": None,
        }
    )
    with_no_time = Student.model_validate(
        {
            **_make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), "single").model_dump(),
            "retention_confirmed_at": None,
        }
    )

    no_receipt = allocate(hostel, [with_no_receipt], _rules(), _now()).outcomes[0]
    no_time = allocate(hostel, [with_no_time], _rules(retention_deadline=None), _now()).outcomes[0]

    assert no_receipt.explanation == "You kept room A1. You confirmed retention on 01 Jul 2026 08:00."
    assert no_time.explanation == "You kept room A1. Your retention confirmation is on record (receipt RET-TINY-r1123)."
    assert "None" not in no_receipt.explanation
    assert "None" not in no_time.explanation


def test_waitlist_positions_are_global_tiebreak_order() -> None:
    result = _allocation()
    waitlisted = [outcome for outcome in result.outcomes if outcome.status is OutcomeStatus.WAITLISTED]
    by_student = {student.id: student for student in load_students()}

    assert [outcome.waitlist_position for outcome in waitlisted] == [6, 1, 2, 3, 4, 5]
    assert [
        outcome.student_id
        for outcome in sorted(
            waitlisted,
            key=lambda outcome: (
                outcome.waitlist_position,
                by_student[outcome.student_id].applied_at,
                outcome.student_id,
            ),
        )
    ] == ["F06", "F07", "F08", "F09", "F10", "R08"]


def test_identical_applied_at_uses_student_id_tiebreak_in_reserved_and_general_pools() -> None:
    hostel = _small_hostel()
    same_time = datetime(2026, 6, 1, 8, 0)
    reserved_students = [
        _make_student("F2", StudentCategory.FRESHER, None, False, same_time, None, True),
        _make_student("F1", StudentCategory.FRESHER, None, False, same_time, None, True),
    ]
    general_students = [
        _make_student("T2", StudentCategory.TRANSFER, None, False, same_time, None),
        _make_student("T1", StudentCategory.TRANSFER, None, False, same_time, None),
    ]

    reserved = allocate(hostel, reserved_students, _rules(fresher_reservation_pct=50), _now())
    one_general_bed = Hostel(
        id="ONE",
        name="One Bed Hall",
        rooms=[Room(id="A1", type="single", capacity=1, price_naira=1)],
    )
    general = allocate(one_general_bed, general_students, _rules(fresher_reservation_pct=0), _now())

    assert _outcomes_by_id(reserved)["F1"].status is OutcomeStatus.ALLOCATED
    assert _outcomes_by_id(reserved)["F2"].status is OutcomeStatus.WAITLISTED
    assert _outcomes_by_id(general)["T1"].status is OutcomeStatus.ALLOCATED
    assert _outcomes_by_id(general)["T2"].status is OutcomeStatus.WAITLISTED
    assert _outcomes_by_id(general)["T1"].room_id == "A1"


def test_rooms_are_filled_in_hostel_room_order() -> None:
    hostel = _small_hostel()
    students = [
        _make_student("T2", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 2), None),
        _make_student("T1", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 1), None),
        _make_student("T3", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 3), None),
    ]

    result = allocate(hostel, students, _rules(fresher_reservation_pct=0), _now())
    by_id = _outcomes_by_id(result)

    assert by_id["T1"].room_id == "A1"
    assert by_id["T2"].room_id == "B1"
    assert by_id["T3"].room_id == "B1"


def test_every_returning_student_retained_leaves_only_vacated_bed_reservation_and_zero_student_case() -> None:
    hostel = _small_hostel()
    retained = [
        _make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), None),
        _make_student("R2", StudentCategory.RETURNING, "B1", True, datetime(2026, 6, 2), None),
        _make_student("R3", StudentCategory.RETURNING, "B1", True, datetime(2026, 6, 3), None),
        _make_student("F1", StudentCategory.FRESHER, None, False, datetime(2026, 6, 4), None, True),
    ]

    full = allocate(hostel, retained, _rules(fresher_reservation_pct=100), _now())
    empty = allocate(hostel, [], _rules(), _now())

    assert full.summary.available_beds == 0
    assert full.summary.reserved_for_freshers == 0
    assert _outcomes_by_id(full)["F1"].status is OutcomeStatus.WAITLISTED
    assert empty.summary.model_dump() == {
        "total_beds": 3,
        "retained": 0,
        "available_beds": 3,
        "reserved_for_freshers": 1,
        "freshers_allocated": 0,
        "general_allocated": 0,
        "waitlisted": 0,
        "rejected": 0,
    }


def test_validation_errors_and_mixed_timezone_error() -> None:
    hostel = _small_hostel()
    student = _make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), "single")
    with pytest.raises(ValueError, match="duplicate student ids"):
        allocate(hostel, [student, student], _rules(), _now())
    with pytest.raises(ValueError, match="duplicate room ids"):
        allocate(Hostel(id="H", name="H", rooms=[hostel.rooms[0], hostel.rooms[0]]), [student], _rules(), _now())
    with pytest.raises(ValueError, match="not in the hostel"):
        allocate(hostel, [_make_student("R1", StudentCategory.RETURNING, "ZZ", True, datetime(2026, 6, 1), None)], _rules(), _now())
    with pytest.raises(ValueError, match="exceed room capacity"):
        allocate(
            hostel,
            [
                _make_student("R1", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 1), None),
                _make_student("R2", StudentCategory.RETURNING, "A1", True, datetime(2026, 6, 2), None),
            ],
            _rules(),
            _now(),
        )

    aware_rules = _rules(retention_deadline=datetime.fromisoformat("2026-07-15T23:59:00+00:00"))
    with pytest.raises(ValueError, match="mixed naive and timezone-aware datetimes"):
        allocate(hostel, [student], aware_rules, _now())

    aware_applied = Student.model_validate(
        {
            **_make_student("T1", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 2), None).model_dump(),
            "applied_at": datetime.fromisoformat("2026-06-02T00:00:00+00:00"),
        }
    )
    naive_applied = _make_student("T2", StudentCategory.TRANSFER, None, False, datetime(2026, 6, 1), None)
    with pytest.raises(ValueError, match="mixed naive and timezone-aware datetimes"):
        allocate(hostel, [aware_applied, naive_applied], _rules(), _now())


def _student(student_id: str):
    return next(student for student in load_students() if student.id == student_id)


def _now() -> datetime:
    return datetime(2026, 8, 1, 12, 0)


def _allocation(rules: Rules | None = None):
    return allocate(load_hostel(), load_students(), rules or load_default_rules(), _now())


def _outcomes_by_id(result):
    return {outcome.student_id: outcome for outcome in result.outcomes}


def _small_hostel() -> Hostel:
    return Hostel(
        id="TINY",
        name="Tiny Hall",
        rooms=[
            Room(id="A1", type="single", capacity=1, price_naira=1),
            Room(id="B1", type="double", capacity=2, price_naira=1),
        ],
    )


def _rules(**updates) -> Rules:
    values = {"retention_deadline": datetime(2026, 7, 15, 23, 59)}
    values.update(updates)
    return Rules(**values)


def _make_student(
    student_id: str,
    category: StudentCategory,
    current_room_id: str | None,
    confirmed: bool,
    applied_at: datetime,
    preferred: str | None,
    offer: bool = False,
) -> Student:
    return Student(
        id=student_id,
        name=f"Student {student_id}",
        category=category,
        current_room_id=current_room_id,
        retention_confirmed=confirmed,
        retention_confirmed_at=datetime(2026, 7, 1, 8, 0) if confirmed else None,
        retention_receipt_id=f"RET-TINY-{student_id.lower()}123" if confirmed else None,
        has_offer_letter=offer,
        applied_at=applied_at,
        preferred_room_type=preferred,
    )

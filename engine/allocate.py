from __future__ import annotations

from datetime import datetime

from engine.explain import build_explanation
from shared.models import (
    AllocationResult,
    AllocationSummary,
    Hostel,
    OutcomeStatus,
    Rules,
    Student,
    StudentCategory,
    StudentOutcome,
)


def allocate(hostel: Hostel, students: list[Student], rules: Rules, now: datetime) -> AllocationResult:
    """Allocate rooms deterministically under the hostel rules."""
    _validate_inputs(hostel, students)

    total_beds = sum(room.capacity for room in hostel.rooms)
    retained: list[Student] = []
    retained_ids: set[str] = set()
    rejected: dict[str, list[str]] = {}
    candidate_codes: dict[str, list[str]] = {}

    for student in students:
        if student.category is StudentCategory.RETURNING and student.current_room_id:
            if _retained(student, rules):
                retained.append(student)
                retained_ids.add(student.id)
            else:
                candidate_codes[student.id] = [_retention_loss_code(student, rules)]

    _validate_retained_rooms(hostel, retained)

    available_beds = total_beds - len(retained)
    base = available_beds if rules.reservation_base == "vacated_beds" else total_beds
    reserved = min((rules.fresher_reservation_pct * base) // 100, available_beds)
    base_label = "vacated beds" if rules.reservation_base == "vacated_beds" else "total beds"

    freshers = [student for student in students if student.category is StudentCategory.FRESHER]
    eligible_freshers: list[Student] = []
    for student in freshers:
        if rules.fresher_requires_offer_letter and not student.has_offer_letter:
            rejected[student.id] = ["NO_OFFER_LETTER"]
        else:
            eligible_freshers.append(student)

    reserved_freshers = _sort_students(eligible_freshers)[:reserved]
    reserved_ids = {student.id for student in reserved_freshers}
    freshers_filled = len(reserved_freshers)
    general = (
        available_beds - freshers_filled
        if rules.unused_reservation_released
        else available_beds - reserved
    )
    general = max(general, 0)

    general_candidates = [
        student
        for student in students
        if _is_general_candidate(student, retained_ids, reserved_ids, rejected, rules)
    ]
    general_allocated = _sort_students(general_candidates)[:general]
    general_ids = {student.id for student in general_allocated}

    allocated_students = retained + reserved_freshers + general_allocated
    room_assignments, preference_misses = _assign_rooms(hostel, retained, reserved_freshers, general_allocated)

    waitlisted = [
        student
        for student in students
        if student.id not in retained_ids
        and student.id not in reserved_ids
        and student.id not in general_ids
        and student.id not in rejected
    ]
    waitlist_positions = {
        student.id: pos for pos, student in enumerate(_sort_students(waitlisted), start=1)
    }

    outcomes_by_id: dict[str, StudentOutcome] = {}
    for student in allocated_students:
        if student.id in retained_ids:
            codes = ["RETAINED_CONFIRMED"]
        elif student.id in reserved_ids:
            codes = ["FRESHER_RESERVED_SEAT"]
        else:
            codes = [*candidate_codes.get(student.id, []), "GENERAL_POOL_ALLOCATED"]
        if student.id in preference_misses:
            codes.append("PREFERENCE_UNAVAILABLE")
        outcomes_by_id[student.id] = _outcome(
            student,
            OutcomeStatus.ALLOCATED,
            codes,
            room_assignments[student.id],
            None,
            rules,
            reserved,
            base,
            base_label,
            general,
            hostel,
        )

    for student in waitlisted:
        codes = [*candidate_codes.get(student.id, [])]
        if student.category is StudentCategory.FRESHER:
            codes.append("FRESHER_RESERVATION_FULL")
            if rules.freshers_may_compete_for_general_pool:
                codes.append("GENERAL_POOL_FULL")
        elif "GENERAL_POOL_FULL" not in codes:
            codes.append("GENERAL_POOL_FULL")
        outcomes_by_id[student.id] = _outcome(
            student,
            OutcomeStatus.WAITLISTED,
            codes,
            None,
            waitlist_positions[student.id],
            rules,
            reserved,
            base,
            base_label,
            general,
            hostel,
        )

    for student in students:
        if student.id in rejected:
            outcomes_by_id[student.id] = _outcome(
                student,
                OutcomeStatus.REJECTED,
                rejected[student.id],
                None,
                None,
                rules,
                reserved,
                base,
                base_label,
                general,
                hostel,
            )

    outcomes = [outcomes_by_id[student.id] for student in students]
    summary = AllocationSummary(
        total_beds=total_beds,
        retained=len(retained),
        available_beds=available_beds,
        reserved_for_freshers=reserved,
        freshers_allocated=len(reserved_freshers),
        general_allocated=len(general_allocated),
        waitlisted=sum(1 for outcome in outcomes if outcome.status is OutcomeStatus.WAITLISTED),
        rejected=sum(1 for outcome in outcomes if outcome.status is OutcomeStatus.REJECTED),
    )
    return AllocationResult(
        hostel_id=hostel.id,
        rules=rules,
        outcomes=outcomes,
        summary=summary,
        run_at=now,
    )


def _validate_inputs(hostel: Hostel, students: list[Student]) -> None:
    if len({student.id for student in students}) != len(students):
        raise ValueError("duplicate student ids")
    if len({room.id for room in hostel.rooms}) != len(hostel.rooms):
        raise ValueError("duplicate room ids")


def _validate_retained_rooms(hostel: Hostel, retained: list[Student]) -> None:
    rooms = {room.id: room for room in hostel.rooms}
    occupancy = {room.id: 0 for room in hostel.rooms}
    for student in retained:
        if student.current_room_id not in rooms:
            raise ValueError("retained student has a current_room_id not in the hostel")
        occupancy[student.current_room_id] += 1
    for room_id, count in occupancy.items():
        if count > rooms[room_id].capacity:
            raise ValueError("retained occupants exceed room capacity")


def _retained(student: Student, rules: Rules) -> bool:
    confirmation_ok = student.retention_confirmed or not rules.retention_requires_confirmation
    if not confirmation_ok:
        return False
    if rules.retention_deadline is None or not rules.retention_requires_confirmation:
        return True
    if student.retention_confirmed_at is None:
        return False
    try:
        return student.retention_confirmed_at <= rules.retention_deadline
    except TypeError as exc:
        raise ValueError("mixed naive and timezone-aware datetimes") from exc


def _retention_loss_code(student: Student, rules: Rules) -> str:
    if student.retention_confirmed and student.retention_confirmed_at and rules.retention_deadline:
        try:
            if student.retention_confirmed_at > rules.retention_deadline:
                return "RETENTION_AFTER_DEADLINE"
        except TypeError as exc:
            raise ValueError("mixed naive and timezone-aware datetimes") from exc
    return "RETENTION_NOT_CONFIRMED"


def _sort_students(students: list[Student]) -> list[Student]:
    return sorted(students, key=lambda student: (student.applied_at, student.id))


def _is_general_candidate(
    student: Student,
    retained_ids: set[str],
    reserved_ids: set[str],
    rejected: dict[str, list[str]],
    rules: Rules,
) -> bool:
    if student.id in retained_ids or student.id in reserved_ids or student.id in rejected:
        return False
    if student.category is StudentCategory.RETURNING:
        return True
    if student.category is StudentCategory.TRANSFER:
        return True
    return rules.freshers_may_compete_for_general_pool


def _assign_rooms(
    hostel: Hostel,
    retained: list[Student],
    reserved_freshers: list[Student],
    general_allocated: list[Student],
) -> tuple[dict[str, str], set[str]]:
    occupancy = {room.id: 0 for room in hostel.rooms}
    assignments: dict[str, str] = {}
    preference_misses: set[str] = set()
    rooms = {room.id: room for room in hostel.rooms}

    for student in retained:
        assert student.current_room_id is not None
        occupancy[student.current_room_id] += 1
        assignments[student.id] = student.current_room_id

    for student in [*reserved_freshers, *general_allocated]:
        room_id = _first_free_room(hostel, occupancy, student.preferred_room_type)
        if room_id is None:
            room_id = _first_free_room(hostel, occupancy, None)
            if room_id is None:
                raise RuntimeError("allocated student has no free bed")
            if student.preferred_room_type is not None:
                preference_misses.add(student.id)
        occupancy[room_id] += 1
        assignments[student.id] = room_id
        if student.preferred_room_type is not None and rooms[room_id].type != student.preferred_room_type:
            preference_misses.add(student.id)

    return assignments, preference_misses


def _first_free_room(hostel: Hostel, occupancy: dict[str, int], room_type: str | None) -> str | None:
    for room in hostel.rooms:
        if room_type is not None and room.type != room_type:
            continue
        if occupancy[room.id] < room.capacity:
            return room.id
    return None


def _outcome(
    student: Student,
    status: OutcomeStatus,
    codes: list[str],
    room_id: str | None,
    waitlist_position: int | None,
    rules: Rules,
    reserved: int,
    base: int,
    base_label: str,
    general: int,
    hostel: Hostel,
) -> StudentOutcome:
    room_type = None
    if room_id is not None:
        room_type = next(room.type for room in hostel.rooms if room.id == room_id)
    ctx = {
        "room": room_id,
        "confirmed_at": student.retention_confirmed_at if rules.retention_requires_confirmation else None,
        "receipt": student.retention_receipt_id,
        "deadline": rules.retention_deadline,
        "reserved": reserved,
        "pct": rules.fresher_reservation_pct,
        "base": base,
        "base_label": base_label,
        "general": general,
        "applied_at": student.applied_at,
        "pos": waitlist_position,
        "type": room_type,
    }
    return StudentOutcome(
        student_id=student.id,
        status=status,
        room_id=room_id,
        waitlist_position=waitlist_position,
        reason_codes=codes,
        explanation=build_explanation(codes, ctx),
    )

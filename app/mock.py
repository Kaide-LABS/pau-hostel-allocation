from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from math import floor
import re

from shared.models import (
    AllocationResult,
    AllocationSummary,
    CompileResult,
    Hostel,
    OutcomeStatus,
    Room,
    Rules,
    Student,
    StudentCategory,
    StudentOutcome,
)


FIXED_NOW = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
DEADLINE = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)
SAMPLE_POLICY = (
    "Hostels reserve up to 40% of available bed spaces for newly admitted students. "
    "Available bed spaces are those vacated by graduating students or by students who did not confirm they are returning. "
    "Reserved spaces may only be allocated on presentation of a valid Offer of Provisional Admission letter. "
    "Returning students who confirm retention keep their rooms."
)
AMBIGUITY = "Hostels reserve up to 40% of available bed spaces for newly admitted students."
UNMAPPED = "Available bed spaces are those vacated by graduating students or by students who did not confirm they are returning."


HOSTEL = Hostel(
    id="palmgrove",
    name="Palmgrove Hall",
    rooms=[
        Room(id="P101", type="single", capacity=1, price_naira=700000),
        Room(id="P102", type="double", capacity=2, price_naira=520000),
        Room(id="P103", type="double", capacity=2, price_naira=520000),
        Room(id="P201", type="quad", capacity=4, price_naira=380000),
    ],
)

STUDENTS = [
    Student(
        id="ret-on-time",
        name="Student Ada Test",
        category=StudentCategory.RETURNING,
        current_room_id="P101",
        retention_confirmed=True,
        retention_confirmed_at=datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc),
        retention_receipt_id="RET-PALM-111aaa",
        applied_at=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        preferred_room_type="single",
    ),
    Student(
        id="ret-unconfirmed",
        name="Student Bayo Sample",
        category=StudentCategory.RETURNING,
        current_room_id="P102",
        applied_at=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
        preferred_room_type="double",
    ),
    Student(
        id="ret-late",
        name="Student Cora Demo",
        category=StudentCategory.RETURNING,
        current_room_id="P103",
        retention_confirmed=True,
        retention_confirmed_at=datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc),
        retention_receipt_id="RET-PALM-222bbb",
        applied_at=datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc),
        preferred_room_type="double",
    ),
    Student(id="tr-1", name="Student Dami Mock", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc), preferred_room_type="single"),
    Student(id="tr-2", name="Student Efe Trial", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
    Student(id="tr-3", name="Student Fola Case", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 11, 9, 0, tzinfo=timezone.utc), preferred_room_type="double"),
    Student(id="tr-4", name="Student Miro Harness", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 13, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
    Student(id="tr-5", name="Student Nia Widget", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc), preferred_room_type="double"),
    Student(id="tr-6", name="Student Osa Scenario", category=StudentCategory.TRANSFER, applied_at=datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
    Student(id="fr-1", name="Student Gita Placeholder", category=StudentCategory.FRESHER, has_offer_letter=True, applied_at=datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc), preferred_room_type="single"),
    Student(id="fr-2", name="Student Hadi Fixture", category=StudentCategory.FRESHER, has_offer_letter=True, applied_at=datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc), preferred_room_type="double"),
    Student(id="fr-3", name="Student Imani Example", category=StudentCategory.FRESHER, has_offer_letter=True, applied_at=datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
    Student(id="fr-4", name="Student Juno Synthetic", category=StudentCategory.FRESHER, has_offer_letter=True, applied_at=datetime(2026, 9, 9, 9, 0, tzinfo=timezone.utc), preferred_room_type="double"),
    Student(id="fr-5", name="Student Kemi Prototype", category=StudentCategory.FRESHER, has_offer_letter=False, applied_at=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
    Student(id="fr-6", name="Student Lani Sandbox", category=StudentCategory.FRESHER, has_offer_letter=True, applied_at=datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc), preferred_room_type="quad"),
]

RULES = Rules(fresher_reservation_pct=40, retention_deadline=DEADLINE, source_text=SAMPLE_POLICY)


def _dt(value: datetime | None) -> str:
    return "" if value is None else value.isoformat()


def _base_and_reserved(hostel: Hostel, retained: int, rules: Rules) -> tuple[int, int, int, str]:
    total_beds = sum(room.capacity for room in hostel.rooms)
    available = total_beds - retained
    base = available if rules.reservation_base == "vacated_beds" else total_beds
    reserved = min(floor(rules.fresher_reservation_pct / 100 * base), available)
    label = "available beds" if rules.reservation_base == "vacated_beds" else "total beds"
    return available, base, reserved, label


def _retained(student: Student, rules: Rules) -> bool:
    if student.category != StudentCategory.RETURNING or not student.current_room_id:
        return False
    if not rules.retention_requires_confirmation:
        return True
    confirmed = student.retention_confirmed or not rules.retention_requires_confirmation
    if not confirmed:
        return False
    if rules.retention_deadline and student.retention_confirmed_at:
        return student.retention_confirmed_at <= rules.retention_deadline
    return True


def _copy_model(model):
    return model.model_copy(deep=True)


def allocate(hostel: Hostel, students: list[Student], rules: Rules, now: datetime) -> AllocationResult:
    total_beds = sum(room.capacity for room in hostel.rooms)
    retained_students = [s for s in students if _retained(s, rules)]
    available, base, reserved, base_label = _base_and_reserved(hostel, len(retained_students), rules)
    outcomes: dict[str, StudentOutcome] = {}
    allocated_order: list[str] = []

    for student in sorted(retained_students, key=lambda s: (s.applied_at, s.id)):
        outcomes[student.id] = StudentOutcome(
            student_id=student.id,
            status=OutcomeStatus.ALLOCATED,
            room_id=student.current_room_id,
            reason_codes=["RETAINED_CONFIRMED"],
            explanation=f"You kept room {student.current_room_id}. You confirmed retention on {_dt(student.retention_confirmed_at)} (receipt {student.retention_receipt_id}).",
        )
        allocated_order.append(student.id)

    eligible_freshers = sorted(
        [s for s in students if s.category == StudentCategory.FRESHER and (s.has_offer_letter or not rules.fresher_requires_offer_letter)],
        key=lambda s: (s.applied_at, s.id),
    )
    for student in [s for s in students if s.category == StudentCategory.FRESHER and rules.fresher_requires_offer_letter and not s.has_offer_letter]:
        outcomes[student.id] = StudentOutcome(
            student_id=student.id,
            status=OutcomeStatus.REJECTED,
            reason_codes=["NO_OFFER_LETTER"],
            explanation="Reserved seats require a valid Offer of Provisional Admission letter, and none is on record.",
        )

    reserved_winners = eligible_freshers[:reserved]
    for student in reserved_winners:
        outcomes[student.id] = StudentOutcome(
            student_id=student.id,
            status=OutcomeStatus.ALLOCATED,
            reason_codes=["FRESHER_RESERVED_SEAT"],
            explanation=f"You received one of {reserved} seats reserved for new students ({rules.fresher_reservation_pct}% of {base} {base_label}).",
        )
        allocated_order.append(student.id)

    general_slots = available - len(reserved_winners) if rules.unused_reservation_released else available - reserved
    general_slots = max(0, general_slots)
    general_candidates = [
        s for s in students
        if s.id not in outcomes
        and (s.category in {StudentCategory.RETURNING, StudentCategory.TRANSFER} or (s.category == StudentCategory.FRESHER and rules.freshers_may_compete_for_general_pool))
    ]
    general_candidates.sort(key=lambda s: (s.applied_at, s.id))
    for student in general_candidates[:general_slots]:
        outcomes[student.id] = StudentOutcome(
            student_id=student.id,
            status=OutcomeStatus.ALLOCATED,
            reason_codes=["GENERAL_POOL_ALLOCATED"],
            explanation=f"You were allocated from the {general_slots} general beds, in application order (applied {_dt(student.applied_at)}).",
        )
        allocated_order.append(student.id)

    waitlisted_students = sorted([s for s in students if s.id not in outcomes], key=lambda s: (s.applied_at, s.id))
    for pos, student in enumerate(waitlisted_students, start=1):
        if student.category == StudentCategory.FRESHER:
            code = "FRESHER_RESERVATION_FULL"
            explanation = f"All {reserved} seats reserved for new students were filled. You are #{pos} on the waitlist."
        elif student.category == StudentCategory.RETURNING and student.retention_confirmed and rules.retention_deadline and student.retention_confirmed_at and student.retention_confirmed_at > rules.retention_deadline:
            code = "RETENTION_AFTER_DEADLINE"
            explanation = f"Your confirmation on {_dt(student.retention_confirmed_at)} came after the deadline of {_dt(rules.retention_deadline)}."
        elif student.category == StudentCategory.RETURNING and not student.retention_confirmed and rules.retention_requires_confirmation:
            code = "RETENTION_NOT_CONFIRMED"
            explanation = "Your room was released because no retention confirmation was recorded."
        else:
            code = "GENERAL_POOL_FULL"
            explanation = f"All {general_slots} general beds were filled before your application ({_dt(student.applied_at)}). You are #{pos} on the waitlist."
        outcomes[student.id] = StudentOutcome(student_id=student.id, status=OutcomeStatus.WAITLISTED, waitlist_position=pos, reason_codes=[code], explanation=explanation)

    _assign_rooms(hostel, students, outcomes, allocated_order)
    ordered = [outcomes[s.id] for s in students]
    summary = AllocationSummary(
        total_beds=total_beds,
        retained=len(retained_students),
        available_beds=available,
        reserved_for_freshers=reserved,
        freshers_allocated=sum(1 for o in ordered if "FRESHER_RESERVED_SEAT" in o.reason_codes),
        general_allocated=sum(1 for o in ordered if "GENERAL_POOL_ALLOCATED" in o.reason_codes),
        waitlisted=sum(1 for o in ordered if o.status == OutcomeStatus.WAITLISTED),
        rejected=sum(1 for o in ordered if o.status == OutcomeStatus.REJECTED),
    )
    return AllocationResult(hostel_id=hostel.id, rules=_copy_model(rules), outcomes=ordered, summary=summary, run_at=now)


def _assign_rooms(hostel: Hostel, students: list[Student], outcomes: dict[str, StudentOutcome], allocated_order: list[str]) -> None:
    by_id = {s.id: s for s in students}
    occupancy = {room.id: 0 for room in hostel.rooms}
    room_by_id = {room.id: room for room in hostel.rooms}
    for outcome in outcomes.values():
        if outcome.status == OutcomeStatus.ALLOCATED and outcome.room_id in occupancy:
            occupancy[outcome.room_id] += 1
    for student_id in allocated_order:
        outcome = outcomes[student_id]
        if outcome.room_id:
            continue
        student = by_id[student_id]
        chosen = next((r for r in hostel.rooms if r.type == student.preferred_room_type and occupancy[r.id] < r.capacity), None)
        if chosen is None:
            chosen = next(r for r in hostel.rooms if occupancy[r.id] < r.capacity)
            if student.preferred_room_type:
                outcome.reason_codes.append("PREFERENCE_UNAVAILABLE")
                outcome.explanation += f" Your preferred room type was full, so you were placed in a {chosen.type} room."
        outcome.room_id = chosen.id
        occupancy[chosen.id] += 1


def confirm_retention(student: Student, now: datetime) -> Student:
    if student.category != StudentCategory.RETURNING:
        raise ValueError("Only returning students can confirm room retention.")
    digest = sha256(student.id.encode("utf-8")).hexdigest()[:6]
    return student.model_copy(update={"retention_confirmed": True, "retention_confirmed_at": now, "retention_receipt_id": f"RET-PALM-{digest}"}, deep=True)


def compile_policy(text: str) -> CompileResult:
    if text is None or not str(text).strip():
        return CompileResult(rules=load_default_rules(), used_fallback=True, error="Policy text is empty.")
    raw = str(text)
    match = re.search(r"(\d{1,3})\s*%", raw)
    pct = max(0, min(100, int(match.group(1)))) if match else RULES.fresher_reservation_pct
    rules = RULES.model_copy(update={"fresher_reservation_pct": pct, "source_text": raw}, deep=True)
    return CompileResult(rules=rules, ambiguities=[AMBIGUITY], unmapped_clauses=[UNMAPPED])


def load_students() -> list[Student]:
    return deepcopy(STUDENTS)


def load_hostel() -> Hostel:
    return HOSTEL.model_copy(deep=True)


def load_default_rules() -> Rules:
    return RULES.model_copy(deep=True)


COMPILE_RESULT = CompileResult(rules=RULES, ambiguities=[AMBIGUITY], unmapped_clauses=[UNMAPPED])
ALLOCATION_RESULT = allocate(HOSTEL, STUDENTS, RULES, FIXED_NOW)

from __future__ import annotations

from math import floor

from shared.models import AllocationResult, OutcomeStatus, Student, StudentCategory


def check_retention_honoured(result: AllocationResult, run_students: list[Student]) -> tuple[bool, str]:
    outcomes = {outcome.student_id: outcome for outcome in result.outcomes}
    required = []
    failed = []
    for student in run_students:
        if student.category != StudentCategory.RETURNING or not student.current_room_id:
            continue
        confirmed = student.retention_confirmed or not result.rules.retention_requires_confirmation
        on_time = not result.rules.retention_deadline or (
            student.retention_confirmed_at is not None and student.retention_confirmed_at <= result.rules.retention_deadline
        )
        if confirmed and on_time:
            required.append(student.id)
            outcome = outcomes.get(student.id)
            if (
                outcome is None
                or outcome.status != OutcomeStatus.ALLOCATED
                or outcome.room_id != student.current_room_id
                or "RETAINED_CONFIRMED" not in outcome.reason_codes
            ):
                failed.append(student.id)
    if failed:
        return False, f"Failed retention ids: {', '.join(failed)}"
    return True, f"{len(required)} of {len(required)} honoured"


def check_reserved_within_limit(result: AllocationResult) -> tuple[bool, str]:
    base = result.summary.available_beds if result.rules.reservation_base == "vacated_beds" else result.summary.total_beds
    limit = min(floor(result.rules.fresher_reservation_pct / 100 * base), result.summary.available_beds)
    used = sum(1 for outcome in result.outcomes if "FRESHER_RESERVED_SEAT" in outcome.reason_codes)
    passed = used <= limit and result.summary.reserved_for_freshers == limit
    return passed, f"{used} seats used, limit {limit}"

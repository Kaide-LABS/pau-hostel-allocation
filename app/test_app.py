from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from app import audit, mock, view
from shared.models import AllocationResult, CompileResult, Hostel, OutcomeStatus, Rules, Student, StudentCategory, StudentOutcome


EXPECTED_CODES = {
    "RETAINED_CONFIRMED",
    "RETENTION_NOT_CONFIRMED",
    "RETENTION_AFTER_DEADLINE",
    "FRESHER_RESERVED_SEAT",
    "FRESHER_RESERVATION_FULL",
    "NO_OFFER_LETTER",
    "GENERAL_POOL_ALLOCATED",
    "GENERAL_POOL_FULL",
    "PREFERENCE_UNAVAILABLE",
}


def test_mock_models_round_trip_and_reason_coverage() -> None:
    Hostel.model_validate(mock.HOSTEL.model_dump())
    Rules.model_validate(mock.RULES.model_dump())
    CompileResult.model_validate(mock.COMPILE_RESULT.model_dump())
    AllocationResult.model_validate(mock.ALLOCATION_RESULT.model_dump())
    for student in mock.STUDENTS:
        Student.model_validate(student.model_dump())
    codes = {code for outcome in mock.ALLOCATION_RESULT.outcomes for code in outcome.reason_codes}
    assert codes == EXPECTED_CODES
    assert {outcome.status for outcome in mock.ALLOCATION_RESULT.outcomes} == {
        OutcomeStatus.ALLOCATED,
        OutcomeStatus.WAITLISTED,
        OutcomeStatus.REJECTED,
    }
    assert all("{" not in outcome.explanation and "}" not in outcome.explanation for outcome in mock.ALLOCATION_RESULT.outcomes)


def test_audit_pass_and_failures() -> None:
    assert audit.check_retention_honoured(mock.ALLOCATION_RESULT, mock.STUDENTS)[0]
    assert audit.check_reserved_within_limit(mock.ALLOCATION_RESULT)[0]
    tampered = mock.ALLOCATION_RESULT.model_copy(deep=True)
    retained = next(outcome for outcome in tampered.outcomes if "RETAINED_CONFIRMED" in outcome.reason_codes)
    retained.status = OutcomeStatus.WAITLISTED
    retained.room_id = None
    assert not audit.check_retention_honoured(tampered, mock.STUDENTS)[0]
    over = mock.ALLOCATION_RESULT.model_copy(deep=True)
    over.outcomes.append(
        StudentOutcome(student_id="extra", status=OutcomeStatus.ALLOCATED, reason_codes=["FRESHER_RESERVED_SEAT"], explanation="x")
    )
    assert not audit.check_reserved_within_limit(over)[0]


def test_view_helpers() -> None:
    assert view.STATUS_STYLE["allocated"]["color"] == "#1a7f37"
    assert view.status_label(OutcomeStatus.WAITLISTED) == "Waitlisted"
    rows = dict(view.rules_rows(mock.RULES))
    assert rows["Reservation base"] == "vacated beds"
    assert rows["Offer letter required for reserved seats"] == "Yes"
    df = view.outcomes_dataframe(mock.ALLOCATION_RESULT, mock.STUDENTS)
    filtered = view.filter_outcomes(df, ["Waitlisted"])
    assert set(filtered["Status"]) == {"Waitlisted"}
    assert view.filter_outcomes(df, []).empty
    assert "40% of" in view.reserved_sentence(mock.ALLOCATION_RESULT.summary, mock.RULES)


def test_pct_change_to_30_lowers_reserved_and_audit_passes() -> None:
    rules_30 = mock.RULES.model_copy(update={"fresher_reservation_pct": 30}, deep=True)
    result_30 = mock.allocate(mock.HOSTEL, mock.STUDENTS, rules_30, mock.FIXED_NOW)
    assert result_30.summary.reserved_for_freshers < mock.ALLOCATION_RESULT.summary.reserved_for_freshers
    assert result_30.outcomes != mock.ALLOCATION_RESULT.outcomes
    assert audit.check_retention_honoured(result_30, mock.STUDENTS)[0]
    assert audit.check_reserved_within_limit(result_30)[0]


def test_contract_invariants_and_determinism() -> None:
    result = mock.ALLOCATION_RESULT
    capacities = {room.id: room.capacity for room in mock.HOSTEL.rooms}
    for room_id, capacity in capacities.items():
        assert sum(1 for outcome in result.outcomes if outcome.room_id == room_id) <= capacity
    assert sum(1 for outcome in result.outcomes if outcome.status == OutcomeStatus.ALLOCATED) <= result.summary.total_beds
    assert sorted(outcome.student_id for outcome in result.outcomes) == sorted(student.id for student in mock.STUDENTS)
    assert len({outcome.student_id for outcome in result.outcomes}) == len(mock.STUDENTS)
    assert all(outcome.reason_codes for outcome in result.outcomes)
    again = mock.allocate(mock.HOSTEL, mock.STUDENTS, mock.RULES, mock.FIXED_NOW)
    assert again == result


def test_empty_students_and_rule_edges() -> None:
    empty = mock.allocate(mock.HOSTEL, [], mock.RULES, mock.FIXED_NOW)
    assert empty.summary.total_beds == 9
    assert empty.summary.retained == 0
    assert empty.summary.available_beds == 9
    assert empty.summary.freshers_allocated == 0
    assert empty.summary.general_allocated == 0
    assert empty.summary.waitlisted == 0
    assert empty.summary.rejected == 0
    for pct in (0, 100):
        rules = mock.RULES.model_copy(update={"fresher_reservation_pct": pct}, deep=True)
        result = mock.allocate(mock.HOSTEL, mock.STUDENTS, rules, mock.FIXED_NOW)
        assert audit.check_reserved_within_limit(result)[0]
    total_base = mock.RULES.model_copy(update={"reservation_base": "total_beds"}, deep=True)
    assert mock.allocate(mock.HOSTEL, mock.STUDENTS, total_base, mock.FIXED_NOW).summary.reserved_for_freshers == 3
    no_confirm = mock.RULES.model_copy(update={"retention_requires_confirmation": False}, deep=True)
    assert audit.check_retention_honoured(mock.allocate(mock.HOSTEL, mock.STUDENTS, no_confirm, mock.FIXED_NOW), mock.STUDENTS)[0]
    no_release = mock.RULES.model_copy(update={"unused_reservation_released": False}, deep=True)
    assert mock.allocate(mock.HOSTEL, mock.STUDENTS, no_release, mock.FIXED_NOW).summary.general_allocated >= 0
    fresher_general = mock.RULES.model_copy(update={"freshers_may_compete_for_general_pool": True}, deep=True)
    assert mock.allocate(mock.HOSTEL, mock.STUDENTS, fresher_general, mock.FIXED_NOW).summary.general_allocated >= 0


def test_missing_current_room_confirmed_returning_does_not_crash() -> None:
    student = Student(
        id="ret-missing-room",
        name="Student Missing Room",
        category=StudentCategory.RETURNING,
        retention_confirmed=True,
        retention_confirmed_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        applied_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    result = mock.allocate(mock.HOSTEL, [student], mock.RULES, mock.FIXED_NOW)
    assert result.outcomes[0].status == OutcomeStatus.ALLOCATED


def test_confirm_retention_edges() -> None:
    confirmed = mock.confirm_retention(mock.STUDENTS[0], mock.FIXED_NOW)
    confirmed_again = mock.confirm_retention(confirmed, mock.FIXED_NOW)
    assert confirmed_again.retention_receipt_id == confirmed.retention_receipt_id
    for student in [s for s in mock.STUDENTS if s.category in {StudentCategory.TRANSFER, StudentCategory.FRESHER}][:2]:
        with pytest.raises(ValueError):
            mock.confirm_retention(student, mock.FIXED_NOW)


def test_compile_policy_odd_inputs() -> None:
    assert mock.compile_policy("   ").used_fallback
    assert mock.compile_policy("%").rules.fresher_reservation_pct == 40
    assert mock.compile_policy("150%").rules.fresher_reservation_pct == 100
    assert mock.compile_policy("40 % and 30 %").rules.fresher_reservation_pct == 40
    long = "policy " * 2000 + "30%"
    assert mock.compile_policy(long).rules.fresher_reservation_pct == 30


def test_audit_missing_retained_outcome_fails_with_id() -> None:
    result = mock.ALLOCATION_RESULT.model_copy(deep=True)
    result.outcomes = [outcome for outcome in result.outcomes if outcome.student_id != "ret-on-time"]
    passed, evidence = audit.check_retention_honoured(result, mock.STUDENTS)
    assert not passed
    assert "ret-on-time" in evidence


def test_html_escape_and_placeholders() -> None:
    assert "<script>" not in view.tag_html('<script>"x"</script>')
    assert "&quot;" in view.tag_html('"quoted"')
    assert view.find_placeholders("hello {x} and {y}") == ["{x}", "{y}"]
    assert view.find_placeholders("plain text") == []
    assert "<" not in view.status_pill_html("allocated").split(">")[1].split("<")[0]


def test_explanation_template_spot_checks() -> None:
    explanations = " ".join(outcome.explanation for outcome in mock.ALLOCATION_RESULT.outcomes)
    assert "You kept room P101. You confirmed retention on" in explanations
    assert "Your room was released because no retention confirmation was recorded." in explanations
    assert "came after the deadline of" in explanations
    assert "You received one of 3 seats reserved for new students (40% of 8 available beds)." in explanations
    assert "All 3 seats reserved for new students were filled." in explanations
    assert "Reserved seats require a valid Offer of Provisional Admission letter, and none is on record." in explanations
    assert "You were allocated from the 5 general beds, in application order" in explanations
    assert "All 5 general beds were filled before your application" in explanations
    assert "Your preferred room type was full, so you were placed in a" in explanations

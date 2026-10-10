from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

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
        assert result.summary.reserved_for_freshers == (0 if pct == 0 else result.summary.available_beds)
    total_base = mock.RULES.model_copy(update={"reservation_base": "total_beds"}, deep=True)
    assert mock.allocate(mock.HOSTEL, mock.STUDENTS, total_base, mock.FIXED_NOW).summary.reserved_for_freshers == 3
    no_confirm = mock.RULES.model_copy(update={"retention_requires_confirmation": False}, deep=True)
    no_confirm_result = mock.allocate(mock.HOSTEL, mock.STUDENTS, no_confirm, mock.FIXED_NOW)
    assert audit.check_retention_honoured(no_confirm_result, mock.STUDENTS)[0]
    assert no_confirm_result.summary.retained == 3
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


def test_returning_room_not_in_hostel_does_not_crash() -> None:
    student = Student(
        id="ret-phantom-room",
        name="Student Phantom Room",
        category=StudentCategory.RETURNING,
        current_room_id="ZZZ",
        retention_confirmed=True,
        retention_confirmed_at=datetime(2026, 10, 8, tzinfo=timezone.utc),
        applied_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    result = mock.allocate(mock.HOSTEL, [student, *mock.STUDENTS], mock.RULES, mock.FIXED_NOW)
    outcome = next(o for o in result.outcomes if o.student_id == "ret-phantom-room")
    assert outcome.status == OutcomeStatus.ALLOCATED
    assert outcome.room_id == "ZZZ"
    assert "RETAINED_CONFIRMED" in outcome.reason_codes
    capacities = {room.id: room.capacity for room in mock.HOSTEL.rooms}
    for room_id, capacity in capacities.items():
        assert sum(1 for o in result.outcomes if o.room_id == room_id) <= capacity
    assert audit.check_retention_honoured(result, [student, *mock.STUDENTS])[0]


def test_confirm_retention_edges() -> None:
    confirmed = mock.confirm_retention(mock.STUDENTS[0], mock.FIXED_NOW)
    confirmed_again = mock.confirm_retention(confirmed, mock.FIXED_NOW)
    assert confirmed_again.retention_receipt_id == confirmed.retention_receipt_id
    transfer = next(s for s in mock.STUDENTS if s.category == StudentCategory.TRANSFER)
    fresher = next(s for s in mock.STUDENTS if s.category == StudentCategory.FRESHER)
    for student in (transfer, fresher):
        with pytest.raises(ValueError):
            mock.confirm_retention(student, mock.FIXED_NOW)


def test_compile_policy_odd_inputs() -> None:
    assert mock.compile_policy(None).used_fallback
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
    assert "&quot;" in view.tag_html('reason "quoted"')
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


def _app(monkeypatch: pytest.MonkeyPatch, use_mock: str = "1") -> AppTest:
    monkeypatch.setenv("USE_MOCK", use_mock)
    at = AppTest.from_file(Path(__file__).with_name("main.py"))
    at.default_timeout = 5
    return at


def _label(student_id: str) -> str:
    student = next(student for student in mock.STUDENTS if student.id == student_id)
    return f"{student.name} ({student.category.value})"


def test_streamlit_demo_path_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    at = _app(monkeypatch)
    at.run()
    assert not at.exception

    at.selectbox(key="selected_student_label").set_value(_label("ret-unconfirmed")).run()
    assert not at.exception
    assert at.session_state.selected_student_id == "ret-unconfirmed"
    at.button(key="confirm_retention").click().run()
    assert not at.exception
    assert at.session_state.last_receipt["ret-unconfirmed"].startswith("RET-PALM-")

    at.button(key="compile_policy").click().run()
    assert not at.exception
    at.button(key="run_allocation").click().run()
    assert not at.exception
    reserved_40 = at.session_state.result.summary.reserved_for_freshers
    assert at.metric

    at.text_area(key="policy_text").set_value(mock.SAMPLE_POLICY.replace("40%", "30%")).run()
    at.button(key="compile_policy").click().run()
    at.button(key="run_allocation").click().run()
    assert not at.exception
    assert at.session_state.result.summary.reserved_for_freshers < reserved_40

    at.text_area(key="policy_text").set_value("   ").run()
    at.button(key="compile_policy").click().run()
    assert not at.exception
    assert any("Paste the policy text first." in item.value for item in at.warning)
    assert any("PASS" in item.value for item in at.markdown)


def test_no_stack_or_llm_imports_in_app() -> None:
    forbidden = (
        "st." + "exception",
        "trace" + "back",
        "import " + "anthropic",
        "from " + "anthropic",
        "import " + "openai",
        "from " + "openai",
    )
    for path in Path("app").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(item in text for item in forbidden), path


def test_real_mode_missing_engine_shows_one_error_without_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("streamlit")
    if Path("engine/allocate.py").exists() and Path("policy/compile.py").exists():
        pytest.skip("real packages are present in this worktree")
    at = _app(monkeypatch, "0")
    at.run()
    assert not at.exception
    errors = [item.value for item in at.error]
    assert len(errors) == 1
    assert "Real engine or compiler not available yet:" in errors[0]


def test_non_returning_confirm_button_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    at = _app(monkeypatch)
    at.run()
    at.selectbox(key="selected_student_label").set_value(_label("tr-1")).run()
    assert at.button(key="confirm_retention").disabled
    at.selectbox(key="selected_student_label").set_value(_label("fr-1")).run()
    assert at.button(key="confirm_retention").disabled


def test_run_before_compile_and_tab_state_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    at = _app(monkeypatch)
    at.run()
    at.selectbox(key="selected_student_label").set_value(_label("ret-unconfirmed")).run()
    at.button(key="run_allocation").click().run()
    assert not at.exception
    assert at.session_state.result is not None
    assert any("Running with the default rules. Compile a policy to use your own." in item.value for item in at.info)
    at.run()
    assert at.session_state.selected_student_id == "ret-unconfirmed"
    assert at.session_state.selected_student_label == _label("ret-unconfirmed")


def test_waitlisted_explanations_have_digits_and_no_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    at = _app(monkeypatch)
    at.run()
    at.button(key="run_allocation").click().run()
    waitlisted = next(
        outcome
        for outcome in at.session_state.result.outcomes
        if outcome.status == OutcomeStatus.WAITLISTED and any(char.isdigit() for char in outcome.explanation)
    )
    at.selectbox(key="selected_student_label").set_value(_label(waitlisted.student_id)).run()
    student_text = " ".join(item.value for item in at.markdown)
    assert any(char.isdigit() for char in waitlisted.explanation)
    assert not view.find_placeholders(waitlisted.explanation)
    assert waitlisted.explanation in student_text
    at.selectbox(key="manager_explain_student_id").set_value(waitlisted.student_id).run()
    manager_text = " ".join(item.value for item in at.markdown)
    assert waitlisted.explanation in manager_text


def test_reserved_sentence_updates_after_policy_change(monkeypatch: pytest.MonkeyPatch) -> None:
    at = _app(monkeypatch)
    at.run()
    at.button(key="compile_policy").click().run()
    at.button(key="run_allocation").click().run()
    text_40 = " ".join(item.value for item in at.markdown)
    assert "40% of" in text_40
    at.text_area(key="policy_text").set_value(mock.SAMPLE_POLICY.replace("40%", "30%")).run()
    at.button(key="compile_policy").click().run()
    at.button(key="run_allocation").click().run()
    text_30 = " ".join(item.value for item in at.markdown)
    assert "30% of" in text_30
    assert "40% of" not in text_30


def test_safe_call_message_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MOCK", "1")
    import app.main as main

    def raises_value_error() -> None:
        raise ValueError("specific value problem")

    def raises_runtime_error() -> None:
        raise RuntimeError("secret runtime detail")

    assert main.safe_call("generic", raises_value_error) == (None, "specific value problem")
    assert main.safe_call("generic", raises_runtime_error) == (None, "generic")

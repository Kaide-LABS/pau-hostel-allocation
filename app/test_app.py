from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

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
    assert rows["Reservation base"] == "available beds"
    assert rows["Share of available beds reserved for new students"] == "40%"
    total_rows = dict(view.rules_rows(mock.RULES.model_copy(update={"reservation_base": "total_beds"}, deep=True)))
    assert total_rows["Reservation base"] == "total beds"
    assert not any("vacated" in key or "vacated" in value for key, value in rows.items())
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


# ---------------------------------------------------------------------------
# Phase 3a: timezone-safe helpers (D1) and the base-label wording fix
# ---------------------------------------------------------------------------

NAIVE = datetime(2026, 7, 15, 23, 59, 0)
AWARE = datetime(2026, 7, 15, 23, 59, 0, tzinfo=timezone.utc)


def test_now_like_follows_reference_flavour() -> None:
    assert view.now_like(AWARE).tzinfo is not None
    assert view.now_like(AWARE).utcoffset() == timedelta(0)
    assert view.now_like(NAIVE).tzinfo is None
    assert view.now_like(None).tzinfo is None
    plus_one = AWARE.astimezone(timezone(timedelta(hours=1)))
    assert view.now_like(plus_one).utcoffset() == timedelta(0)


def test_is_after_all_aware_naive_combinations() -> None:
    assert view.is_after(AWARE + timedelta(hours=2), AWARE)
    assert not view.is_after(AWARE, AWARE + timedelta(hours=2))
    assert view.is_after(NAIVE + timedelta(hours=2), NAIVE)
    assert not view.is_after(NAIVE, NAIVE + timedelta(hours=2))
    # Exactly one side naive: must not raise; the naive side is treated as local time.
    assert view.is_after(datetime.now(timezone.utc) + timedelta(days=1), datetime.now())
    assert not view.is_after(datetime.now(timezone.utc) - timedelta(days=1), datetime.now())
    assert view.is_after(datetime.now() + timedelta(days=1), datetime.now(timezone.utc))
    assert not view.is_after(datetime.now() - timedelta(days=1), datetime.now(timezone.utc))
    local_aware = datetime.now().astimezone()
    local_naive = local_aware.replace(tzinfo=None)
    assert not view.is_after(local_aware, local_naive)
    assert not view.is_after(local_naive, local_aware)


def test_is_after_none_and_equal() -> None:
    assert not view.is_after(AWARE, None)
    assert not view.is_after(NAIVE, None)
    assert not view.is_after(None, NAIVE)  # type: ignore[arg-type]
    assert not view.is_after(AWARE, AWARE)
    assert not view.is_after(NAIVE, NAIVE)


def test_late_warning_text_handles_naive_deadline_without_raising() -> None:
    def fmt(value: datetime | None) -> str:
        return "Not recorded" if value is None else value.strftime("%d %b %Y, %H:%M:%S")

    past_naive = datetime(2026, 7, 15, 23, 59, 0)
    expected = "The retention deadline was 15 Jul 2026, 23:59:00. A confirmation now will be recorded as late."
    assert view.late_warning_text(datetime.now(timezone.utc), past_naive, fmt) == expected
    assert view.late_warning_text(view.now_like(past_naive), past_naive, fmt) == expected
    assert view.late_warning_text(datetime.now(), None, fmt) is None
    future_naive = datetime.now() + timedelta(days=30)
    assert view.late_warning_text(datetime.now(timezone.utc), future_naive, fmt) is None
    past_aware = datetime(2026, 7, 15, 23, 59, 0, tzinfo=timezone.utc)
    assert view.late_warning_text(datetime.now(), past_aware, fmt) is not None


def test_audit_tolerates_mixed_naive_and_aware_datetimes() -> None:
    naive_rules = mock.RULES.model_copy(update={"retention_deadline": datetime(2026, 10, 9, 18, 0)}, deep=True)
    result = mock.ALLOCATION_RESULT.model_copy(update={"rules": naive_rules}, deep=True)
    # Naive deadline (local time) against aware UTC confirmations, with a margin of hours
    # either way: ret-on-time is on time, ret-late is late, so exactly one is required.
    assert audit.check_retention_honoured(result, mock.STUDENTS) == (True, "1 of 1 honoured")
    assert audit.check_reserved_within_limit(result)[0]


def test_reserved_sentence_base_label_for_both_bases() -> None:
    summary = mock.ALLOCATION_RESULT.summary
    vacated = mock.RULES.model_copy(update={"reservation_base": "vacated_beds"}, deep=True)
    total = mock.RULES.model_copy(update={"reservation_base": "total_beds"}, deep=True)
    vacated_text = view.reserved_sentence(summary, vacated)
    total_text = view.reserved_sentence(summary, total)
    assert vacated_text == (
        f"{summary.reserved_for_freshers} of {summary.available_beds} available beds reserved for new students "
        f"(40% of {summary.available_beds} available beds)."
    )
    assert total_text == (
        f"{summary.reserved_for_freshers} of {summary.available_beds} available beds reserved for new students "
        f"(40% of {summary.total_beds} total beds)."
    )
    assert "total beds" not in vacated_text
    assert total_text.endswith("total beds).")


# ---------------------------------------------------------------------------
# Phase 3a: real engine against data/ fixtures (offline, read-only)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILES = ("students.json", "hostel.json", "default_rules.json", "result.json")


def _require_real_engine() -> None:
    for relative in ("engine/allocate.py", "engine/retention.py", "data/students.json"):
        if not (REPO_ROOT / relative).exists():
            pytest.skip(f"{relative} is not present in this worktree")


def _data_snapshot() -> dict[str, bytes | None]:
    snapshot: dict[str, bytes | None] = {}
    for name in DATA_FILES:
        path = REPO_ROOT / "data" / name
        snapshot[name] = path.read_bytes() if path.exists() else None
    return snapshot


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch):
    """Real engine plus fixtures; fails the test if anything tries to write to data/."""
    _require_real_engine()
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from engine.allocate import allocate
    from engine.retention import confirm_retention
    from shared import store

    def refuse(*_args, **_kwargs):
        raise AssertionError("tests must not write to data/")

    monkeypatch.setattr(store, "save_students", refuse)
    monkeypatch.setattr(store, "save_result", refuse)
    before = _data_snapshot()
    ns = SimpleNamespace(
        allocate=allocate,
        confirm_retention=confirm_retention,
        hostel=store.load_hostel(),
        students=store.load_students(),
        rules=store.load_default_rules(),
    )
    yield ns
    assert _data_snapshot() == before


def _unconfirmed_returning_id(real) -> str:
    return next(s.id for s in real.students if s.category == StudentCategory.RETURNING and not s.retention_confirmed)


def _confirm_live(real, student_id: str, rules: Rules):
    student = next(s for s in real.students if s.id == student_id)
    assert student.category == StudentCategory.RETURNING and not student.retention_confirmed
    updated = real.confirm_retention(student, view.now_like(rules.retention_deadline))
    return updated, [updated if s.id == updated.id else s for s in real.students]


def test_real_engine_fixture_run_after_live_confirmation(real) -> None:
    updated, students = _confirm_live(real, _unconfirmed_returning_id(real), real.rules)
    assert updated.retention_confirmed and (updated.retention_receipt_id or "").startswith("RET-")
    result = real.allocate(real.hostel, students, real.rules, view.now_like(real.rules.retention_deadline))
    ids = [outcome.student_id for outcome in result.outcomes]
    assert sorted(ids) == sorted(s.id for s in students)
    assert len(set(ids)) == len(students)
    assert all(outcome.reason_codes for outcome in result.outcomes)
    assert result.summary.waitlisted > 0
    assert audit.check_retention_honoured(result, students)[0]
    assert audit.check_reserved_within_limit(result)[0]
    df = view.outcomes_dataframe(result, students)
    assert len(df) == len(students)
    assert set(df["Status"]) <= {"Allocated", "Waitlisted", "Rejected"}
    assert not view.filter_outcomes(df, ["Waitlisted"]).empty


def test_real_engine_late_live_confirmation_is_after_deadline(real) -> None:
    # Correct engine behaviour, not a failure: data/default_rules.json has a past
    # retention_deadline (2026-07-15), so a confirmation made now is late and the
    # engine records RETENTION_AFTER_DEADLINE. The UI warns before the click.
    # The deadline is set explicitly so this keeps passing if the owner moves the fixture.
    rules = real.rules.model_copy(update={"retention_deadline": datetime(2026, 7, 15, 23, 59, 0)}, deep=True)
    assert view.is_after(view.now_like(rules.retention_deadline), rules.retention_deadline)
    student_id = _unconfirmed_returning_id(real)
    _, students = _confirm_live(real, student_id, rules)
    result = real.allocate(real.hostel, students, rules, view.now_like(rules.retention_deadline))
    outcome = next(o for o in result.outcomes if o.student_id == student_id)
    assert "RETENTION_AFTER_DEADLINE" in outcome.reason_codes
    assert "RETAINED_CONFIRMED" not in outcome.reason_codes
    assert audit.check_retention_honoured(result, students)[0]

    def fmt(value: datetime | None) -> str:
        return "Not recorded" if value is None else value.strftime("%d %b %Y, %H:%M:%S")

    assert view.late_warning_text(view.now_like(rules.retention_deadline), rules.retention_deadline, fmt)


def test_real_engine_on_time_live_confirmation_is_retained(real) -> None:
    rules = real.rules.model_copy(update={"retention_deadline": datetime.now() + timedelta(days=30)}, deep=True)
    student_id = _unconfirmed_returning_id(real)
    _, students = _confirm_live(real, student_id, rules)
    result = real.allocate(real.hostel, students, rules, view.now_like(rules.retention_deadline))
    outcome = next(o for o in result.outcomes if o.student_id == student_id)
    assert outcome.status == OutcomeStatus.ALLOCATED
    assert "RETAINED_CONFIRMED" in outcome.reason_codes
    assert audit.check_retention_honoured(result, students)[0]


def test_real_engine_aware_confirmation_with_naive_deadline_is_a_value_error(real) -> None:
    # Documents why D1 matters: an aware timestamp against the naive fixture deadline is
    # rejected by the engine with ValueError (which safe_call turns into a message), so the
    # UI must build timestamps with view.now_like(rules.retention_deadline).
    student = next(s for s in real.students if s.id == _unconfirmed_returning_id(real))
    aware = real.confirm_retention(student, datetime.now(timezone.utc))
    students = [aware if s.id == aware.id else s for s in real.students]
    with pytest.raises(ValueError):
        real.allocate(real.hostel, students, real.rules, datetime.now())
    _, ok_students = _confirm_live(real, student.id, real.rules)
    real.allocate(real.hostel, ok_students, real.rules, view.now_like(real.rules.retention_deadline))


def test_real_engine_pct_40_to_30_lowers_reserved(real) -> None:
    rules_30 = real.rules.model_copy(update={"fresher_reservation_pct": 30}, deep=True)
    now = view.now_like(real.rules.retention_deadline)
    result_40 = real.allocate(real.hostel, real.students, real.rules, now)
    result_30 = real.allocate(real.hostel, real.students, rules_30, now)
    assert real.rules.fresher_reservation_pct == 40
    assert result_30.summary.reserved_for_freshers < result_40.summary.reserved_for_freshers
    assert result_30.outcomes != result_40.outcomes
    assert audit.check_reserved_within_limit(result_30)[0]
    assert audit.check_retention_honoured(result_30, real.students)[0]
    assert view.reserved_sentence(result_30.summary, result_30.rules).startswith(f"{result_30.summary.reserved_for_freshers} of")


def test_real_engine_total_beds_base_sentence(real) -> None:
    rules = real.rules.model_copy(update={"reservation_base": "total_beds"}, deep=True)
    result = real.allocate(real.hostel, real.students, rules, view.now_like(rules.retention_deadline))
    sentence = view.reserved_sentence(result.summary, result.rules)
    assert f"% of {result.summary.total_beds} total beds)" in sentence
    assert audit.check_reserved_within_limit(result)[0]


def test_real_engine_explanations_have_no_placeholders_and_are_deterministic(real) -> None:
    now = view.now_like(real.rules.retention_deadline)
    result = real.allocate(real.hostel, real.students, real.rules, now)
    for outcome in result.outcomes:
        assert not view.find_placeholders(outcome.explanation), outcome.student_id
        assert outcome.explanation.strip()
    waitlisted = [o for o in result.outcomes if o.status == OutcomeStatus.WAITLISTED]
    assert waitlisted and all(any(char.isdigit() for char in o.explanation) for o in waitlisted)
    assert real.allocate(real.hostel, real.students, real.rules, now).outcomes == result.outcomes


def test_real_engine_confirm_retention_rejects_non_returning(real) -> None:
    fresher = next(s for s in real.students if s.category == StudentCategory.FRESHER)
    with pytest.raises(ValueError):
        real.confirm_retention(fresher, view.now_like(real.rules.retention_deadline))


# ---------------------------------------------------------------------------
# Phase 3a follow-up: main.py wiring of D1 (real engine behind the mock switch) and HTML escaping
# ---------------------------------------------------------------------------


def _wire_real_engine(monkeypatch: pytest.MonkeyPatch, real) -> None:
    """Point the mock module's seams at the real engine and the naive-datetime fixtures."""
    from copy import deepcopy

    monkeypatch.setattr(mock, "allocate", real.allocate)
    monkeypatch.setattr(mock, "confirm_retention", real.confirm_retention)
    monkeypatch.setattr(mock, "load_hostel", lambda: deepcopy(real.hostel))
    monkeypatch.setattr(mock, "load_students", lambda: deepcopy(real.students))
    monkeypatch.setattr(mock, "load_default_rules", lambda: deepcopy(real.rules))


def test_streamlit_wiring_with_real_engine_and_naive_fixtures(monkeypatch: pytest.MonkeyPatch, real) -> None:
    # Would fail if main.py built an aware datetime.now(timezone.utc) or compared with a raw `>`:
    # the pre-click late warning would raise TypeError (naive fixture deadline), and the confirm
    # timestamp would make the real allocate raise ValueError ("Allocation failed").
    # Explicit naive past deadline (the fixture's shape), so the late warning is always expected.
    real.rules = real.rules.model_copy(update={"retention_deadline": datetime(2026, 7, 15, 23, 59, 0)}, deep=True)
    _wire_real_engine(monkeypatch, real)
    student = next(s for s in real.students if s.id == _unconfirmed_returning_id(real))
    label = f"{student.name} ({student.category.value})"

    at = _app(monkeypatch)
    at.run()
    assert not at.exception
    assert not at.error

    at.selectbox(key="selected_student_label").set_value(label).run()
    assert not at.exception
    assert not at.error
    assert any("A confirmation now will be recorded as late." in item.value for item in at.warning)

    at.button(key="confirm_retention").click().run()
    assert not at.exception
    assert not at.error
    assert at.session_state.last_receipt[student.id].startswith("RET-")
    assert any("Receipt RET-" in item.value for item in at.success)
    confirmed = next(s for s in at.session_state.students if s.id == student.id)
    assert confirmed.retention_confirmed_at is not None and confirmed.retention_confirmed_at.tzinfo is None

    at.button(key="run_allocation").click().run()
    assert not at.exception
    assert not at.error
    assert not any("Allocation failed" in item.value for item in at.error)
    assert len(at.metric) == 8
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Total beds"] == "24"
    assert metrics["Retained"] == "10"
    assert metrics["Rejected"] == "2"
    assert at.session_state.result.summary.total_beds == 24
    assert at.session_state.result.summary.retained == 10
    audit_boxes = [item.value for item in at.markdown if 'class="audit-' in item.value]
    assert len(audit_boxes) == 2
    assert all("audit-pass" in box and "PASS" in box for box in audit_boxes)


def test_html_snippets_escape_dynamic_strings() -> None:
    attack = "<script>alert(1)</script>"
    student = mock.STUDENTS[0].model_copy(update={"name": attack, "current_room_id": attack}, deep=True)
    for html_text in (
        view.explanation_box_html(attack),
        view.student_card_html(student, attack),
        view.audit_box_html(attack, True, attack),
        view.tag_html(attack),
        view.status_pill_html("allocated"),
    ):
        assert "<script>" not in html_text
    assert "&lt;script&gt;" in view.explanation_box_html(attack)
    # Normal text stays verbatim, including quotes and apostrophes.
    plain = "You kept room P101. You confirmed retention on 2026-07-02 (receipt RET-PALM-3f9a1c). It's \"fine\"."
    assert view.explanation_box_html(plain) == f'<div class="explanation-box">{plain}</div>'
    assert plain in view.explanation_box_html(plain)


def test_streamlit_renders_script_in_name_and_explanation_escaped(monkeypatch: pytest.MonkeyPatch) -> None:
    attack = "<script>alert(1)</script>"
    students = [s.model_copy(deep=True) for s in mock.STUDENTS]
    target = next(s for s in students if s.id == "tr-1")
    target.name = f"Student {attack}"
    real_allocate = mock.allocate

    def hostile_allocate(hostel, student_list, rules, now):
        result = real_allocate(hostel, student_list, rules, now)
        for outcome in result.outcomes:
            if outcome.student_id == "tr-1":
                outcome.explanation = f"Hostile {attack} text"
        return result

    monkeypatch.setattr(mock, "load_students", lambda: [s.model_copy(deep=True) for s in students])
    monkeypatch.setattr(mock, "allocate", hostile_allocate)
    at = _app(monkeypatch)
    at.run()
    at.button(key="run_allocation").click().run()
    at.selectbox(key="selected_student_label").set_value(f"{target.name} (transfer)").run()
    assert not at.exception
    rendered = [item.value for item in at.markdown]
    assert not any("<script>" in value for value in rendered)
    assert any("&lt;script&gt;alert(1)&lt;/script&gt;" in value and "student-card" in value for value in rendered)
    assert any("Hostile &lt;script&gt;alert(1)&lt;/script&gt; text" in value for value in rendered)
    at.selectbox(key="manager_explain_student_id").set_value("tr-1").run()
    assert not any("<script>" in item.value for item in at.markdown)


def _install_recorders(monkeypatch: pytest.MonkeyPatch, allocate_fn, confirm_fn) -> dict[str, list]:
    """Wrap allocate, confirm_retention and view.late_warning_text; record the `now` each receives."""
    calls: dict[str, list] = {"allocate": [], "confirm": [], "late": []}
    late_fn = view.late_warning_text

    def rec_allocate(hostel, students, rules, now):
        calls["allocate"].append(now)
        return allocate_fn(hostel, students, rules, now)

    def rec_confirm(student, now):
        calls["confirm"].append(now)
        return confirm_fn(student, now)

    def rec_late(now, deadline, formatter):
        calls["late"].append(now)
        return late_fn(now, deadline, formatter)

    monkeypatch.setattr(mock, "allocate", rec_allocate)
    monkeypatch.setattr(mock, "confirm_retention", rec_confirm)
    monkeypatch.setattr(view, "late_warning_text", rec_late)
    return calls


def _drive_confirm_and_run(at: AppTest, label: str) -> None:
    at.run()
    at.selectbox(key="selected_student_label").set_value(label).run()
    at.button(key="confirm_retention").click().run()
    at.button(key="run_allocation").click().run()
    assert not at.exception
    assert not at.error


def test_streamlit_passes_naive_now_when_rules_deadline_is_naive(monkeypatch: pytest.MonkeyPatch, real) -> None:
    # Each of the three call sites in main.py (late warning, confirm click, run allocation) must
    # build `now` with view.now_like(rules.retention_deadline). Reverting any one to an aware
    # datetime.now(timezone.utc) makes the recorded tzinfo non-None and fails this test.
    real.rules = real.rules.model_copy(update={"retention_deadline": datetime(2026, 7, 15, 23, 59, 0)}, deep=True)
    _wire_real_engine(monkeypatch, real)
    calls = _install_recorders(monkeypatch, real.allocate, real.confirm_retention)
    student = next(s for s in real.students if s.id == _unconfirmed_returning_id(real))
    _drive_confirm_and_run(_app(monkeypatch), f"{student.name} ({student.category.value})")
    assert len(calls["confirm"]) == 1
    assert calls["confirm"][0].tzinfo is None
    assert len(calls["allocate"]) >= 1
    assert all(value.tzinfo is None for value in calls["allocate"])
    assert len(calls["late"]) >= 1
    assert all(value.tzinfo is None for value in calls["late"])


def test_streamlit_passes_aware_now_when_rules_deadline_is_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock rules carry an aware deadline, so now_like must track it and hand back aware UTC.
    assert mock.RULES.retention_deadline is not None and mock.RULES.retention_deadline.tzinfo is not None
    calls = _install_recorders(monkeypatch, mock.allocate, mock.confirm_retention)
    _drive_confirm_and_run(_app(monkeypatch), _label("ret-unconfirmed"))
    assert len(calls["confirm"]) == 1
    assert calls["confirm"][0].utcoffset() == timedelta(0)
    assert len(calls["allocate"]) >= 1
    assert all(value.utcoffset() == timedelta(0) for value in calls["allocate"])
    assert len(calls["late"]) >= 1
    assert all(value.utcoffset() == timedelta(0) for value in calls["late"])


def test_rules_rows_formats_retention_deadline_for_humans() -> None:
    naive = mock.RULES.model_copy(update={"retention_deadline": datetime(2026, 10, 31, 23, 59, 0)}, deep=True)
    aware = mock.RULES.model_copy(update={"retention_deadline": datetime(2026, 10, 31, 23, 59, 0, tzinfo=timezone.utc)}, deep=True)
    missing = mock.RULES.model_copy(update={"retention_deadline": None}, deep=True)
    assert dict(view.rules_rows(naive))["Retention deadline"] == "31 Oct 2026 23:59"
    assert dict(view.rules_rows(aware))["Retention deadline"] == "31 Oct 2026 23:59"
    assert dict(view.rules_rows(missing))["Retention deadline"] == "None"
    for rules in (naive, aware, mock.RULES):
        assert "T" not in dict(view.rules_rows(rules))["Retention deadline"]

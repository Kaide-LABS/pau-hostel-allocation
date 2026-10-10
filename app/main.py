from __future__ import annotations

import os
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
USE_MOCK = os.getenv("USE_MOCK", "1") == "1"

import pandas as pd
import streamlit as st

from app import audit, view
from shared.models import AllocationResult, CompileResult, OutcomeStatus, Rules, Student, StudentCategory

REAL_IMPORT_ERROR: str | None = None
save_result: Callable[[AllocationResult], Any] | None = None

if USE_MOCK:
    from app import mock

    allocate = mock.allocate
    confirm_retention = mock.confirm_retention
    compile_policy = mock.compile_policy
    load_students = mock.load_students
    load_hostel = mock.load_hostel
    load_default_rules = mock.load_default_rules
else:
    try:
        from engine.allocate import allocate
        from engine.retention import confirm_retention
        from policy.compile import compile_policy
        from shared.store import load_default_rules, load_hostel, load_students, save_result
    except ImportError as exc:
        REAL_IMPORT_ERROR = exc.name or str(exc)

SAMPLE_POLICY = (
    "Hostels reserve up to 40% of available bed spaces for newly admitted students. "
    "Available bed spaces are those vacated by graduating students or by students who did not confirm they are returning. "
    "Reserved spaces may only be allocated on presentation of a valid Offer of Provisional Admission letter. "
    "Returning students who confirm retention keep their rooms."
)

CSS = """
<style>
html, body, [class*="css"] { font-size: 18px; }
.block-container { padding-top: 2rem; }
[data-testid="stMetric"] {
    border: 1px solid #d0d7de;
    border-left: 0.4rem solid #1F3A5F;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    background: #ffffff;
    color: #111827;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
    font-size: 2.4rem;
    font-weight: 700;
    color: #111827;
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #4B5563;
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
}
.st-key-m_retained [data-testid="stMetric"],
.st-key-m_fresher [data-testid="stMetric"],
.st-key-m_general [data-testid="stMetric"] { border-left-color: #15803D; }
.st-key-m_waitlisted [data-testid="stMetric"] { border-left-color: #B45309; }
.st-key-m_rejected [data-testid="stMetric"] { border-left-color: #B91C1C; }
.step-card {
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 1rem;
    background: #F3F5F8;
    color: #111827;
    height: 100%;
}
.step-num {
    display: inline-block;
    width: 1.8rem;
    height: 1.8rem;
    line-height: 1.8rem;
    text-align: center;
    border-radius: 50%;
    background: #1F3A5F;
    color: #ffffff;
    font-weight: 700;
}
.step-title { font-weight: 700; font-size: 1.1rem; margin: 0.4rem 0 0.25rem 0; color: #111827; }
.student-card, .explanation-box {
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 1rem;
    background: #ffffff;
    color: #111827;
    margin: 0.75rem 0;
}
.audit-pass {
    border-left: 0.45rem solid #1a7f37;
    background: #dafbe1;
    color: #111827;
    padding: 0.8rem 1rem;
    margin-bottom: 0.75rem;
}
.audit-fail {
    border-left: 0.45rem solid #cf222e;
    background: #ffebe9;
    color: #111827;
    padding: 0.8rem 1rem;
    margin-bottom: 0.75rem;
}
</style>
"""


def safe_call(label: str, fn: Callable[..., Any], *args: Any) -> tuple[Any | None, str | None]:
    try:
        return fn(*args), None
    except ValueError as exc:
        return None, str(exc)
    except Exception:
        return None, label


def init_state() -> bool:
    if "state_ready" in st.session_state:
        return bool(st.session_state.state_ready)

    st.session_state.state_ready = False
    st.session_state.compile_result = None
    st.session_state.compile_seconds = None
    st.session_state.result = None
    st.session_state.run_students = []
    st.session_state.policy_text = SAMPLE_POLICY
    st.session_state.selected_student_id = None
    st.session_state.last_receipt = {}
    st.session_state.flash = []

    loaders = [
        ("hostel", "Could not load hostel", load_hostel),
        ("students", "Could not load students", load_students),
        ("rules", "Could not load rules", load_default_rules),
    ]
    for key, label, loader in loaders:
        value, error = safe_call(label, loader)
        if error:
            st.error(f"{label}: {error}.")
            return False
        st.session_state[key] = value

    st.session_state.state_ready = True
    return True


def _student_options(students: list[Student]) -> list[str]:
    return [f"{student.name} ({student.category.value})" for student in students]


def _student_id_from_label(label: str) -> str | None:
    for student in st.session_state.students:
        if label == f"{student.name} ({student.category.value})":
            return student.id
    return None


def _student_by_id(students: list[Student]) -> dict[str, Student]:
    return {student.id: student for student in students}


def _outcome_by_student(result: AllocationResult) -> dict[str, Any]:
    return {outcome.student_id: outcome for outcome in result.outcomes}


def _format_dt(value: datetime | None) -> str:
    return "Not recorded" if value is None else value.strftime("%d %b %Y, %H:%M:%S")


def _render_student_result(student: Student) -> None:
    result = st.session_state.result
    if result is None:
        st.info("No allocation has been run yet. The hostel manager runs it from the Hostel manager tab.")
        return
    outcome = _outcome_by_student(result).get(student.id)
    if outcome is None:
        st.warning("No outcome recorded for this student in the latest run.")
        return
    st.markdown(view.result_status_html(outcome.status), unsafe_allow_html=True)
    if outcome.room_id:
        st.write(f"Room {outcome.room_id}")
    elif outcome.waitlist_position:
        st.write(f"Waitlist position #{outcome.waitlist_position}")
    st.markdown("#### Why")
    st.markdown(view.explanation_box_html(outcome.explanation), unsafe_allow_html=True)
    st.markdown(" ".join(view.tag_html(code) for code in outcome.reason_codes), unsafe_allow_html=True)
    if view.find_placeholders(outcome.explanation):
        st.warning("Explanation contains an unfilled placeholder.")
    run_students = _student_by_id(st.session_state.run_students)
    run_student = run_students.get(student.id)
    if run_student and student.retention_confirmed != run_student.retention_confirmed:
        st.info("Your confirmation was recorded after the last allocation run. It will count in the next run.")


def render_student_tab() -> None:
    st.write(
        "Returning students: confirm you're keeping your room before the deadline and get a receipt. "
        "Everyone: check your result and the reason behind it."
    )
    selected_label = st.selectbox(
        "Student",
        _student_options(st.session_state.students),
        index=None,
        placeholder="Choose a student",
        key="selected_student_label",
    )
    if not selected_label:
        st.session_state.selected_student_id = None
        st.info("Choose a student to begin.")
        return

    selected_id = _student_id_from_label(selected_label)
    if selected_id is None:
        st.session_state.selected_student_id = None
        st.warning("No student matches that selection.")
        return
    st.session_state.selected_student_id = selected_id
    student = _student_by_id(st.session_state.students)[selected_id]
    retention = "confirmed" if student.retention_confirmed else "not confirmed"
    st.markdown(view.student_card_html(student, retention), unsafe_allow_html=True)
    deadline = st.session_state.rules.retention_deadline
    if deadline is not None:
        st.caption(f"Confirmation deadline: {deadline.strftime('%d %b %Y, %H:%M')}")
    if student.category == StudentCategory.RETURNING and not student.retention_confirmed:
        late_text = view.late_warning_text(view.now_like(deadline), deadline, _format_dt)
        if late_text:
            st.warning(late_text)

    receipt = st.session_state.last_receipt.get(student.id) or student.retention_receipt_id
    if student.category != StudentCategory.RETURNING:
        st.button("Confirm I'm keeping my room", key="confirm_retention", disabled=True)
        st.caption("Only current residents confirm retention.")
    elif student.retention_confirmed:
        st.success(
            f"Room kept. Receipt {receipt}, recorded {_format_dt(student.retention_confirmed_at)}. "
            "Keep this receipt as proof of confirmation."
        )
    elif st.button("Confirm I'm keeping my room", key="confirm_retention"):
        call_now = view.now_like(st.session_state.rules.retention_deadline)
        updated, error = safe_call("Could not record your confirmation. Please try again.", confirm_retention, student, call_now)
        if error:
            st.error(error)
        else:
            st.session_state.students = [updated if item.id == updated.id else item for item in st.session_state.students]
            st.session_state.last_receipt[updated.id] = updated.retention_receipt_id
            st.success(
                f"Room kept. Receipt {updated.retention_receipt_id}, recorded {_format_dt(updated.retention_confirmed_at)}. "
                "Keep this receipt as proof of confirmation."
            )
            student = updated

    st.subheader("My result")
    _render_student_result(student)


def _render_compile_result(result: CompileResult) -> None:
    rows = view.rules_rows(result.rules)
    if result.used_fallback:
        suffix = f": {result.error}" if result.error else ""
        st.warning(
            f"Fallback rules in use: the compiler could not process this policy{suffix}. "
            "The app is using the published default rules, so allocation still works."
        )
    elif result.error:
        st.error(result.error)
    elif USE_MOCK:
        st.success("Mock compile: no API call was made.")
    else:
        model = os.getenv("ANTHROPIC_MODEL") or "claude-haiku-5-5"
        seconds = st.session_state.get("compile_seconds")
        timing = f" in {seconds:.1f} s" if seconds is not None else ""
        st.success(
            f"Read live by Claude ({model}){timing}. {len(rows)} rules extracted, "
            f"{len(result.ambiguities)} ambiguities, {len(result.unmapped_clauses)} unmapped clauses."
        )
    st.subheader("How the policy was read")
    if result.ambiguities:
        st.markdown("**Needs a human decision**")
    for item in result.ambiguities:
        st.warning(f"Could be read more than one way: {item}")
    if result.unmapped_clauses:
        st.markdown("**Not covered by the rules engine**")
    for item in result.unmapped_clauses:
        st.error(f"Not mapped to any rule: {item}")
    st.table(pd.DataFrame(rows, columns=["Rule", "Value"]))
    with st.expander("Compiled source text"):
        st.write(result.rules.source_text)


def _status_cell_style(value: str) -> str:
    style = view.STATUS_STYLE[value.lower()]
    return f"color: {style['color']}; background-color: {style['background']}; font-weight: 700"


def _render_result(result: AllocationResult) -> None:
    if st.session_state.get("run_rules") != st.session_state.rules:
        st.caption("Results are from the previous run; run again to update.")
    summary = result.summary
    rows = [
        [
            ("total", "Total beds", summary.total_beds),
            ("retained", "Retained", summary.retained),
            ("available", "Available", summary.available_beds),
            ("reserved", "Reserved for new students", summary.reserved_for_freshers),
        ],
        [
            ("fresher", "New students allocated", summary.freshers_allocated),
            ("general", "General pool allocated", summary.general_allocated),
            ("waitlisted", "Waitlisted", summary.waitlisted),
            ("rejected", "Rejected", summary.rejected),
        ],
    ]
    for row in rows:
        for col, (key, label, value) in zip(st.columns(4), row):
            with col, st.container(key=f"m_{key}"):
                st.metric(label, value)
    st.write(view.reserved_sentence(summary, result.rules))
    statuses = st.multiselect(
        "Show",
        ["Allocated", "Waitlisted", "Rejected"],
        default=["Allocated", "Waitlisted", "Rejected"],
        key="outcome_status_filter",
    )
    df = view.filter_outcomes(view.outcomes_dataframe(result, st.session_state.run_students), statuses)
    styled = df.style.map(_status_cell_style, subset=["Status"])
    st.dataframe(styled, hide_index=True, use_container_width=True)

    ordered = sorted(result.outcomes, key=lambda outcome: (outcome.status != OutcomeStatus.WAITLISTED, outcome.student_id))
    students = _student_by_id(st.session_state.run_students)
    choice = st.selectbox(
        "Why did this student get this outcome?",
        [outcome.student_id for outcome in ordered],
        format_func=lambda student_id: students.get(student_id).name if student_id in students else student_id,
        key="manager_explain_student_id",
    )
    outcome = _outcome_by_student(result)[choice]
    st.markdown(view.explanation_box_html(outcome.explanation), unsafe_allow_html=True)
    if view.find_placeholders(outcome.explanation):
        st.warning("Explanation contains an unfilled placeholder.")


def render_manager_tab() -> None:
    st.write("Paste the hostel's policy, check how it was read, then run the allocation.")
    text = st.text_area("Hostel policy (plain English)", key="policy_text", height=200)
    if st.button("Compile policy", key="compile_policy"):
        if not text.strip():
            st.warning("Paste the policy text first.")
        else:
            started = time.perf_counter()
            result, error = safe_call("Policy compiler failed unexpectedly.", compile_policy, text)
            st.session_state.compile_seconds = time.perf_counter() - started
            if error:
                st.error(error)
            else:
                st.session_state.compile_result = result
                st.session_state.rules = result.rules
    if st.session_state.compile_result:
        _render_compile_result(st.session_state.compile_result)

    if st.button("Run allocation", key="run_allocation"):
        if st.session_state.compile_result is None:
            st.info("Running with the default rules. Compile a policy to use your own.")
        call_now = view.now_like(st.session_state.rules.retention_deadline)
        result, error = safe_call("Allocation failed.", allocate, st.session_state.hostel, st.session_state.students, st.session_state.rules, call_now)
        if error:
            st.error(f"Allocation failed: {error}")
        else:
            st.session_state.result = result
            st.session_state.run_students = deepcopy(st.session_state.students)
            st.session_state.run_rules = result.rules
            if save_result is not None:
                _, save_error = safe_call("Could not save allocation result.", save_result, result)
                if save_error:
                    st.warning(save_error)
            st.success("Allocation run complete.")
    if st.session_state.result:
        _render_result(st.session_state.result)


def _audit_box(title: str, passed: bool, evidence: str) -> None:
    st.markdown(view.audit_box_html(title, passed, evidence), unsafe_allow_html=True)


def render_audit_tab() -> None:
    if st.session_state.result is None:
        st.info("Run an allocation first.")
        return
    retained_passed, retained_evidence = audit.check_retention_honoured(st.session_state.result, st.session_state.run_students)
    reserved_passed, reserved_evidence = audit.check_reserved_within_limit(st.session_state.result)
    _audit_box("Every confirmed on-time retention was honoured.", retained_passed, retained_evidence)
    _audit_box("Reserved seats stayed within the policy limit.", reserved_passed, reserved_evidence)


st.set_page_config(page_title="Hostel Allocation", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

if REAL_IMPORT_ERROR:
    st.error(f"Real engine or compiler not available yet: {REAL_IMPORT_ERROR}. Set USE_MOCK=1 or wait for the merge.")
    st.stop()

STEPS = [
    ("1", "Policy in", "The manager pastes the hostel policy in plain English. Claude converts it into structured rules and flags anything vague instead of guessing."),
    ("2", "Rules applied", "A deterministic engine applies the same rules to every student: on-time returners keep their rooms, up to 40% of available beds go to new students with offer letters, and the rest are allocated by application time."),
    ("3", "Every result explained", "Each student sees exactly why they got a room or a waitlist place, and Student Affairs can audit the whole run."),
]

head_left, head_right = st.columns([5, 1])
with head_left:
    st.title("PAU Hostel Allocation Engine")
    st.write("Fair, explainable bed allocation under the published hostel policy.")
with head_right:
    st.markdown(view.source_pill_html(USE_MOCK), unsafe_allow_html=True)
st.markdown("**The AI reads the policy. It never decides who gets a room.**")
for step_col, (number, title, sentence) in zip(st.columns(3), STEPS):
    step_col.markdown(
        f'<div class="step-card"><div class="step-num">{number}</div><div class="step-title">{title}</div><div>{sentence}</div></div>',
        unsafe_allow_html=True,
    )

ready = init_state()
tabs = st.tabs(["Student", "Hostel manager", "Student Affairs audit"])
if ready:
    with tabs[0]:
        render_student_tab()
    with tabs[1]:
        render_manager_tab()
    with tabs[2]:
        render_audit_tab()
else:
    for tab in tabs:
        with tab:
            st.info("App data is not available yet.")

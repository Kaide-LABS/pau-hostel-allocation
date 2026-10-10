from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import re
from typing import Callable

import pandas as pd

from shared.models import AllocationResult, AllocationSummary, OutcomeStatus, Rules, Student


STATUS_STYLE = {
    OutcomeStatus.ALLOCATED.value: {"color": "#1a7f37", "background": "#dafbe1"},
    OutcomeStatus.WAITLISTED.value: {"color": "#9a6700", "background": "#fff8c5"},
    OutcomeStatus.REJECTED.value: {"color": "#cf222e", "background": "#ffebe9"},
}


def status_label(status: OutcomeStatus | str) -> str:
    value = status.value if isinstance(status, OutcomeStatus) else str(status)
    return value.capitalize()


def rules_rows(rules: Rules) -> list[tuple[str, str]]:
    base = base_label(rules)
    deadline = rules.retention_deadline.strftime("%d %b %Y %H:%M") if rules.retention_deadline else "None"
    return [
        ("Share of available beds reserved for new students", f"{rules.fresher_reservation_pct}%"),
        ("Reservation base", base),
        ("Offer letter required for reserved seats", "Yes" if rules.fresher_requires_offer_letter else "No"),
        ("Retention requires confirmation", "Yes" if rules.retention_requires_confirmation else "No"),
        ("Retention deadline", deadline),
        ("Unused reserved seats released", "Yes" if rules.unused_reservation_released else "No"),
        ("New students may compete for general pool", "Yes" if rules.freshers_may_compete_for_general_pool else "No"),
        ("Tiebreak", "Application time"),
    ]


REASON_LABELS = {
    "RETAINED_CONFIRMED": "Kept room (confirmed on time)",
    "RETENTION_NOT_CONFIRMED": "Did not confirm retention",
    "RETENTION_AFTER_DEADLINE": "Confirmed after deadline",
    "FRESHER_RESERVED_SEAT": "Reserved seat (new student)",
    "FRESHER_RESERVATION_FULL": "Reserved seats full",
    "NO_OFFER_LETTER": "No offer letter",
    "GENERAL_POOL_ALLOCATED": "General pool",
    "GENERAL_POOL_FULL": "General pool full",
    "PREFERENCE_UNAVAILABLE": "Preferred room unavailable",
}


def readable_reasons(codes: list[str]) -> str:
    return " \u00b7 ".join(REASON_LABELS.get(code, code) for code in codes)


def outcomes_dataframe(result: AllocationResult, students: list[Student], readable: bool = False) -> pd.DataFrame:
    """One row per student. `readable=False` keeps the raw reason codes (CSV); `readable=True` shows labels (screen)."""
    reason_column = "Reason" if readable else "Reason codes"
    students_by_id = {student.id: student for student in students}
    rows = []
    for outcome in result.outcomes:
        student = students_by_id.get(outcome.student_id)
        rows.append(
            {
                "Student": student.name if student else outcome.student_id,
                "Category": student.category.value if student else "",
                "Status": status_label(outcome.status),
                "Room": outcome.room_id or "",
                "Waitlist position": str(outcome.waitlist_position) if outcome.waitlist_position else "",
                reason_column: readable_reasons(outcome.reason_codes) if readable else ", ".join(outcome.reason_codes),
                "Explanation": outcome.explanation,
            }
        )
    return pd.DataFrame(rows, columns=["Student", "Category", "Status", "Room", "Waitlist position", reason_column, "Explanation"])


def filter_outcomes(df: pd.DataFrame, statuses: list[str]) -> pd.DataFrame:
    if not statuses:
        return df.iloc[0:0].copy()
    return df[df["Status"].isin(statuses)].copy()


def status_pill_html(status: OutcomeStatus | str) -> str:
    value = status.value if isinstance(status, OutcomeStatus) else str(status).lower()
    style = STATUS_STYLE[value]
    return f'<span style="color:{style["color"]};background:{style["background"]};padding:0.2rem 0.55rem;border-radius:999px;font-weight:700;">{escape(status_label(value))}</span>'


RESULT_COLOR = {
    OutcomeStatus.ALLOCATED.value: "#15803D",
    OutcomeStatus.WAITLISTED.value: "#B45309",
    OutcomeStatus.REJECTED.value: "#B91C1C",
}


def result_status_html(status: OutcomeStatus | str) -> str:
    value = status.value if isinstance(status, OutcomeStatus) else str(status).lower()
    color = RESULT_COLOR[value]
    return f'<div style="font-size:2.2rem;font-weight:800;line-height:1.2;color:{color};background:#ffffff;">{escape(status_label(value))}</div>'


def source_pill_html(use_mock: bool) -> str:
    label, color, background = ("Mock data", "#374151", "#E5E7EB") if use_mock else ("Live engine", "#14532D", "#DCFCE7")
    return (
        '<div style="text-align:right;">'
        f'<span style="color:{color};background:{background};padding:0.25rem 0.75rem;border-radius:999px;font-weight:700;font-size:0.85rem;">{label}</span>'
        '</div>'
    )


def tag_html(text: str) -> str:
    return f'<span style="border:1px solid #d0d7de;border-radius:999px;padding:0.1rem 0.45rem;margin-right:0.25rem;background:#ffffff;color:#111827;">{escape(str(text), quote=True)}</span>'


def base_label(rules: Rules) -> str:
    return "available beds" if rules.reservation_base == "vacated_beds" else "total beds"


def reserved_sentence(summary: AllocationSummary, rules: Rules) -> str:
    base = summary.available_beds if rules.reservation_base == "vacated_beds" else summary.total_beds
    return (
        f"{summary.reserved_for_freshers} of {summary.available_beds} available beds reserved for new students "
        f"({rules.fresher_reservation_pct}% of {base} {base_label(rules)})."
    )


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None


def now_like(reference: datetime | None) -> datetime:
    """Current time in the same flavour as `reference`: aware UTC if it is aware, naive local otherwise."""
    if reference is not None and _is_aware(reference):
        return datetime.now(timezone.utc)
    return datetime.now()


def is_after(a: datetime | None, b: datetime | None) -> bool:
    """True when `a` is strictly later than `b`. Never raises; a naive value is treated as local time."""
    if a is None or b is None:
        return False
    try:
        if _is_aware(a) != _is_aware(b):
            a = a if _is_aware(a) else a.astimezone()
            b = b if _is_aware(b) else b.astimezone()
        return a > b
    except (TypeError, ValueError, OverflowError, OSError):
        return False


def late_warning_text(now: datetime, deadline: datetime | None, formatter: Callable[[datetime | None], str]) -> str | None:
    if not is_after(now, deadline):
        return None
    return f"The retention deadline was {formatter(deadline)}. A confirmation now will be recorded as late."


def _text(value: object) -> str:
    # quote=False keeps apostrophes and quotes readable; only &, < and > are escaped.
    return escape(str(value), quote=False)


def explanation_box_html(explanation: str) -> str:
    return f'<div class="explanation-box">{_text(explanation)}</div>'


def student_card_html(student: Student, retention: str) -> str:
    return (
        f'<div class="student-card"><strong>{_text(student.name)}</strong><br>Category: {_text(student.category.value)}<br>'
        f'Current room: {_text(student.current_room_id or "None")}<br>Retention: {_text(retention)}</div>'
    )


def audit_box_html(title: str, passed: bool, evidence: str) -> str:
    state = "PASS" if passed else "FAIL"
    cls = "audit-pass" if passed else "audit-fail"
    return f'<div class="{cls}"><strong>{state}</strong> {_text(title)}<br>{_text(evidence)}</div>'


def find_placeholders(text: str) -> list[str]:
    return re.findall(r"\{[^{}]+\}", text)

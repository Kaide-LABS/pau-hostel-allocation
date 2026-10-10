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
    base = "vacated beds" if rules.reservation_base == "vacated_beds" else "total beds"
    deadline = rules.retention_deadline.isoformat() if rules.retention_deadline else "None"
    return [
        ("Share of vacated beds reserved for new students", f"{rules.fresher_reservation_pct}%"),
        ("Reservation base", base),
        ("Offer letter required for reserved seats", "Yes" if rules.fresher_requires_offer_letter else "No"),
        ("Retention requires confirmation", "Yes" if rules.retention_requires_confirmation else "No"),
        ("Retention deadline", deadline),
        ("Unused reserved seats released", "Yes" if rules.unused_reservation_released else "No"),
        ("New students may compete for general pool", "Yes" if rules.freshers_may_compete_for_general_pool else "No"),
        ("Tiebreak", "Application time"),
    ]


def outcomes_dataframe(result: AllocationResult, students: list[Student]) -> pd.DataFrame:
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
                "Reason": ", ".join(outcome.reason_codes),
            }
        )
    return pd.DataFrame(rows, columns=["Student", "Category", "Status", "Room", "Waitlist position", "Reason"])


def filter_outcomes(df: pd.DataFrame, statuses: list[str]) -> pd.DataFrame:
    if not statuses:
        return df.iloc[0:0].copy()
    return df[df["Status"].isin(statuses)].copy()


def status_pill_html(status: OutcomeStatus | str) -> str:
    value = status.value if isinstance(status, OutcomeStatus) else str(status).lower()
    style = STATUS_STYLE[value]
    return f'<span style="color:{style["color"]};background:{style["background"]};padding:0.2rem 0.55rem;border-radius:999px;font-weight:700;">{escape(status_label(value))}</span>'


def tag_html(text: str) -> str:
    return f'<span style="border:1px solid #d0d7de;border-radius:999px;padding:0.1rem 0.45rem;margin-right:0.25rem;">{escape(str(text), quote=True)}</span>'


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

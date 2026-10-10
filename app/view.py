from __future__ import annotations

from html import escape
import re

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
                "Waitlist position": outcome.waitlist_position or "",
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


def reserved_sentence(summary: AllocationSummary, rules: Rules) -> str:
    base = summary.available_beds if rules.reservation_base == "vacated_beds" else summary.total_beds
    label = "available beds" if rules.reservation_base == "vacated_beds" else "total beds"
    return f"{summary.reserved_for_freshers} of {summary.available_beds} available beds reserved for new students ({rules.fresher_reservation_pct}% of {base} {label})."


def find_placeholders(text: str) -> list[str]:
    return re.findall(r"\{[^{}]+\}", text)

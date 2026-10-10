from __future__ import annotations

from datetime import datetime
from string import Formatter
from typing import Mapping, Sequence

REASON_CODES: tuple[str, ...] = (
    "RETAINED_CONFIRMED",
    "RETENTION_NOT_CONFIRMED",
    "RETENTION_AFTER_DEADLINE",
    "FRESHER_RESERVED_SEAT",
    "FRESHER_RESERVATION_FULL",
    "NO_OFFER_LETTER",
    "GENERAL_POOL_ALLOCATED",
    "GENERAL_POOL_FULL",
    "PREFERENCE_UNAVAILABLE",
)

TEMPLATES: dict[str, str] = {
    "RETAINED_CONFIRMED": "You kept room {room}. You confirmed retention on {confirmed_at} (receipt {receipt}).",
    "RETENTION_NOT_CONFIRMED": "Your room was released because no retention confirmation was recorded.",
    "RETENTION_AFTER_DEADLINE": "Your confirmation on {confirmed_at} came after the deadline of {deadline}.",
    "FRESHER_RESERVED_SEAT": "You received one of {reserved} seats reserved for new students ({pct}% of {base} {base_label}).",
    "FRESHER_RESERVATION_FULL": "All {reserved} seats reserved for new students were filled. You are #{pos} on the waitlist.",
    "NO_OFFER_LETTER": "Reserved seats require a valid Offer of Provisional Admission letter, and none is on record.",
    "GENERAL_POOL_ALLOCATED": "You were allocated from the {general} general beds, in application order (applied {applied_at}).",
    "GENERAL_POOL_FULL": "All {general} general beds were filled before your application ({applied_at}). You are #{pos} on the waitlist.",
    "PREFERENCE_UNAVAILABLE": "Your preferred room type was full, so you were placed in a {type} room.",
}

_RETENTION_NOT_REQUIRED = (
    "You kept room {room}. Retention confirmation was not required under the current rules."
)


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%d %b %Y %H:%M")


def explain_code(code: str, ctx: Mapping[str, object]) -> str:
    if code not in TEMPLATES:
        raise ValueError(f"unknown reason code: {code}")
    if code == "RETAINED_CONFIRMED":
        if ctx.get("confirmation_required", True) is False:
            template = _RETENTION_NOT_REQUIRED
        elif ctx["confirmed_at"] is None:
            sentence = f"You kept room {_format_value(ctx['room'])}. Your retention confirmation is on record."
            if ctx.get("receipt") is not None:
                sentence = sentence[:-1] + f" (receipt {_format_value(ctx['receipt'])})."
            return sentence
        elif ctx.get("receipt") is None:
            return (
                f"You kept room {_format_value(ctx['room'])}. "
                f"You confirmed retention on {_format_value(ctx['confirmed_at'])}."
            )
        else:
            template = TEMPLATES[code]
    else:
        template = TEMPLATES[code]
    values = {key: _format_value(ctx[key]) for key in _placeholder_names(template)}
    return template.format(**values)


def build_explanation(codes: Sequence[str], ctx: Mapping[str, object]) -> str:
    if not codes:
        raise ValueError("at least one reason code is required")
    return " ".join(explain_code(code, ctx) for code in codes)


def _format_value(value: object) -> str:
    if isinstance(value, datetime):
        return fmt_dt(value)
    return str(value)


def _placeholder_names(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name is not None
    }

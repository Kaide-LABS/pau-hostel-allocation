"""Shared data models. FROZEN: change only via the owner. See CONTRACT.md section 3."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StudentCategory(str, Enum):
    RETURNING = "returning"   # current resident of THIS hostel
    TRANSFER = "transfer"     # existing PAU student not currently in this hostel
    FRESHER = "fresher"       # newly admitted


class Student(BaseModel):
    id: str
    name: str                                  # INVENTED names only, never real students
    category: StudentCategory
    current_room_id: str | None = None         # RETURNING only
    retention_confirmed: bool = False
    retention_confirmed_at: datetime | None = None
    retention_receipt_id: str | None = None
    has_offer_letter: bool = False             # FRESHER only
    applied_at: datetime
    preferred_room_type: Literal["single", "double", "quad"] | None = None


class Room(BaseModel):
    id: str                                    # e.g. "B204"
    type: Literal["single", "double", "quad"]
    capacity: int = Field(ge=1)
    price_naira: int = Field(ge=0)


class Hostel(BaseModel):
    id: str
    name: str                                  # invented, e.g. "Palmgrove Hall"
    rooms: list[Room]


class Rules(BaseModel):
    version: int = 1
    fresher_reservation_pct: int = Field(ge=0, le=100, default=40)
    reservation_base: Literal["vacated_beds", "total_beds"] = "vacated_beds"
    fresher_requires_offer_letter: bool = True
    retention_requires_confirmation: bool = True
    retention_deadline: datetime | None = None
    unused_reservation_released: bool = True          # unfilled fresher seats go to the general pool
    freshers_may_compete_for_general_pool: bool = False
    tiebreak: Literal["applied_at"] = "applied_at"
    source_text: str = ""


class CompileResult(BaseModel):
    rules: Rules
    unmapped_clauses: list[str] = []   # policy sentences the compiler could NOT map to a rule field
    ambiguities: list[str] = []        # sentences that map but could be read more than one way
    used_fallback: bool = False
    error: str | None = None


class OutcomeStatus(str, Enum):
    ALLOCATED = "allocated"
    WAITLISTED = "waitlisted"
    REJECTED = "rejected"


class StudentOutcome(BaseModel):
    student_id: str
    status: OutcomeStatus
    room_id: str | None = None
    waitlist_position: int | None = None
    reason_codes: list[str]            # at least one, from CONTRACT.md section 5
    explanation: str                   # built from templates, NOT LLM-written


class AllocationSummary(BaseModel):
    total_beds: int
    retained: int
    available_beds: int                # total_beds - retained
    reserved_for_freshers: int         # floor(pct/100 * base)
    freshers_allocated: int
    general_allocated: int
    waitlisted: int
    rejected: int


class AllocationResult(BaseModel):
    hostel_id: str
    rules: Rules
    outcomes: list[StudentOutcome]
    summary: AllocationSummary
    run_at: datetime

# CONTRACT.md — Hostel Allocation Engine (TIC Mini Hackathon, Challenge 03)

Every session reads this file before writing code. Build against these shapes exactly. If something here is wrong or missing, STOP and tell the owner. Do not invent a workaround in your own folder.

## 0. What we are building (one paragraph)

A tool a hostel manager uses to run room allocation under the university's published policy, which Student Affairs can audit. Students confirm room retention digitally and get a timestamped receipt. The manager pastes the policy text. AI compiles it into a validated rules file. A deterministic allocator applies the rules. Every student sees their outcome and the exact rule that decided it. We do NOT take allocation away from the hostels. Student Affairs' own statement says hostels determine their own room allocation, so we give them a fair, auditable way to do it.

## 1. Stack (fixed)

- Python 3.11, Streamlit (UI), Pydantic v2 (models and validation), pytest
- LLM: Claude via the `anthropic` Python SDK. Key in env `ANTHROPIC_API_KEY`, model in env `ANTHROPIC_MODEL` (default `claude-haiku-5-5`). Never commit the key: read it from the environment or a gitignored `.env`. No other LLM provider anywhere in the codebase.
- No database. JSON files in `data/`, read and written through `shared/store.py`
- No OR-Tools unless the owner approves. The allocator is deterministic priority logic.

## 2. Folder ownership (hard rule: write ONLY in your folder)

| Path | Owner | Notes |
|---|---|---|
| `shared/models.py`, `shared/store.py` | OWNER (Hafeedh) | Created before sessions start. FROZEN. Change only via the owner. |
| `README.md`, `requirements.txt`, `CONTRACT.md` | OWNER | Sessions list new packages in `<their folder>/NEEDS.txt`; the owner merges them. |
| `engine/`, `tests/test_engine.py` | SESSION A | Allocator plus explanations |
| `data/` | SESSION A (creates); everyone else read-only | Fixtures. First deliverable, due 12:00. |
| `policy/`, `tests/test_policy.py` | SESSION B | Policy compiler |
| `app/` | SESSION C | Streamlit UI |
| `specs/session-X.md` | OWNER | Each session's brief. Read-only for sessions. |
| `specs/session-X-prd.md` | SESSION X | The PRD that session's multi-loopr spec phase produces. |

## 2a. Worktrees and branches

Three worktrees, created from the same `main` commit that holds this file and `shared/`:

| Session | Worktree | Branch |
|---|---|---|
| A — engine | `../hostel-a` | `session-a` |
| B — policy compiler | `../hostel-b` | `session-b` |
| C — UI | `../hostel-c` | `session-c` |

- Each session works ONLY inside its own worktree, and writes ONLY to the folders section 2 assigns it. Never edit files in another worktree.
- To see another session's pushed work, read only: `git fetch origin && git show origin/session-a:engine/allocate.py`, or `git diff main...origin/session-b`.
- Never merge another session's branch into your own. The owner merges all three into `main` at 13:00 and 14:30. After each merge, run `git fetch origin && git rebase origin/main` before continuing.
- Push your branch to `origin` at least every 30 minutes.

## 2b. Spec phase (multi-loopr)

**multi-loopr role pinning (all three sessions, every run):**

| Role | Provider |
|---|---|
| Spec / PRD author and orchestrator | Claude (the session itself) |
| Executor (writes all code) | Codex |
| Reviewer | Claude (gets the spec artifacts plus the diff, never the conversation) |

If multi-loopr rejects this pinning, or would let one provider review its own diff, stop and report it.

Each session runs multi-loopr's full spec pipeline (interrogation, documentation and research layer, PRD), with three limits:

1. **Timebox: 25 minutes.** Save the PRD to `specs/session-X-prd.md` and start building by 12:05 at the latest.
2. **Contract wins.** Sections 1, 2, 2a, 3 and 4, plus your own section (A: 5 and 8; B: 6; C: 7), and sections 9 and 10, are hard constraints. Your PRD may add depth inside your folder: edge cases, error handling, internal structure, tests beyond section 9. It must NOT change any shared model, function signature, folder ownership, reason code, algorithm step or demo step. If research suggests the contract is wrong, write it under "## Contract conflicts" in your PRD and tell the owner. Do not build around it.
3. **Research stays on your folder's stack:**
   - A: Python, Pydantic, pytest.
   - B: Anthropic Python SDK tool use, Pydantic JSON schema.
   - C: Streamlit layout, session_state, styling.

Git: freeze is 16:00. No pushes after.

## 3. Shared models (`shared/models.py`, owner pastes this verbatim)

```python
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
    reason_codes: list[str]            # at least one, from section 5
    explanation: str                   # built from templates in section 5, NOT LLM-written

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
```

`shared/store.py` (owner): `load_students() -> list[Student]`, `save_students(list[Student])`, `load_hostel() -> Hostel`, `load_default_rules() -> Rules`, `save_result(AllocationResult)`, `load_result() -> AllocationResult | None`. All paths live under `data/`.

## 4. Function interfaces (the only cross-folder calls)

```python
# engine/allocate.py  (SESSION A)
def allocate(hostel: Hostel, students: list[Student], rules: Rules, now: datetime) -> AllocationResult: ...

# engine/retention.py  (SESSION A)
def confirm_retention(student: Student, now: datetime) -> Student:
    """Sets retention_confirmed, retention_confirmed_at, and a receipt id like 'RET-<hostel>-<6 hex>'.
    Raises ValueError if the student is not RETURNING."""

# policy/compile.py  (SESSION B)
def compile_policy(text: str) -> CompileResult:
    """Never raises. On any failure returns the default rules with used_fallback=True and error set."""
```

The UI (SESSION C) calls only these three functions plus `shared/store.py`.

## 5. Allocation algorithm (SESSION A implements exactly this)

1. **Retain.** Each RETURNING student keeps `current_room_id` if `retention_confirmed` is true (or `retention_requires_confirmation` is false) AND, when `retention_deadline` is set, `retention_confirmed_at <= retention_deadline`. → ALLOCATED, `RETAINED_CONFIRMED`.
2. **Count.** `available_beds = total_beds - retained`.
3. **Reserve.** `base = available_beds` if `reservation_base == "vacated_beds"`, else `total_beds`. `reserved = floor(fresher_reservation_pct / 100 * base)`, capped at `available_beds`.
4. **Freshers into reserved seats.** Eligible freshers (offer letter present if required), sorted by tiebreak, fill up to `reserved` seats. → `FRESHER_RESERVED_SEAT`. Freshers missing a required offer letter → REJECTED, `NO_OFFER_LETTER`.
5. **General pool.** `general = available_beds - freshers_filled` if `unused_reservation_released`, else `available_beds - reserved`. Candidates: RETURNING students not retained, all TRANSFER students, plus remaining eligible freshers if `freshers_may_compete_for_general_pool`. Sort by tiebreak and fill. → `GENERAL_POOL_ALLOCATED`.
6. **Waitlist.** Everyone left → WAITLISTED with a 1-based position in tiebreak order, plus the code for why they missed:
   - `FRESHER_RESERVATION_FULL`
   - `GENERAL_POOL_FULL`
   - `RETENTION_NOT_CONFIRMED`
   - `RETENTION_AFTER_DEADLINE`
7. **Room assignment.** Retained students keep their room. Others go to the first room with a free bed matching `preferred_room_type`, else any free bed (add `PREFERENCE_UNAVAILABLE`). Process in allocation order.

**Explanation templates** (A owns the exact wording in `engine/explain.py`; every number is filled from the run, never invented):

- `RETAINED_CONFIRMED` → "You kept room {room}. You confirmed retention on {confirmed_at} (receipt {receipt})."
- `RETENTION_NOT_CONFIRMED` → "Your room was released because no retention confirmation was recorded."
- `RETENTION_AFTER_DEADLINE` → "Your confirmation on {confirmed_at} came after the deadline of {deadline}."
- `FRESHER_RESERVED_SEAT` → "You received one of {reserved} seats reserved for new students ({pct}% of {base} {base_label})."
- `FRESHER_RESERVATION_FULL` → "All {reserved} seats reserved for new students were filled. You are #{pos} on the waitlist."
- `NO_OFFER_LETTER` → "Reserved seats require a valid Offer of Provisional Admission letter, and none is on record."
- `GENERAL_POOL_ALLOCATED` → "You were allocated from the {general} general beds, in application order (applied {applied_at})."
- `GENERAL_POOL_FULL` → "All {general} general beds were filled before your application ({applied_at}). You are #{pos} on the waitlist."
- `PREFERENCE_UNAVAILABLE` → "Your preferred room type was full, so you were placed in a {type} room."

## 6. Policy compiler rules (SESSION B)

- One Claude call (`messages.create`), temperature 0, `max_tokens` ≤ 1024. Force structured output with a single tool named `emit_rules` and `tool_choice={"type": "tool", "name": "emit_rules"}`. Its `input_schema` is `{"rules": <Rules JSON schema>, "unmapped_clauses": [str], "ambiguities": [str]}`. Read the tool-use block's input. Never parse free text.
- Map each policy sentence to `Rules` fields. Sentences that fit no field go to `unmapped_clauses`, verbatim. Never drop them silently.
- "Up to X%" means `fresher_reservation_pct = X`. Ambiguous wording (e.g. whether freshers can also compete for general beds) uses the default value AND adds the sentence to `ambiguities`.
- Validate with `Rules.model_validate`. If validation fails, retry once with the error appended. If it fails again → `load_default_rules()`, `used_fallback=True`, `error` set.
- No network or no key → fallback immediately. The demo must work offline.
- `source_text` = the input text.
- Ship `data/sample_policy.txt` content in `policy/` as a constant for tests. Its text is the Student Affairs rule, paraphrased:
  "Hostels reserve up to 40% of available bed spaces for newly admitted students. Available bed spaces are those vacated by graduating students or by students who did not confirm they are returning. Reserved spaces may only be allocated on presentation of a valid Offer of Provisional Admission letter. Returning students who confirm retention keep their rooms."

## 7. UI (SESSION C)

Three tabs in one Streamlit app (`app/main.py`, run with `streamlit run app/main.py`):

1. **Student.** Pick a student → "Confirm I'm keeping my room" (RETURNING only) → shows the receipt id and timestamp. "My result" → status, room or waitlist position, and the explanation sentence(s).
2. **Hostel manager.**
   - A policy textarea (prefilled with the sample) → "Compile policy" → shows the rules as a readable table, with yellow warnings for `ambiguities`, red for `unmapped_clauses`, and a banner if `used_fallback`.
   - "Run allocation" → summary metrics (total, retained, available, reserved, freshers allocated, general allocated, waitlisted) plus an outcomes table, filterable by status.
3. **Student Affairs audit** (cut first if late). Did the hostel honour every confirmed retention? Were reserved seats within the policy limit? Shows a pass or fail line for each.

Until A and B merge, C builds against `app/mock.py`: hand-made objects that match section 3 exactly. Every button must survive bad input. Show `st.error` messages, never a stack trace.

## 8. Fixtures (SESSION A, due 12:00, built BEFORE the spec phase)

- `data/hostel.json`: one invented hostel, 10 rooms, 24 beds total (mix of single, double and quad).
- `data/students.json`: 32 invented students:
  - 14 RETURNING (10 confirmed, 1 confirmed after the deadline, 3 not confirmed)
  - 6 TRANSFER
  - 12 FRESHER (10 with an offer letter, 2 without)
  
  Mixed `applied_at` times and preferences. Demand must exceed supply so the waitlist is non-empty.
- `data/default_rules.json`: the `Rules` defaults, with `retention_deadline` set.

## 9. Invariants (tests must assert; A in `test_engine.py`, B in `test_policy.py`)

- No room exceeds capacity. Total allocated ≤ total beds.
- Every confirmed, on-time RETURNING student is retained.
- Freshers in reserved seats ≤ `reserved`.
- Every student has exactly one outcome and ≥1 reason code. Explanations contain no unfilled `{placeholders}`.
- Determinism: the same inputs produce identical outcomes.
- Changing `fresher_reservation_pct` from 40 to 30 changes `reserved` accordingly (the demo's magic moment).
- `compile_policy` never raises: test empty text, garbage text, and a missing API key.

## 10. Demo path (everything must serve this, in 3 minutes)

1. Student tab: a returning student confirms retention → receipt.
2. Manager tab: compile the sample policy → rules table. Run → summary plus waitlist.
3. Click one waitlisted student → their reason, with real numbers.
4. Edit the policy from 40% to 30% → recompile → rerun → numbers and explanations change live.
5. (If built) The audit tab shows all passes.

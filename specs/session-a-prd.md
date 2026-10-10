# SESSION A PRD: Allocation engine

Status: confirmed at loopr Gate 1 and Gate 2 (owner). Hard constraints: CONTRACT.md sections 1, 2, 2a, 3, 4, 5, 8, 9, 10. This PRD adds depth inside `engine/`, `tests/test_engine.py` and `data/`. It changes no model, signature, reason code, algorithm step or demo step.

Companion artifacts (untracked, produced by loopr): `.claude/loopr/baby_prd.md`, `.claude/loopr/context.md`, `.claude/loopr/conformance-ledger.md`.

## 1. Outcome

A PAU hostel manager can run room allocation under the published policy in a way Student Affairs can audit. Every student sees their outcome with the exact rule and real numbers that decided it. Hostels keep allocation authority. Explanations are template-built, never LLM-written.

## 2. Deliverables and ownership

| File | Content |
|---|---|
| `engine/__init__.py` | empty |
| `engine/explain.py` | one template per reason code, `build_explanation(codes, ctx) -> str` |
| `engine/retention.py` | `confirm_retention(student, now) -> Student` |
| `engine/allocate.py` | `allocate(hostel, students, rules, now) -> AllocationResult` |
| `tests/test_engine.py` | every section 9 engine invariant plus section 7 below |
| `data/*.json` | done, commit 93883cc, do not change counts |
| `engine/NEEDS.txt` | only if a new package is needed (none expected: stdlib, pydantic, pytest) |

Codex edits only these paths. Conventions (conformance ledger: CONFORM): `from __future__ import annotations` at the top of every module; models imported as `from shared.models import ...`; Python 3.11 syntax only. No LLM, no network, no randomness, no clock reads inside `allocate` (time comes from `now`).

## 3. Interpretation decisions (depth, inside the contract)

D1. **Datetimes are naive** everywhere (fixtures are naive). If a comparison raises `TypeError` (naive vs aware), `allocate` raises `ValueError("mixed naive and timezone-aware datetimes")`.

D2. **Tiebreak** = ascending `(applied_at, id)`. The `id` secondary key makes ties deterministic. `Rules.tiebreak` has one allowed value.

D3. **Integer math** for reservation: `reserved = min((pct * base) // 100, available_beds)`. No floats, so 30% of 14 is exactly 4.

D4. **Retention check (step 1)** for a RETURNING student with a `current_room_id`:
- `confirmation_ok` = `retention_confirmed` is true, or `retention_requires_confirmation` is false.
- `on_time` = `retention_deadline` is None, or `retention_requires_confirmation` is false, or (`retention_confirmed_at` is not None and `retention_confirmed_at <= retention_deadline`).
- Retained iff `confirmation_ok and on_time`.
- A RETURNING student with no `current_room_id` cannot be retained and is a plain general-pool candidate (no retention reason code).

D5. **Retention-loss reason code.** A RETURNING student with a room who is NOT retained gets, as the FIRST reason code, `RETENTION_AFTER_DEADLINE` if `retention_confirmed` is true and `retention_confirmed_at` is after the deadline, else `RETENTION_NOT_CONFIRMED`. This applies whether they then win a general bed or are waitlisted. (Owner approved at Gate 1. CONTRACT step 6 lists these as waitlist reasons only. See Contract conflicts C2.)

D6. **Reason code order** in `reason_codes` (and so in the explanation sentences): retention-loss code (D5) → pool outcome code → `PREFERENCE_UNAVAILABLE`. An outcome always has at least one code.
- Retained: `[RETAINED_CONFIRMED]`.
- Fresher in reserved seat: `[FRESHER_RESERVED_SEAT]` (+ `PREFERENCE_UNAVAILABLE`).
- Fresher without required offer letter: REJECTED, `[NO_OFFER_LETTER]`. Never waitlisted.
- Eligible fresher not seated, `freshers_may_compete_for_general_pool` false: WAITLISTED, `[FRESHER_RESERVATION_FULL]`.
- Eligible fresher not seated, may compete: joins the general pool. If allocated: `[GENERAL_POOL_ALLOCATED]`. If missed: WAITLISTED, `[FRESHER_RESERVATION_FULL, GENERAL_POOL_FULL]`.
- General candidate allocated: pool outcome `GENERAL_POOL_ALLOCATED` (+ `PREFERENCE_UNAVAILABLE`). Missed: WAITLISTED, `GENERAL_POOL_FULL`.

D7. **Waitlist position** is one global 1-based queue over all WAITLISTED students, ordered by the D2 tiebreak. (A single waitlist matches the single `waitlisted` count in the summary.)

D8. **Summary fields.** `reserved_for_freshers` = `reserved` (step 3 value). `freshers_allocated` = students with `FRESHER_RESERVED_SEAT`. `general_allocated` = students with `GENERAL_POOL_ALLOCATED` (including any competing freshers). `waitlisted` / `rejected` = outcome counts. `retained` = count of `RETAINED_CONFIRMED`. `total_beds` = sum of room capacities. `available_beds = total_beds - retained`.

D9. **Room assignment (step 7).** Room order is `hostel.rooms` order. Occupancy starts with retained students in their own rooms. Allocation order = reserved-seat freshers (D2), then general-pool allocated (D2). For each: first room with a free bed whose `type == preferred_room_type`; if none (or the preference is None and no room qualifies, impossible), the first room with any free bed, and add `PREFERENCE_UNAVAILABLE` only when a preference existed and was not met. Preference None: first room with any free bed, no extra code. Because seats are bounded by free beds, a free bed always exists. If not, raise `RuntimeError` (internal invariant), never return a partial result.

D10. **Input validation (`ValueError`, clear message):** duplicate student ids; duplicate room ids; a retained student whose `current_room_id` is not in the hostel; retained occupants exceeding a room's capacity. `allocate` never mutates its inputs. `outcomes` are in input-student order. `run_at = now`.

D11. **`confirm_retention`:**
- Not RETURNING → `ValueError`.
- Already `retention_confirmed` with a receipt → return the student unchanged (idempotent; keeps the original timestamp so a later click cannot turn an on-time confirmation into a late one).
- Otherwise return `Student.model_validate({**student.model_dump(), "retention_confirmed": True, "retention_confirmed_at": now, "retention_receipt_id": f"RET-{HOSTEL}-{hex6}"})`. Do NOT use `model_copy(update=...)`: it performs no validation (R2).
- `HOSTEL` = `shared.store.load_hostel().id.upper()`; on any exception use `"HOSTEL"`. `hex6` = first 6 hex chars of `sha256(f"{student.id}|{now.isoformat()}")`. Deterministic, not random. Input is never mutated.

D12. **Confirmation not required.** If `retention_requires_confirmation` is false and a retained student has no confirmation, the `RETAINED_CONFIRMED` explanation uses the variant: "You kept room {room}. Retention confirmation was not required under the current rules." (Same code, no `None` leaks.)

## 4. Explanation templates (`engine/explain.py`)

Wording is CONTRACT section 5 verbatim. Date format `fmt_dt(dt)` = `dt.strftime("%d %b %Y %H:%M")`, e.g. `02 Jul 2026 10:14`. `base_label` = `"vacated beds"` or `"total beds"`. `{base}` is the numeric base from step 3. `{pct}` is the integer. Explanation of an outcome = the sentences for its `reason_codes`, in order, joined by one space.

Context dict keys (all filled from the run): `room`, `confirmed_at`, `receipt`, `deadline`, `reserved`, `pct`, `base`, `base_label`, `general`, `applied_at`, `pos`, `type`. A missing key needed by a code's template raises `KeyError` inside the engine (a bug), never leaves `{...}` in output.

## 5. Algorithm (CONTRACT section 5, steps 1-7, exactly)

1. Retain per D4 → ALLOCATED, `RETAINED_CONFIRMED`.
2. `available_beds = total_beds - retained`.
3. `base = available_beds` if `reservation_base == "vacated_beds"` else `total_beds`; `reserved` per D3.
4. Eligible freshers (offer letter present if required), sorted D2, fill `min(reserved, len(eligible))` seats. Ineligible → REJECTED `NO_OFFER_LETTER`.
5. `general = available_beds - freshers_filled` if `unused_reservation_released` else `available_beds - reserved`. Candidates: RETURNING not retained, all TRANSFER, plus remaining eligible freshers iff `freshers_may_compete_for_general_pool`. Sort D2, fill `general` (never below 0).
6. Everyone left → WAITLISTED with D6 codes and D7 positions.
7. Room assignment per D9.

## 6. Acceptance numbers on the fixtures (default rules: 40%, vacated_beds, deadline 2026-07-15 23:59)

- Summary at 40%: total_beds 24, retained 10, available 14, reserved 5, freshers_allocated 5 (F01-F05), general_allocated 9, waitlisted 6, rejected 2 (F11, F12).
- Waitlist at 40%, in order: F06 #1, F07 #2, F08 #3, F09 #4, F10 #5 (all `FRESHER_RESERVATION_FULL`), R08 #6 (`RETENTION_AFTER_DEADLINE`, `GENERAL_POOL_FULL`).
- General pool at 40% (applied order): R02, R06, R14, T01-T06 allocated; R02/R06/R14 carry `RETENTION_NOT_CONFIRMED` first.
- At 30%: reserved 4 (F01-F04), general 10, general_allocated 10, R08 now allocated (still carries `RETENTION_AFTER_DEADLINE`), waitlisted 6 (F05-F10), rejected 2.
- Every code appears across the two runs: `RETAINED_CONFIRMED`, `RETENTION_NOT_CONFIRMED`, `RETENTION_AFTER_DEADLINE`, `FRESHER_RESERVED_SEAT`, `FRESHER_RESERVATION_FULL`, `NO_OFFER_LETTER`, `GENERAL_POOL_ALLOCATED`, `GENERAL_POOL_FULL`, `PREFERENCE_UNAVAILABLE`.

If the implementation disagrees with these numbers, stop and report which side is wrong. Do not edit fixtures or numbers to force agreement.

## 7. Tests (`tests/test_engine.py`)

First lines of the file insert the repo root into `sys.path` (`Path(__file__).resolve().parents[1]`) so `pytest tests/test_engine.py` works from the repo root. This is required, not cosmetic: in the default prepend import mode pytest adds only the test file's own directory (`tests/`) to `sys.path`, and plain `pytest` (unlike `python -m pytest`) does not add the current directory (R1). The module name `test_engine` must stay unique across sessions' test files. Tests load fixtures through `shared.store`. `now` is a fixed datetime, never the clock.

Section 9 invariants (parametrised over several rule variants where cheap):
1. No room over capacity; total allocated ≤ total beds.
2. Every confirmed on-time RETURNING student is retained, in their own room.
3. Freshers in reserved seats ≤ `reserved`.
4. Every student has exactly one outcome, ≥1 reason code, from the section 5 code set only; explanation contains no `{` or `}`.
5. Determinism: two calls produce equal `model_dump()` of outcomes and summary; shuffled input order gives the same per-student outcomes.
6. 40% → 30%: `reserved` 5 → 4, `general_allocated` 9 → 10, R08 flips WAITLISTED → ALLOCATED, F05 flips ALLOCATED → WAITLISTED, explanation text changes.

Extra depth:
7. Section 6 numbers, exactly (summary, waitlist order and positions, rejected ids).
8. Code coverage: union of reason codes over the 40% and 30% runs equals all 9 codes.
9. Template exactness: for each code, build an explanation from a known context and compare to the CONTRACT wording with the numbers filled.
10. `confirm_retention`: happy path (fields set, receipt matches `^RET-[A-Z0-9]+-[0-9a-f]{6}$`, original untouched); TRANSFER and FRESHER raise `ValueError`; idempotent second call; same inputs give same receipt.
11. Edge rules (small hand-built hostels): `reservation_base="total_beds"` with cap at available; pct 0 and 100; `unused_reservation_released` false vs true; `freshers_may_compete_for_general_pool` true (including the two-code waitlist case); `fresher_requires_offer_letter` false; `retention_requires_confirmation` false (D4, D12); `retention_deadline` None; confirmed but `retention_confirmed_at` None with a deadline; RETURNING with no room; empty student list; preference fallback sets `PREFERENCE_UNAVAILABLE`; preference None sets nothing.
12. Validation errors (D10) and the mixed-timezone `ValueError` (D1).

## 8. Done means

- `pytest tests/test_engine.py` green.
- `allocate()` on fixtures: non-empty waitlist, all 9 codes exercised (section 6).
- multi-loopr evidence passes and is reported honestly.
- `git diff main...session-a` touches only `engine/`, `tests/test_engine.py`, `data/`, `specs/session-a-prd.md`.

## Research notes (documentation layer, scope: Python, Pydantic v2, pytest)

Sources: pytest docs "import mechanisms and sys.path" (docs.pytest.org/en/latest/explanation/pythonpath.html), Python `datetime` docs (via mirrors), Pydantic migration guide, and the installed Pydantic 2.14.0 `BaseModel.model_copy` docstring checked locally. The arxiv, paper-search and github MCP servers failed to connect this session and were not used (they do not cover this stack).

- R1 (pytest). Prepend mode inserts the test module's directory into `sys.path`, not the repo root. `python -m pytest` also adds the cwd; plain `pytest` does not. Consequence: the `sys.path` insertion in section 7 is mandatory. Without `__init__.py` files, test module basenames must be unique.
- R2 (Pydantic v2). `model_copy(update=...)` does not validate updated values and is not recursive (verified: a string was accepted into a `bool` field). Consequence: D11 builds the confirmed student through `model_validate`. `model_dump(mode="json")` is how `shared/store.py` serialises datetimes; engine code does not call it.
- R3 (datetime). Ordering comparison of naive vs aware datetimes raises `TypeError`; `==` is just False. Consequence: D1 converts that `TypeError` to a clear `ValueError`.
- R4 (environment). The local interpreter is Python 3.14.4 with Pydantic 2.14.0; the contract targets 3.11. Use only 3.11-compatible syntax and no dependency beyond stdlib, pydantic and pytest.

## Contract conflicts

C1. **`confirm_retention(student, now)` has no hostel parameter, yet the receipt format is `RET-<hostel>-<6 hex>`.** Resolved without changing the signature: hostel id comes from `shared.store.load_hostel().id` (D11). The cleaner fix is an owner decision (add `hostel_id` to `Student`, or a `hostel_id` argument).

C2. **CONTRACT step 6 lists `RETENTION_NOT_CONFIRMED` / `RETENTION_AFTER_DEADLINE` as waitlist codes only.** On the fixtures only one non-retained returning student is waitlisted, so `RETENTION_NOT_CONFIRMED` would never appear and an unconfirmed student who wins a general bed would get no explanation of why their room was released. D5 attaches the code to every non-retained returning student with a room. Owner approved at Gate 1. Owner may veto at merge.

C3. **"1-based position in tiebreak order" does not say whether the waitlist is one queue or one per pool.** D7 chooses one global queue.

C4. **Retention deadline when confirmation is not required** is unspecified. D4 skips the deadline clause when `retention_requires_confirmation` is false.

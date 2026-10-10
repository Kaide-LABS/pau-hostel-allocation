# PHASE 1 SPEC -- mock, pure helpers, tests (no Streamlit UI yet)

Authority: specs/session-c-prd.md (sections 7, 10.3, 11, 13, 14), CONTRACT.md (sections 3, 4, 5, 9), specs/session-c.md. Where this file and the PRD disagree, the PRD wins. Write only under app/.

## Deliverables

1. `app/__init__.py` (empty).
2. `app/mock.py` per PRD section 13:
   - `HOSTEL`, `STUDENTS` (about 12, invented names), `RULES`, `COMPILE_RESULT` (one ambiguity, one unmapped clause, both quoting sentences of the sample policy), `FIXED_NOW`, `ALLOCATION_RESULT = allocate(HOSTEL, STUDENTS, RULES, FIXED_NOW)`.
   - Every object is built through the shared.models classes.
   - Stubs with the exact CONTRACT section 4 signatures: `allocate(hostel, students, rules, now)`, `confirm_retention(student, now)`, `compile_policy(text)`; plus loaders `load_students()`, `load_hostel()`, `load_default_rules()` returning deep copies.
   - `allocate` is a compact deterministic stand-in for CONTRACT section 5 steps 1-7 with the section 5 explanation templates filled from the run (retain; count; reserve using `reservation_base` and `fresher_reservation_pct`, floor, capped at available beds; freshers into reserved seats ordered by `applied_at`; general pool per `unused_reservation_released`, `freshers_may_compete_for_general_pool`; waitlist with 1-based positions and the correct why-code; room assignment with `PREFERENCE_UNAVAILABLE`). Fill `AllocationSummary` from the run. Same inputs give identical output.
   - The default mock data must produce all nine reason codes: RETAINED_CONFIRMED, RETENTION_NOT_CONFIRMED, RETENTION_AFTER_DEADLINE, FRESHER_RESERVED_SEAT, FRESHER_RESERVATION_FULL, NO_OFFER_LETTER, GENERAL_POOL_ALLOCATED, GENERAL_POOL_FULL, PREFERENCE_UNAVAILABLE, and all three statuses. Demand must exceed supply.
   - Rerunning with `fresher_reservation_pct=30` changes `reserved_for_freshers` and the affected outcomes and explanations.
   - `confirm_retention`: ValueError for non-RETURNING; else a copy with `retention_confirmed=True`, `retention_confirmed_at=now`, `retention_receipt_id="RET-PALM-<6 hex>"` (hex derived from the student id, stable).
   - `compile_policy`: never raises; empty or whitespace text returns default rules, `used_fallback=True`, `error="Policy text is empty."`; otherwise sets `fresher_reservation_pct` from the first `(\d{1,3})\s*%` (clamped 0-100), `source_text` = the input, and returns the ambiguity and unmapped lists.
3. `app/audit.py`: pure functions, no Streamlit import.
   - `check_retention_honoured(result, run_students) -> tuple[bool, str]` and `check_reserved_within_limit(result) -> tuple[bool, str]`, exactly as PRD section 10.3 (recompute the limit from `result.rules` and `summary`; evidence strings with real numbers or failing ids).
4. `app/view.py`: pure helpers, no Streamlit import.
   - `STATUS_STYLE` (allocated/waitlisted/rejected colours from PRD section 11), `status_label(status)`, `rules_rows(rules) -> list[tuple[str, str]]` (plain-language labels and human values per PRD 10.2), `outcomes_dataframe(result, students) -> pandas.DataFrame` with columns Student, Category, Status, Room, Waitlist position, Reason (reason codes joined), `filter_outcomes(df, statuses)`, `status_pill_html(status)` and `tag_html(text)` (escape every dynamic string with `html.escape`), `reserved_sentence(summary, rules)` (the one-line "N of M available beds reserved ..." sentence built only from numbers), `find_placeholders(text) -> list[str]`.
5. `app/test_app.py` containing PRD section 14 tests 1-4 only (the AppTest tests come in phase 2):
   - model round-trip of every mock object; reason-code coverage equals the nine codes and no `{` or `}` in any explanation;
   - audit PASS on the mock result, FAIL on a tampered retained student, FAIL on an extra FRESHER_RESERVED_SEAT beyond the limit;
   - `view.py` colour mapping, rules rows, filter logic;
   - changing pct 40 to 30 through the mock `allocate` lowers `reserved_for_freshers` and both audit checks still pass;
   - CONTRACT section 9 invariants on the mock result: no room over capacity, allocated <= total beds, every student has exactly one outcome with at least one reason code, determinism.

## Out of scope this phase

`app/main.py`, any Streamlit rendering, `app/NEEDS.txt` (phase 2), real-mode imports, edits outside app/.

## Done when

`.venv\Scripts\python.exe -m pytest app -q` passes; `git diff --stat` for the phase touches only files under app/; commits are neutral with no attribution lines.

## Reviewer note

The reviewer must produce `app/.loopr/PHASE_2_SPEC.md`: PRD section 15 phase 2 (app/main.py with the three tabs, the USE_MOCK switch, state, styling, error handling per PRD sections 8-12; AppTest tests 5-6; app/NEEDS.txt), adjusted for anything learned in review.

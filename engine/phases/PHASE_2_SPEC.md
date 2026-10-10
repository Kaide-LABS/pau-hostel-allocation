# PHASE 2: the allocator and the full invariant suite

Inputs to read first (record each in artifacts_read): this file, `specs/session-a-prd.md`, `CONTRACT.md`, `engine/explain.py`, `engine/retention.py`, `tests/test_engine.py` (from phase 1), `shared/models.py`, `shared/store.py`, and `data/*.json`.

Scope: PRD sections 3 (D1-D10), 5, 6 and 7. Phase 1's explain and retention modules are done; reuse `build_explanation` and do not duplicate template text.

## File to add

`engine/allocate.py` with `allocate(hostel: Hostel, students: list[Student], rules: Rules, now: datetime) -> AllocationResult`, implementing CONTRACT section 5 steps 1-7 EXACTLY with the PRD decisions:

- D1 naive datetimes (`TypeError` on comparison → `ValueError`), D2 tiebreak `(applied_at, id)`, D3 integer-only reservation math, D4 retention check, D5 retention-loss code first, D6 reason-code order and per-category codes, D7 one global waitlist queue, D8 summary field definitions, D9 room assignment in `hostel.rooms` order with allocation order retained → reserved-seat freshers → general pool, `PREFERENCE_UNAVAILABLE` only when a preference existed and was unmet, D10 validation errors and input-order outcomes, `run_at = now`, no input mutation.
- Explanation per outcome = `build_explanation(reason_codes, ctx)` with every number taken from the run: `room`, `confirmed_at`, `receipt`, `deadline`, `reserved`, `pct`, `base` (the step 3 numeric base), `base_label` (`"vacated beds"` or `"total beds"`), `general` (the step 5 pool size), `applied_at`, `pos`, `type` (assigned room type).
- Deterministic priority logic only. No OR-Tools, randomness, LLM or I/O. Small private helpers are fine; keep the module readable in one pass.

## Tests to add in `tests/test_engine.py`

All of PRD section 7 items 1-8, 11 and 12, through `shared.store` fixtures and fixed `now` values:

- Section 9 invariants (1-5), including determinism under shuffled input order.
- Item 6 and 7: the 40% run must match PRD section 6 exactly (summary, F01-F05 reserved, F11/F12 rejected, waitlist order F06..F10 then R08 with positions 1-6, R08 codes `RETENTION_AFTER_DEADLINE` + `GENERAL_POOL_FULL`, R02/R06/R14 lead with `RETENTION_NOT_CONFIRMED`). The 30% run: reserved 4, general_allocated 10, R08 ALLOCATED, F05 WAITLISTED, explanation text differs from the 40% run.
- Item 8: union of reason codes over both runs equals all 9 codes.
- Item 11 edge rules on small hand-built hostels, one test each.
- Item 12 validation errors and the mixed-timezone error.
- One test that `allocate` does not mutate its inputs.

## Acceptance

- `.venv\Scripts\python.exe -m pytest tests/test_engine.py -q` passes from the repo root.
- `allocate()` on the fixtures gives a non-empty waitlist and exercises all 9 codes.
- `git diff` touches only `engine/` (not `engine/phases/`) and `tests/test_engine.py`.
- If an expected number in PRD section 6 turns out to be wrong, STOP and report which side is wrong. Do not bend either side.

## Carry-over from phase review

Phase 1 review (explanations + retention) is accepted. Observations the allocator phase must honour:

- **Test result observed:** `.venv\Scripts\python.exe -m pytest tests/test_engine.py -q` → `10 passed` from the repo root. Re-run and keep it green as allocation tests are added below the phase-2 marker.
- **`build_explanation(codes, ctx)` is the one entry point for prose.** `allocate` must construct the `ctx` dict and call it; do not re-template any CONTRACT section 5 wording inside `allocate.py`. The templates and `REASON_CODES` order in `engine/explain.py` are frozen by phase 1 and verified verbatim against CONTRACT section 5.
- **`explain_code` key contract (verified by hand):** a placeholder key that is present but `None` triggers the D12 `RETAINED_CONFIRMED` variant; a key that is *absent* raises `KeyError`. So when building the retained-student `ctx`, pass `confirmed_at=None` explicitly for the "confirmation not required" case (D12) — never omit the key, or the engine will raise instead of producing the variant sentence.
- **`confirm_retention` idempotency is intentional and relied upon:** an already-confirmed student with a receipt is returned unchanged (original timestamp preserved). `allocate`'s step-1 retention check (D4) reads `retention_confirmed` / `retention_confirmed_at` as-is and must not call `confirm_retention` or otherwise re-stamp timestamps.
- **Receipt format** is `RET-{HOSTEL}-{hex6}` matching `^RET-[A-Z0-9]+-[0-9a-f]{6}$`, `HOSTEL` falling back to `"HOSTEL"` on any `load_hostel()` exception. Allocation does not issue receipts; it only surfaces an existing `retention_receipt_id` in the `RETAINED_CONFIRMED` explanation `ctx` as `receipt`.
- **Accepted minor notes (non-blocking, no change required):** `explain_code` reads `ctx["confirmed_at"]` for every `RETAINED_CONFIRMED` call including the normal path; this is correct and is what enforces the absent-key `KeyError`. `_placeholder_names` returns an unordered set, which is harmless because templates use only named fields.
- **Decision the next phase must honour:** reason-code ordering is D6 (retention-loss code → pool outcome → `PREFERENCE_UNAVAILABLE`), and `REASON_CODES` in `explain.py` is the canonical validation set — every outcome's `reason_codes` must be a subset of it, in D6 order.

## Reviewer's own responsibility

This is the last build phase, but it is NOT run as `is_final_phase` (a final phase would have the reviewer commit `BUILD_COMPLETE.md` at the repo root, which is owner territory). Instead the reviewer genuinely writes and commits `engine/phases/PHASE_3_SPEC.md`: a short closing record with the section `## Carry-over from phase review` (observed test result, accepted minor notes, remaining risks) and the line "No further build work in this folder." Commit only that file.

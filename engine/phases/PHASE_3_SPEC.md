# PHASE 3: build closeout (allocation engine)

This is the closing record for the Session A allocation engine. Phases 1 and 2
delivered the full deliverable set defined in `specs/session-a-prd.md` section 2:
`engine/explain.py`, `engine/retention.py`, `engine/allocate.py`, and the complete
invariant suite in `tests/test_engine.py`. The phase-2 architect review defects were
specified as PRD D13 (RETAINED_CONFIRMED variants, no `None` in prose) and D14 (mixed
naive/aware datetimes always surface as `ValueError`), and both are now implemented and
covered by tests.

Inputs read for this review (recorded in artifacts_read): `engine/phases/PHASE_2_SPEC.md`,
`specs/session-a-prd.md`, `CONTRACT.md`, the prior turn's `tests/test_engine.py`,
`engine/allocate.py`, `engine/explain.py`, `engine/retention.py`.

## Scope

No further implementation is scheduled. This phase exists only to record the final
review verdict and hand the engine off for the owner's merge into `main`.

## Acceptance (verified this turn)

- `.venv\Scripts\python.exe -m pytest tests/test_engine.py -q` → **25 passed, 1 warning**
  from the repo root. (The warning is a Windows `.pytest_cache` path race, not a test
  failure.)
- The executor diff under review touches only `engine/allocate.py`, `engine/explain.py`
  and `tests/test_engine.py` — all inside Session A ownership. `shared/` is untouched; no
  LLM, network, randomness or clock read was introduced in `engine/`.
- `allocate()` on the fixtures still gives a non-empty waitlist and exercises all 9 reason
  codes across the 40% and 30% runs (unchanged from phase 2, re-verified by the suite).

## Carry-over from phase review

- **Observed test result:** `25 passed` (phase 1 added 10, phase 2 first dispatch 9, the
  D13/D14 continuation 6 more). Re-run from the repo root with the project `.venv`.
- **D13 verified by hand.** `explain_code("RETAINED_CONFIRMED", ctx)` selects its sentence
  in the exact D13 order: (a) `confirmation_required is False` → the D12 "not required"
  sentence; (b) `confirmed_at is None` → "…Your retention confirmation is on record", with
  " (receipt {receipt})" appended only when `receipt is not None`; (c) `receipt is None` →
  "…You confirmed retention on {confirmed_at}."; (d) otherwise the frozen CONTRACT wording.
  The absent-key `KeyError` contract is preserved: a ctx missing the key a chosen branch
  needs still raises `KeyError` (test at `tests/test_engine.py` covers `{"room": "A101"}`).
  Traced both allocation paths — confirmed-with-no-receipt and confirmed-with-no-time — and
  both produce the expected prose with no `None`.
- **D14 verified by hand.** `_sort_students` wraps the sort `TypeError` into
  `ValueError("mixed naive and timezone-aware datetimes")`, matching the existing wraps in
  `_retained` and `_retention_loss_code`. The new probe (one tz-aware `applied_at` among
  naive transfers) reaches that sort and raises the wrapped error.
- **`ctx` change verified.** `allocate` now always passes the real `retention_confirmed_at`
  and sets `confirmation_required=rules.retention_requires_confirmation`; the old
  "`None`-when-not-required" trick is gone. The `"None" not in explanation` sweep over the
  40%/30% fixture runs and the rule-variant runs guards against regressions.
- **Accepted minor notes (non-blocking, no change required):**
  - The `_RETENTION_NOT_REQUIRED` branch only needs `{room}`, so a D12 ctx that omits
    `confirmed_at` would still format; the engine always supplies `confirmed_at`, so this is
    harmless. Noted only so a future caller does not assume all keys are mandatory.
  - `_placeholder_names` returns an unordered set; harmless because templates use named
    fields only (carried over from phase 1, still true).
- **Remaining risks:** none blocking. The C2 owner veto on attaching
  `RETENTION_NOT_CONFIRMED`/`RETENTION_AFTER_DEADLINE` to non-waitlisted returning students
  (PRD D5) remains an owner call at merge; the implementation follows the Gate-1 approval.
  The D11/C1 hostel-id-via-`load_hostel()` coupling in `confirm_retention` is unchanged and
  already has fallback coverage.

No further build work in this folder.

# PHASE 1: explanations and retention

Inputs to read first (record each in artifacts_read): this file, `specs/session-a-prd.md`, `CONTRACT.md`, plus `shared/models.py`, `shared/store.py` and `specs/session-a.md`.

Scope: PRD sections 3 (D1, D11, D12), 4 and 7 items 9 and 10. `allocate.py` is NOT part of this phase.

## Files to add

1. `engine/__init__.py`: empty.
2. `engine/explain.py`, with exactly this public surface:
   ```python
   REASON_CODES: tuple[str, ...]          # the 9 CONTRACT section 5 codes, in PRD section 6 order
   TEMPLATES: dict[str, str]              # code -> template; CONTRACT section 5 wording VERBATIM
   def fmt_dt(dt: datetime) -> str        # dt.strftime("%d %b %Y %H:%M")
   def explain_code(code: str, ctx: Mapping[str, object]) -> str
   def build_explanation(codes: Sequence[str], ctx: Mapping[str, object]) -> str
   ```
   - `ctx` holds raw values: `room`, `confirmed_at` (datetime or None), `receipt`, `deadline` (datetime), `reserved`, `pct`, `base`, `base_label`, `general`, `applied_at` (datetime), `pos`, `type`. `explain_code` formats any `datetime` through `fmt_dt` and everything else through `str`.
   - Unknown code → `ValueError`. A placeholder missing from `ctx` → `KeyError` (never leave `{...}` in the output).
   - `RETAINED_CONFIRMED` variant (PRD D12): when `ctx["confirmed_at"] is None`, use "You kept room {room}. Retention confirmation was not required under the current rules." Otherwise use the CONTRACT wording.
   - `build_explanation` joins the sentences for `codes`, in order, with one space. Empty `codes` → `ValueError`.
3. `engine/retention.py`: `confirm_retention(student: Student, now: datetime) -> Student` per PRD D11, exactly: `ValueError` if not RETURNING; idempotent for an already confirmed student with a receipt; builds the result with `Student.model_validate({...})` (NOT `model_copy(update=...)`); receipt `RET-{HOSTEL}-{hex6}` where `HOSTEL = load_hostel().id.upper()` (any exception → `"HOSTEL"`) and `hex6 = sha256(f"{student.id}|{now.isoformat()}".encode()).hexdigest()[:6]`; never mutates the input.
4. `tests/test_engine.py`, created in this phase. First lines insert the repo root into `sys.path` (PRD section 7). Tests for this phase:
   - Template exactness: for every one of the 9 codes, build the sentence from a known `ctx` and compare to the full literal CONTRACT sentence with the numbers filled. Include the D12 variant, the datetime format (`02 Jul 2026 10:14` style), unknown code, missing key, empty codes, and multi-code joining order.
   - No `{`/`}` remains in any output.
   - `confirm_retention`: happy path (confirmed true, `confirmed_at == now`, receipt matches `^RET-[A-Z0-9]+-[0-9a-f]{6}$`, input object unchanged); fixture student `R02` (unconfirmed returning) gets receipt prefix `RET-PALM-`; TRANSFER and FRESHER raise `ValueError`; idempotent (an already confirmed fixture student comes back equal, with the original receipt and timestamp); determinism (same inputs → same receipt); different `now` → different receipt.
   - Leave a clearly marked section for phase 2 tests; do not stub failing tests.

## Acceptance

- `.venv\Scripts\python.exe -m pytest tests/test_engine.py -q` passes from the repo root.
- `git diff` of this phase touches only `engine/` (not `engine/phases/`) and `tests/test_engine.py`.
- Commit with a neutral message, no attribution.

## Reviewer's own responsibility

After reviewing, genuinely write and commit the next artifact `engine/phases/PHASE_2_SPEC.md` by adding a `## Carry-over from phase review` section (see `engine/phases/REVIEWER.md`). The base content of that file already exists. Do not rewrite it.

# SESSION C PRD — Streamlit UI (Hostel Allocation Engine)

Produced by the multi-loopr spec phase (loopr brownfield interrogation, all six conditions satisfied, Gate 2 and Gate 1 confirmed by the owner). Hard constraints: CONTRACT.md sections 1, 2, 2a, 3, 4, 7, 9, 10. This PRD adds depth inside `app/` only and changes no model, signature, reason code, algorithm step or demo step.

> Provenance: the interrogation answers (outcome, acceptance criteria, scope edges, soft context) were drafted by Session C from the owner's CONTRACT.md and specs/session-c.md, then the boundary (Gate 2) and the PRD (Gate 1) were confirmed interactively by the owner.

## 1. Outcome

A hostel manager can run room allocation under the university's published policy from one Streamlit app, and Student Affairs can audit it. Students confirm room retention digitally and get a timestamped receipt, and every student sees their outcome and the exact rule that decided it. It must play as a 3-minute live demo (CONTRACT section 10). Session C owns only the UI (`app/`) and calls only `allocate`, `confirm_retention`, `compile_policy` and `shared/store.py`.

## 2. Acceptance criteria (confirmed at Gate 1)

1. `streamlit run app/main.py` starts with `USE_MOCK=1` and with `USE_MOCK=0` and renders three tabs (Student, Hostel manager, Student Affairs audit) with no traceback.
2. Student tab: selecting a RETURNING student and clicking "Confirm I'm keeping my room" displays a receipt id and a timestamp; for a TRANSFER or FRESHER student the confirm button is absent or disabled. "My result" shows status, room or waitlist position, and the explanation sentence.
3. Manager tab: the policy textarea is prefilled with the sample policy; "Compile policy" shows the Rules as a readable table; each ambiguity renders as a yellow warning, each unmapped clause as a red error, and `used_fallback=True` shows a banner.
4. "Run allocation" shows large metrics (total, retained, available, reserved, freshers allocated, general allocated, waitlisted) and an outcomes table filterable by status, coloured green/amber/red for allocated/waitlisted/rejected.
5. Selecting a waitlisted student shows their reason-code explanation containing real numbers, with no unfilled `{placeholders}`.
6. Changing the policy text from 40% to 30%, recompiling and re-running changes `reserved` and the displayed explanations without restarting the app.
7. Audit tab shows a pass or fail line for "every confirmed on-time retention honoured" and "reserved seats within the policy limit", computed from the AllocationResult (and fails visibly on a tampered result in a test).
8. Bad input (empty policy, no student selected, run before compile, engine or compiler raising an exception) yields `st.error` or `st.warning`, never a stack trace; state persists across tab switches via `st.session_state`.
9. `app/mock.py` outcomes cover every section 5 reason code, and its objects validate against `shared/models.py` with `model_validate`.
10. No real student names appear anywhere; `git diff` touches only `app/` and `specs/session-c-prd.md`; `USE_MOCK` defaults to `"1"`.
11. An automated Streamlit AppTest smoke test (`app/test_app.py`) exercising the demo path against mock data passes under pytest.

## 3. Scope edges (confirmed)

Out of scope: edits to `shared/`, `engine/`, `policy/`, `data/` or another worktree; any change to a model, signature, reason code, algorithm step or demo step; allocation, receipt or compilation logic inside the UI; LLM calls from `app/`; database, auth, multi-hostel, concurrency; dependencies beyond streamlit and at most pandas; mobile layout, i18n, PDF/CSV export; pushes after 16:00 (bug fixes only after 15:30). The audit tab is cut first if time runs short and may never delay the demo path.

## 4. Boundary (confirmed at Gate 2)

This build covers the Session C Streamlit UI only, in `app/` (`main.py`, `mock.py`, `NEEDS.txt`, `__init__.py`, `test_app.py`) plus `specs/session-c-prd.md`. Touched surface (read-only): CONTRACT.md, requirements.txt, shared/models.py, shared/store.py, specs/session-c.md.

## 5. Soft context

- Student Affairs' statement says hostels determine their own allocation. Screen wording must present the tool as a fair, auditable way for hostels to do that, never as the university overriding the hostel.
- Explanations come from the engine's templates. The UI shows `StudentOutcome.explanation` verbatim; it never paraphrases it or invents numbers.
- Projector demo in 3 minutes: large metrics, clear status colours, key result visible without scrolling. Reliability beats features.
- Invented student names only, including mock data and screenshots.
- A and B merge at 13:00 and 14:30, so `USE_MOCK` defaults to 1 and the UI must keep working on mock data when the engine or compiler is late or broken.
- Reviewer must be a different provider from the executor (Claude reviews, Codex writes).

## 6. Conformance ledger

- CONFORM `from __future__ import annotations` at the top of every module (used in `shared/models.py`, `shared/store.py` and prescribed by the contract). All app modules start with it.
- No CONFLICT or AMBIGUOUS patterns were found, so Gate 3 never fired.

## 7. Files (all under `app/`)

| File | Purpose |
|---|---|
| `app/__init__.py` | Empty. Makes `app` importable as a package. |
| `app/main.py` | The Streamlit app. `USE_MOCK` switch, state, three tabs, styling. |
| `app/mock.py` | Hand-built section 3 objects and stub `allocate`, `confirm_retention`, `compile_policy`. |
| `app/audit.py` | Pure functions: the two audit checks (no Streamlit import, unit-testable). |
| `app/view.py` | Pure helpers: rules-to-rows, outcome-to-dataframe, status colours (no Streamlit import except where noted). |
| `app/NEEDS.txt` | `streamlit` and `pandas` (the owner merges into requirements.txt). |
| `app/test_app.py` | pytest: model validation of mock, audit checks including tampered results, AppTest demo-path smoke test. |

`main.py` stays thin: widgets and state only. Logic that can be tested without Streamlit lives in `audit.py` and `view.py`.

## 8. Imports and the USE_MOCK switch

`streamlit run app/main.py` puts `app/` (not the repo root) on `sys.path`, so `from shared.models import ...` would fail. `main.py` therefore, before any project import:

```python
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv      # python-dotenv is already in requirements.txt
load_dotenv(ROOT / ".env")
USE_MOCK = os.getenv("USE_MOCK", "1") == "1"
```

- `USE_MOCK` true: `from app import mock` supplies `allocate`, `confirm_retention`, `compile_policy`, and loaders `load_students`, `load_hostel`, `load_default_rules` (mock-backed, same signatures as `shared.store`).
- `USE_MOCK` false: `from engine.allocate import allocate`, `from engine.retention import confirm_retention`, `from policy.compile import compile_policy`, `from shared.store import load_students, load_hostel, load_default_rules, save_result`.
- The real-mode imports are performed inside a `try`. If any import fails, `main.py` shows one `st.error` ("Real engine or compiler not available yet: <module>. Set USE_MOCK=1 or wait for the merge.") and stops rendering the tabs; it never shows a traceback.
- The active mode is shown in a small caption under the subtitle ("Data source: mock" or "Data source: live engine") so a projector audience is never misled.
- The sample policy text is a constant in `main.py`, copied verbatim from CONTRACT section 6.

## 9. State (`st.session_state`)

Initialised once by `init_state()`; keys:

| Key | Type | Meaning |
|---|---|---|
| `hostel` | `Hostel` | Loaded once. |
| `students` | `list[Student]` | Working copy, updated when a student confirms retention. |
| `rules` | `Rules` | Current compiled rules (default rules until compiled). |
| `compile_result` | `CompileResult \| None` | Last compile outcome. |
| `result` | `AllocationResult \| None` | Last allocation. |
| `run_students` | `list[Student]` | Snapshot of `students` taken at the moment of the run (audit input). |
| `policy_text` | `str` | Textarea value (widget key). |
| `selected_student_id` | `str \| None` | Student tab selection. |
| `last_receipt` | `dict` per student id | Receipt id and timestamp shown after a confirm. |
| `flash` | `list` | One-shot messages. |

Data loading errors (`FileNotFoundError`, validation errors) become one `st.error` naming the file ("Could not load students: data/students.json is missing. Session A's fixtures are due first.") and the tabs render in a disabled state.

All widget keys are explicit and stable (for AppTest and for state surviving tab switches). The working `students` list is authoritative; the UI does not call `save_students` (so the tracked fixture `data/students.json` is never dirtied by a demo). After a successful real-mode run the UI may call `save_result`, wrapped so that a failure shows `st.warning`, never `st.error`.

## 10. Layout and interaction

`st.set_page_config(page_title="Hostel Allocation", layout="wide")` is the first Streamlit call. A CSS block injected once through `st.markdown(..., unsafe_allow_html=True)` provides projector styling (see section 11); `.streamlit/config.toml` is outside `app/`, so theming is done in code, not in a config file.

Header: title "Hostel Room Allocation", one-line subtitle "A fair, auditable way for hostels to run allocation under the published policy.", then the data-source caption. Three tabs via `st.tabs(["Student", "Hostel manager", "Student Affairs audit"])`.

### 10.1 Student tab

1. `st.selectbox` of students labelled `"{name} ({category})"`, placeholder "Choose a student". No selection: `st.info("Choose a student to begin.")` and nothing else renders.
2. A small card: name, category, current room (if any), retention state.
3. "Confirm I'm keeping my room":
   - Only rendered enabled for RETURNING students who are not yet confirmed. For TRANSFER or FRESHER the button is disabled with caption "Only current residents confirm retention."; for an already confirmed student the button is replaced by the stored receipt.
   - On click: `confirm_retention(student, now)` inside try/except; on success replace the student in `session_state.students`, then show a green success box with the receipt id and the timestamp (formatted `DD Mon YYYY, HH:MM:SS`). A `ValueError` becomes `st.error(str(e))`; any other exception becomes `st.error("Could not record your confirmation. Please try again.")`.
   - If `rules.retention_deadline` is set and `now` is later, show `st.warning` before the click: "The retention deadline was {deadline}. A confirmation now will be recorded as late." (This is data from the rules, not UI logic.)
4. "My result": if no allocation has run, `st.info("No allocation has been run yet. Ask the hostel manager to run it.")`. Otherwise find the student's `StudentOutcome` and show: a coloured status pill, the room id or "#N on the waitlist", and the explanation verbatim in a bordered box, with each reason code as a small tag. A student missing from the result gets `st.warning("No outcome recorded for this student in the latest run.")`.
5. Note: the result shown is the last run's. If the student's retention changed after the last run, show `st.info("Your confirmation was recorded after the last allocation run. It will count in the next run.")`.

### 10.2 Hostel manager tab

1. Policy: `st.text_area` (key `policy_text`, height ~200) prefilled with the sample policy.
2. "Compile policy" button:
   - Empty or whitespace-only text: `st.warning("Paste the policy text first.")`, no call.
   - Otherwise call `compile_policy(text)` in try/except (the contract says it never raises, the UI still defends). Store `compile_result`; set `rules` to `compile_result.rules`.
   - Banner: if `used_fallback`, `st.warning` banner, bold: "Fallback rules in use: the compiler could not process this policy" plus `error` when present. If `error` is set without fallback, `st.error(error)`.
   - Each `ambiguities` item renders as a yellow box (`st.warning`) prefixed "Could be read more than one way:". Each `unmapped_clauses` item renders as a red box (`st.error`) prefixed "Not mapped to any rule:". Both quote the sentence verbatim.
   - Rules table: a two-column table (Rule, Value) with plain-language labels (e.g. "Share of vacated beds reserved for new students: 40%", "Reservation base: vacated beds", "Offer letter required for reserved seats: Yes", "Retention deadline: ..."), values formatted for humans (Yes/No, dates). A `rules.source_text` expander shows the compiled text. Never show raw JSON as the main view.
3. "Run allocation" button:
   - If no policy was compiled in this session, run with the current `rules` (default rules) and show `st.info("Running with the default rules. Compile a policy to use your own.")` so step 2 of the demo is never blocked.
   - Call `allocate(hostel, students, rules, now)` in try/except (`ValueError` and others become `st.error("Allocation failed: <short message>")`). On success store `result` and `run_students = deepcopy(students)`, and flash `st.success`.
   - Summary: seven large metrics in one row (`st.columns(7)` falling back to two rows below a width the CSS handles): Total beds, Retained, Available, Reserved for new students, New students allocated, General allocated, Waitlisted. Rejected is shown as a smaller eighth item (the contract's summary has it; the spec's list omits it, so it is secondary).
   - Under the metrics, one sentence built only from summary numbers, e.g. "{reserved} of {available} available beds reserved for new students ({pct}% of {base_label})", so the 40% to 30% change is visible at a glance.
   - Outcomes table: columns Student, Category, Status, Room, Waitlist position, Reason. Filter with `st.multiselect("Show", ["Allocated","Waitlisted","Rejected"], default=all)`; the table is a pandas DataFrame, status cells coloured with `Styler.map` (allocated green, waitlisted amber, rejected red), `hide_index=True`, wide.
   - Below the table, "Why did this student get this outcome?": a `st.selectbox` listing the waitlisted students first, then the rest; selecting shows that student's explanation verbatim in the same box style as the Student tab. (Demo step 3.)
4. Re-running after editing the policy replaces `result`, so the metrics and explanations change live (demo step 4). A previous result is never shown beside new rules without a "Results are from the previous run; run again to update." caption when `rules` changed since the run.

### 10.3 Student Affairs audit tab (cut first)

If no result: `st.info("Run an allocation first.")`. Otherwise two lines, each a coloured PASS or FAIL box with one sentence of evidence:

1. "Every confirmed on-time retention was honoured." For each student in `run_students` with category RETURNING and `retention_confirmed` and (no `retention_deadline` or `retention_confirmed_at <= retention_deadline`; or `retention_requires_confirmation` false): the matching outcome must be `ALLOCATED`, `room_id == current_room_id`, and `RETAINED_CONFIRMED` in `reason_codes`. Evidence: "N of N honoured" or the ids that failed.
2. "Reserved seats stayed within the policy limit." `reserved_limit = min(floor(pct/100 * base), available_beds)` recomputed from `result.rules` and `summary` (`base` = `available_beds` or `total_beds` per `reservation_base`). Pass when the count of outcomes with `FRESHER_RESERVED_SEAT` is `<= reserved_limit` and `summary.reserved_for_freshers == reserved_limit`. Evidence: "{used} seats used, limit {limit}".

Both are pure functions in `audit.py` returning `(passed: bool, evidence: str)`. They read only the `AllocationResult`, the `run_students` snapshot and the contract formulas; they never trust `summary` numbers they can recompute.

## 11. Visual polish (projector-ready)

- `layout="wide"`; base font sizes raised via CSS (body 18px, metric value 2.6rem, metric label 1rem).
- Status colours: allocated `#1a7f37` on `#dafbe1`, waitlisted `#9a6700` on `#fff8c5`, rejected `#cf222e` on `#ffebe9`. Text always has a word label as well as colour. Contrast meets WCAG AA.
- Metric cards with a light border and padding; generous spacing between sections; no tab requires scrolling past the fold to see its main result at 1280x720.
- Light theme only; no dark-mode work.
- Pill and tag markup is plain HTML in `st.markdown(unsafe_allow_html=True)` built by `view.py` helpers (escape every dynamic string with `html.escape`).
- Avoid widgets newer than Streamlit 1.36 (`st.badge`, `st.pills`, `border=` on `st.metric`) because `requirements.txt` floors at 1.36.

## 12. Error handling rules

| Situation | Behaviour |
|---|---|
| Fixture file missing or invalid | One `st.error` naming the file; tabs disabled. |
| Real-mode import fails | One `st.error`; app stops rendering tabs; no traceback. |
| Student not selected | `st.info`, no actions. |
| Confirm on non-RETURNING | Disabled button with caption; a forced call surfaces the engine's `ValueError` via `st.error`. |
| Empty policy text | `st.warning`, no compile call. |
| Run before compile | Runs with current rules plus `st.info`. |
| `compile_policy` raises (contract says it never does) | `st.error("Policy compiler failed unexpectedly.")`, previous rules kept. |
| `allocate` raises | `st.error("Allocation failed: ...")`, previous result kept. |
| Result lacks an outcome for a student | `st.warning` on that student, rest unaffected. |
| Placeholder text `{x}` found in an explanation | Rendered as-is plus `st.warning("Explanation contains an unfilled placeholder.")` so A's bug is visible, not hidden. |

A thin wrapper `safe_call(label, fn, *args)` returns `(value, error_message)` and is the only place exceptions are caught. Nothing in `main.py` prints `traceback`, `repr(exception)` or `st.exception`.

## 13. `app/mock.py`

- `HOSTEL`: one invented hostel ("Palmgrove Hall"), about 8 rooms, mixed single/double/quad. Every object is built through the section 3 models (`Model(...)`), so it fails loudly if it ever drifts from `shared/models.py`.
- `STUDENTS`: about 12 invented students (names obviously fictional, e.g. "Student Ada Test"; no real names): RETURNING (confirmed on time, confirmed late, unconfirmed), TRANSFER, FRESHER (with and without offer letter), mixed `applied_at` and `preferred_room_type`.
- `RULES`: `Rules` defaults with a `retention_deadline` set after the on-time confirmation timestamps and before the one late confirmation in `STUDENTS`.
- `COMPILE_RESULT`: the default rules plus exactly one ambiguity and one unmapped clause (both quoting sentences of the sample policy).
- `ALLOCATION_RESULT`: outcomes covering every section 5 reason code at least once: `RETAINED_CONFIRMED`, `RETENTION_NOT_CONFIRMED`, `RETENTION_AFTER_DEADLINE`, `FRESHER_RESERVED_SEAT`, `FRESHER_RESERVATION_FULL`, `NO_OFFER_LETTER`, `GENERAL_POOL_ALLOCATED`, `GENERAL_POOL_FULL`, `PREFERENCE_UNAVAILABLE`. Explanations are the contract's templates with real, consistent numbers (the same numbers as the summary). All three statuses appear.
- Stub functions with the exact section 4 signatures:
  - `allocate(hostel, students, rules, now)`: returns a copy of `ALLOCATION_RESULT` with `rules` replaced by the argument and `run_at=now`; so the demo step "40% to 30%" is demonstrable on mock data, `summary.reserved_for_freshers` is recomputed as `min(floor(pct/100 * base), available_beds)` and the reserved-seat explanation text is regenerated from that number. Retained students stay retained.
  - `confirm_retention(student, now)`: raises `ValueError` if not RETURNING; otherwise returns a copy with `retention_confirmed=True`, `retention_confirmed_at=now`, `retention_receipt_id=f"RET-PALM-{6 hex}"` (hex derived from the student id so it is stable).
  - `compile_policy(text)`: never raises; empty text or whitespace returns default rules with `used_fallback=True` and `error="Policy text is empty."`; otherwise finds the first `(\d{1,3})\s*%` in the text and sets `fresher_reservation_pct` accordingly, returning `COMPILE_RESULT`-style ambiguity and unmapped lists.
  - Loaders `load_students()`, `load_hostel()`, `load_default_rules()` return deep copies.

The mock deliberately contains no allocation algorithm beyond that arithmetic; it exists to exercise the UI.

## 14. Test plan (`app/test_app.py`, pytest, no network)

1. Mock objects validate: `Model.model_validate(obj.model_dump())` round-trips for hostel, students, rules, compile result, allocation result.
2. Reason-code coverage: the set of codes in `ALLOCATION_RESULT` equals the nine section 5 codes; no explanation contains `{` or `}`.
3. Audit unit tests: PASS on the mock result; FAIL when a retained student's outcome is changed to waitlisted; FAIL when a `FRESHER_RESERVED_SEAT` outcome is added beyond the limit.
4. `view.py` unit tests: status colour mapping, rules-to-rows labels, filter logic.
5. AppTest smoke test (`streamlit.testing.v1.AppTest.from_file("app/main.py")` with `USE_MOCK=1`): no exceptions; confirm retention for a RETURNING student shows a receipt; compile then run shows the metrics; change the policy to 30%, recompile, rerun, and assert `reserved` changed; run an empty-policy compile and assert a warning, not an exception; audit tab shows two PASS lines.
6. A grep-style test: no file under `app/` contains `st.exception`, `traceback`, or an import of `anthropic`/`openai`.

The AppTest sets `sys.path` to the repo root itself; `main.py` already does. Real-mode (`USE_MOCK=0`) is verified manually at the 14:30 checkpoint, not by CI-style tests (A and B may not exist in this worktree).

## 15. Build phases (dispatched through multi-loopr: Codex executes, Claude reviews)

1. Phase 1: `app/__init__.py`, `app/mock.py`, `app/view.py`, `app/audit.py`, tests 1 to 4. Checkpoint 13:00 items 1.
2. Phase 2: `app/main.py` with the three tabs, the `USE_MOCK` switch, state, styling and error handling; test 5 and 6; `app/NEEDS.txt`. Checkpoint 13:00 items 2 and 3.
3. Phase 3 (14:30 checkpoint, after A and B merge): `git fetch origin && git rebase origin/main`; run with `USE_MOCK=0`; integration fixes inside `app/` only.

Each phase: Codex implements, Claude reviews the diff with this PRD, CONTRACT.md and specs/session-c.md only (never the conversation), findings fixed, then commit. The loopr evidence check runs after the last phase.

## Research notes

Checked against the Streamlit docs (docs.streamlit.io) and the installed Streamlit 1.65 (`requirements.txt` floors at 1.36):

- Testing: `AppTest.from_file(...)` exposes `at.tabs`, `at.button`, `at.session_state`; widgets are driven with `.click().run()` (an explicit `run()` is needed after every interaction). Button state cannot be preset through `session_state`, so tests click buttons. Prefer explicit widget `key=`s and look widgets up by key (`at.button(key=...)`).
- Dataframes: `st.dataframe` accepts a pandas Styler (cell colours and font weight work; bars, hover and captions do not). `column_config` formatting wins over Styler formatting. Do not enable the newer `lazy` mode, which does not support Styler.
- Theming: `.streamlit/config.toml` must live in the repo root (or `~/.streamlit/`), outside `app/`, so theming is done with injected CSS in `main.py`. The browser's saved theme choice can override a config file anyway.
- Imports: `streamlit run app/main.py` puts the script's own folder (`app/`) at `sys.path[0]`, not the repo root (confirmed by running a probe script), so `main.py` inserts the repo root itself (section 8).
- Session state: widget-backed keys persist across tab switches within a session; tab selection itself is client-side, so switching tabs does not rerun the script by default.

## Contract conflicts

None blocking. Observations for the owner (no workaround was built):

1. `confirm_retention(student, now)` has no hostel argument but the receipt format is `RET-<hostel>-<6 hex>`. Session A must derive the hostel part itself (for example from a constant or by loading the hostel). The UI shows whatever receipt id is returned.
2. Demo hazard: if `default_rules.json`'s `retention_deadline` is earlier than the wall-clock time of the demo, a live confirmation made on stage is "late" and the student would get `RETENTION_AFTER_DEADLINE` on the next run. The UI warns before the click (section 10.1) but does not fake the clock. The owner should set the fixture deadline in the future of the demo date, or accept the late-confirmation path as the demo story.
3. `save_students` would write the tracked fixture `data/students.json` on every demo confirmation. The UI therefore keeps confirmations in `st.session_state` only and does not call `save_students`. If the owner wants confirmations to persist across app restarts, `data/` needs a separate working copy (an owner or Session A decision).
4. CONTRACT section 7 lists seven metrics; the section 3 summary also has `rejected`. It is shown as a secondary metric, which does not change any model.
5. specs/session-c.md says the build should start by 12:05; the spec phase ran past that (interrogation finished about 12:12). No contract change is needed; this is noted for the timeline only.

# PHASE 2 SPEC -- the Streamlit app (main.py, NEEDS.txt, AppTest smoke tests)

Authority: specs/session-c-prd.md (sections 7, 8, 9, 10, 11, 12, 14), CONTRACT.md (sections 7, 9, 10), specs/session-c.md. Where this file and the PRD disagree, the PRD wins. Write only under app/. Phase 1 (`app/mock.py`, `app/view.py`, `app/audit.py`, `app/__init__.py`, `app/test_app.py` tests 1-4 plus hardening) is done and committed; do not rewrite it. `main.py` stays thin -- all logic that can be unit-tested lives in `view.py`/`audit.py`/`mock.py` already. Add new pure helpers there (not in `main.py`) if a tab needs logic, and cover them with a unit test.

## Deliverables

1. `app/NEEDS.txt`: exactly the two new packages, one per line, lowercase: `streamlit` and `pandas`. No versions, no comments. (`python-dotenv` is already in the owner's requirements.txt per PRD section 8, so it is NOT listed here.)

2. `app/main.py` per PRD sections 8-12. Structure, in order:
   - `from __future__ import annotations` first line, then the sys.path bootstrap EXACTLY as PRD section 8: insert repo root, `load_dotenv(ROOT / ".env")`, `USE_MOCK = os.getenv("USE_MOCK", "1") == "1"`. All project imports come after this block.
   - `USE_MOCK` true: `from app import mock` and bind `allocate, confirm_retention, compile_policy, load_students, load_hostel, load_default_rules` from it. False: the real-mode imports (`engine.allocate.allocate`, `engine.retention.confirm_retention`, `policy.compile.compile_policy`, `shared.store.load_students/load_hostel/load_default_rules/save_result`) performed inside a single `try`; on `ImportError` set a module-level flag/message and later render one `st.error` ("Real engine or compiler not available yet: <module>. Set USE_MOCK=1 or wait for the merge.") then `st.stop()` -- never a traceback. `save_result` only exists in real mode; guard its use.
   - `SAMPLE_POLICY`: the CONTRACT section 6 sample policy text verbatim as a module constant (reuse the exact wording; it already exists as `mock.SAMPLE_POLICY`, but `main.py` must not depend on mock in real mode, so define it locally).
   - `safe_call(label, fn, *args) -> tuple[value | None, str | None]`: the ONLY place exceptions are caught; returns `(value, None)` or `(None, message)`. Nothing in `main.py` calls `traceback`, `repr(exc)`, or `st.exception`.
   - `NOW` provider: a single module-level `now()` returning a timezone-aware UTC datetime, used for `confirm_retention` and `allocate`. (AppTest determinism does not depend on it; do not freeze it, but keep it to one call site so a future fixed-clock swap is trivial.)
   - `init_state()`: initialise every `st.session_state` key from PRD section 9 exactly (`hostel`, `students`, `rules`, `compile_result`, `result`, `run_students`, `policy_text`, `selected_student_id`, `last_receipt`, `flash`), loading hostel/students/rules once through the bound loaders inside `safe_call`; a load failure sets a one-line `st.error` naming the file and renders tabs disabled. Guard so it runs once per session.
   - `st.set_page_config(page_title="Hostel Allocation", layout="wide")` as the FIRST Streamlit call; then inject the PRD section 11 CSS once via `st.markdown(..., unsafe_allow_html=True)`.
   - Header: title "Hostel Room Allocation", subtitle "A fair, auditable way for hostels to run allocation under the published policy.", then the data-source caption ("Data source: mock" or "Data source: live engine").
   - `st.tabs(["Student", "Hostel manager", "Student Affairs audit"])` and the three tab bodies exactly per PRD 10.1 / 10.2 / 10.3. Every widget has an explicit, stable `key=` (needed for AppTest and for state surviving tab switches).

3. Tab behaviours (implement the PRD subsections literally; the acceptance-critical points):
   - Student (10.1): selectbox labelled `"{name} ({category})"` with placeholder; info prompt when nothing selected; a card; "Confirm I'm keeping my room" enabled ONLY for RETURNING not-yet-confirmed (disabled with the caption for TRANSFER/FRESHER, replaced by the stored receipt when already confirmed); on click call `confirm_retention` via `safe_call`, replace the student in `session_state.students`, store `last_receipt[id]`, show a green success box with receipt id and timestamp formatted `DD Mon YYYY, HH:MM:SS`; `ValueError` -> `st.error(str(e))`, other -> the generic message; the pre-click late-deadline `st.warning` when `rules.retention_deadline` is set and `now()` is later; "My result" per 10.1 step 4-5 using `view.status_pill_html`, the explanation verbatim in a bordered box, each reason code via `view.tag_html`, and `find_placeholders` driving the "unfilled placeholder" warning (PRD 12).
   - Hostel manager (10.2): `st.text_area` key `policy_text` prefilled with `SAMPLE_POLICY`; "Compile policy" -> empty/whitespace gives `st.warning("Paste the policy text first.")` with no call, else `compile_policy` via `safe_call`, store `compile_result`, set `rules`, render the fallback/error banners, each ambiguity as `st.warning` prefixed "Could be read more than one way:", each unmapped clause as `st.error` prefixed "Not mapped to any rule:", then the Rule/Value table from `view.rules_rows` with a `source_text` expander (never raw JSON as the main view); "Run allocation" -> run with current rules (info note if none compiled this session) via `safe_call`, store `result` and `run_students = deepcopy(students)`, seven `st.metric`s in `st.columns(7)` (Rejected as a smaller eighth item), the one-line `view.reserved_sentence`, the outcomes table from `view.outcomes_dataframe` filtered by `view.filter_outcomes` with an `st.multiselect` (default all three) and a pandas `Styler.map` colouring the Status cell green/amber/red, `hide_index=True`, wide; the "Why did this student get this outcome?" selectbox (waitlisted first) showing the explanation verbatim. Show the "Results are from the previous run; run again to update." caption when `rules` changed since the run.
   - Student Affairs audit (10.3): `st.info("Run an allocation first.")` when no result, else two coloured PASS/FAIL boxes from `audit.check_retention_honoured(result, run_students)` and `audit.check_reserved_within_limit(result)`, each with its evidence sentence.

4. `app/test_app.py` additions -- PRD section 14 tests 5 and 6 (append; keep tests 1-4 and the phase-1 hardening tests unchanged):
   - Test 5 (AppTest smoke, `streamlit.testing.v1.AppTest.from_file("app/main.py")` with `USE_MOCK=1` forced via `monkeypatch.setenv` before construction): runs with no uncaught exception (`at.exception` empty after each `.run()`); confirming retention for a RETURNING student surfaces a receipt (locate the button by key, `.click().run()`, assert the receipt string appears in `at.session_state.last_receipt` or a success element); compile then run shows the metrics (assert `at.metric` present / `session_state.result is not None`); change `policy_text` to a 30% policy, recompile, rerun, assert `session_state.result.summary.reserved_for_freshers` dropped versus the 40% run; an empty-policy compile yields a warning and no exception; the audit tab shows two PASS lines. Drive widgets by `key=`; call `.run()` after every interaction.
   - Test 6 (grep-style): no file under `app/` contains `st.exception`, `traceback`, or an import of `anthropic`/`openai` (walk `app/*.py`, read text, assert).

## Hardening checklist (second executor turn; add a test or guard for each not already covered)

- AppTest with an invalid `USE_MOCK` env ("0" without the engine present): asserts exactly one `st.error` and no traceback (`at.exception` empty). If the real packages happen to be importable in the worktree, skip rather than fail.
- Confirm-retention on a TRANSFER/FRESHER through the UI path is unreachable (button disabled); assert the button's `disabled` is True for those selections.
- Run-before-compile shows the info note and still produces a result (assert both).
- Selecting a waitlisted student in "My result" and in the manager explanation box shows a reason string with real digits and no `{`/`}` (reuse `find_placeholders`).
- Re-running after a 40->30 edit changes the `reserved_sentence` text (assert the "30% of" substring appears, "40% of" gone).
- `safe_call` returns the message (not the exception) when `fn` raises, and the generic message path never leaks `str(exc)` for a non-`ValueError`.
- Tab switch persistence: set `selected_student_id`, run, assert it survives a second `.run()`.

## Out of scope this phase

Phase 3 integration (`USE_MOCK=0` against the real engine/compiler, the 14:30 rebase), `.streamlit/config.toml` (lives at repo root, not ours), any edit outside `app/`, any change to a model, signature, reason code, algorithm step or demo step, LLM calls from `app/`, `save_students` (never called -- PRD section 9), CSV/PDF export, mobile/i18n/dark-mode.

## Done when

`.venv\Scripts\python.exe -m pytest app -q` passes (tests 1-6 plus hardening); `git diff --stat` for the phase touches only files under `app/`; `streamlit run app/main.py` starts with `USE_MOCK=1` and renders three tabs with no traceback; commits are neutral with no attribution lines.

## Notes carried from phase 1 review

- Phase 1 is green at 13 passing tests; mock allocation, the two audit checks and the `view.py` helpers are stable and match the CONTRACT section 5 templates word for word. `main.py` must show `StudentOutcome.explanation` verbatim and never recompute or paraphrase a number.
- `view.py` already provides `status_pill_html`, `tag_html` (both `html.escape` every dynamic string), `reserved_sentence`, `rules_rows`, `outcomes_dataframe`, `filter_outcomes`, `find_placeholders`, `STATUS_STYLE`, `status_label`. Use these; do not duplicate their logic in `main.py`.
- `mock.allocate` recomputes for ANY rules, so the 40->30 live change works without a canned result; the manager tab must pass the current `session_state.rules` into `allocate`, not a constant.
- Avoid Streamlit widgets newer than 1.36 (`st.badge`, `st.pills`, `border=` on `st.metric`); the pill/tag markup goes through `st.markdown(unsafe_allow_html=True)` with the `view.py` helpers.

## Reviewer note

The phase 2 reviewer runs `pytest app -q`, confirms the AppTest smoke test actually drives the demo path (not a stub that asserts nothing), checks `git diff --stat` touches only `app/`, and confirms no traceback path exists. If phase 2 completes the demo, the reviewer writes `app/.loopr/PHASE_3_SPEC.md` covering PRD section 15 phase 3 (the 14:30 `git fetch origin && git rebase origin/main`, `USE_MOCK=0` real-mode run, and integration fixes confined to `app/`), committed in that turn.

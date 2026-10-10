# BUILD COMPLETE — Session B policy compiler (`compile_policy`)

Completion record for multi-loopr run `a358ea60-dcfe-4959-897e-75d1849ac793`, phase 1
(the only phase). Produced by the reviewer turn after verifying the executor's diff against
`CONTRACT.md` (sections 1, 2, 2a, 3, 4, 6, 9, 10), `specs/session-b.md`,
`specs/session-b-prd.md`, `policy/loopr/baby_prd.md` and `policy/loopr/context.md`.

## Verdict

**clean.** The build satisfies the PRD and every hard contract constraint in scope. All
offline tests pass. One non-blocking defensive observation is recorded below; it is not a
spec violation and does not gate completion.

## Evidence

- `.venv/Scripts/python -m pytest tests/test_policy.py -q` → **40 passed in 5.73s**
  (reviewer ran it this turn; matches the executor's reported 40 passed).
- `git diff --name-only main...HEAD` touches only: `policy/__init__.py`, `policy/compile.py`,
  `policy/prompts.py`, `policy/smoke.py`, `policy/NEEDS.txt`, `policy/AUDIT.md`,
  `policy/loopr/baby_prd.md`, `policy/loopr/context.md`, `tests/test_policy.py`,
  `specs/session-b-prd.md`. No edits to `shared/`, `data/`, `engine/`, `app/`,
  `requirements.txt`, `README.md`, `CONTRACT.md` or `.gitignore`.
- No commit message on the branch carries an AI-attribution or co-author trailer.
- No secret is committed; `.env` is never read into `os.environ` and never printed.

## Requirement verification (CONTRACT §6 / PRD §3)

| Requirement | Status | Trace |
|---|---|---|
| `compile_policy` never raises on any path (non-str, empty, over-length, no key, SDK error, `load_default_rules` raising, fallback build failure) | PASS | outer `except Exception` `policy/compile.py:39-42`; `_fallback` nested guard `:224-242`; `_safe_default_rules` `:217-221`; sweep `tests/test_policy.py:350-373` |
| Exactly one `messages.create` per attempt; `max_tokens=1024`; no `temperature`/`top_p`/`top_k`; single `emit_rules` tool; `tool_choice={"type":"tool","name":"emit_rules"}`; only the `tool_use` block is read, never free text | PASS | `_call_model` `:115-132`; `test_call_shape_and_model:121-139` |
| `emit_rules` input schema's `rules` equals `Rules.model_json_schema()` built at call time | PASS | `_emit_rules_tool` `:135-148`; asserted `tests/test_policy.py:136` |
| One retry on invalid output with the rejected-output message appended; second invalid → `_fallback` with `used_fallback=True` and `error` set | PASS | `_compile:59-70`; `build_retry_message` `policy/prompts.py:44-51`; `test_invalid_output_then_valid_retries_once:148-162`, `test_invalid_then_invalid_falls_back:165-179` |
| API/network/auth errors are not retried; `_make_client` not constructed when no key; key redacted from `error` | PASS | API catch `:67-70`, `_api_error:245-249`, `_api_exceptions:252-260`; key guard `:50-52`; `test_api_exception_falls_back_without_retry_and_redacts_key:295-304` |
| `source_text` forced to equal the input; unmapped/ambiguous entries kept verbatim (whitespace-collapsed substring, else Jaccard≥0.6 snap, else invalid); de-dupe preserves order | PASS | `_validate_payload:151-164`, `_coerce_clause_list:167-184`, `_snap_to_source:187-201`; `test_unmapped_clause_preserved_and_whitespace_snapped:217-229`, `test_unsalvageable_unmapped_clause_is_invalid:232-244` |
| "Up to X%" → `fresher_reservation_pct = X`; ambiguous wording keeps the default and is listed | PASS | prompt field guide `policy/prompts.py:22-34`; `test_ambiguity_preserves_default:247-266` |
| Default-merge: model `rules` merged over `load_default_rules()` before `Rules.model_validate` | PASS | `_validate_payload:157-160`; `test_omitted_fields_merge_from_defaults:269-276` |
| Only the Anthropic SDK; no other LLM provider; no real network in pytest | PASS | `policy/compile.py:8-11`; `offline` fixture blocks `socket.connect` and the client factory `tests/test_policy.py:58-72` |

## Acceptance criteria (baby PRD)

1. Offline, no-key, mocked client — `pytest tests/test_policy.py` passes. **Met** (40 passed).
2. Sample policy → 40 / `vacated_beds` / offer-letter / retention; 30% variant → 30. **Met**
   (`test_sample_policy_compiles_expected_rules`, `test_thirty_percent_variant`).
3. Invalid output → one retry with error appended; second failure → defaults + fallback. **Met**.
4. Missing key → immediate fallback, no client call; empty/garbage never raise. **Met**.
5. Unmapped sentence verbatim; ambiguous sentence keeps default and is listed. **Met**.
6. One call per attempt, no sampling params, `max_tokens<=1024`, single `emit_rules`, forced
   `tool_choice`. **Met**.
7. `python policy/smoke.py` real-call check: **not run this turn** (reviewer turn is offline and
   isolated; no key). Remains an owner/executor manual step per PRD §8. Offline criteria 1–6 and
   8 are fully met.
8. multi-loopr evidence check — scope and commit-hygiene satisfied; final determination is
   multi-loopr's own.

## Non-blocking observation

- Key redaction is applied in the API-error path (`_api_error`), which is the realistic leak
  vector since the SDK surfaces network/auth failures as `anthropic.APIError`. The outer
  catch-all (`:42`) and the validation-fallback messages do not re-run redaction; no in-scope
  path routes the key through them, so this is defense-in-depth only, not a defect. If the owner
  wants belt-and-suspenders, redact in `_fallback` as well. No code change is required to pass.

## Out-of-scope confirmed untouched

Other LLM providers; free-text parsing; streaming; multi-call/agentic compilation; new `Rules`
fields; caching/persistence; OR-Tools; real network in pytest; `shared/`, `data/`, `engine/`,
`app/`. None were introduced.

## Status

Phase 1 of 1 is complete. The policy compiler is built, reviewed, and green offline. The only
remaining action outside this turn is the one-time real-key smoke run (PRD §8), which the
reviewer turn cannot and should not perform.

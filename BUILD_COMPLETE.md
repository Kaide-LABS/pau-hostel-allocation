# BUILD COMPLETE — Session B policy compiler (`compile_policy`)

Completion record for multi-loopr run `fc72c513-69da-44fc-81fe-da32e83f4fdb`, phase 1
(the only phase). Produced by the reviewer turn after independently verifying the executor's
diff against `CONTRACT.md` (sections 1, 2, 2a, 3, 4, 6, 9, 10), `specs/session-b.md`,
`specs/session-b-prd.md`, `policy/loopr/baby_prd.md` and `policy/loopr/context.md`. This turn
reviewed the round-2 prompt fix (unmapped-clause invariant, retention-confirmation guidance,
a second worked example) plus its three new offline tests.

## Verdict

**clean.** The build satisfies the PRD and every hard contract constraint in scope. All
offline tests pass. Two non-blocking observations are recorded below; neither is a spec
violation and neither gates completion.

## Evidence

- `.venv/Scripts/python -m pytest tests/test_policy.py -q` → **43 passed in 4.65s**
  (reviewer ran it this turn; matches the executor's reported 43 passed and the final line
  recorded in `policy/AUDIT.md`).
- `git diff --name-only main...HEAD` touches only: `BUILD_COMPLETE.md`, `policy/__init__.py`,
  `policy/compile.py`, `policy/prompts.py`, `policy/smoke.py`, `policy/NEEDS.txt`,
  `policy/AUDIT.md`, `policy/loopr/baby_prd.md`, `policy/loopr/context.md`,
  `tests/test_policy.py`, `specs/session-b-prd.md`. No edits to `shared/`, `data/`, `engine/`,
  `app/`, `requirements.txt`, `README.md`, `CONTRACT.md` or `.gitignore`.
- No commit message on the branch carries an AI-attribution or co-author trailer.
- No secret is committed; `.env` is never read into `os.environ` and never printed.

## Requirement verification (CONTRACT §6 / PRD §3)

| Requirement | Status | Trace |
|---|---|---|
| `compile_policy` never raises on any path (non-str, empty, over-length, no key, SDK error, `load_default_rules` raising, fallback build failure) | PASS | outer `except Exception` `policy/compile.py:39-42`; `_fallback` nested guard `:224-242`; `_safe_default_rules` `:217-221`; sweep `tests/test_policy.py:374-397` |
| Exactly one `messages.create` per attempt; `max_tokens=1024`; no `temperature`/`top_p`/`top_k`; single `emit_rules` tool; `tool_choice={"type":"tool","name":"emit_rules"}`; only the `tool_use` block is read, never free text | PASS | `_call_model` `:115-132`; `test_call_shape_and_model:121-139` |
| `emit_rules` input schema's `rules` equals `Rules.model_json_schema()` built at call time | PASS | `_emit_rules_tool` `:135-148`; asserted `tests/test_policy.py:136` |
| One retry on invalid output with the rejected-output message appended; second invalid → `_fallback` with `used_fallback=True` and `error` set | PASS | `_compile:59-70`; `build_retry_message` `policy/prompts.py:51-58`; `test_invalid_output_then_valid_retries_once:172-186`, `test_invalid_then_invalid_falls_back:189-203` |
| API/network/auth errors are not retried; `_make_client` not constructed when no key; key redacted from `error` | PASS | API catch `:67-70`, `_api_error:245-249`, `_api_exceptions:252-260`; key guard `:50-52`; `test_api_exception_falls_back_without_retry_and_redacts_key:319-328` |
| `source_text` forced to equal the input; unmapped/ambiguous entries kept verbatim (whitespace-collapsed substring, else Jaccard≥0.6 snap, else invalid); de-dupe preserves order | PASS | `_validate_payload:151-164`, `_coerce_clause_list:167-184`, `_snap_to_source:187-201`; `test_unmapped_clause_preserved_and_whitespace_snapped:241-253`, `test_unsalvageable_unmapped_clause_is_invalid:256-268` |
| "Up to X%" → `fresher_reservation_pct = X`; ambiguous wording keeps the default and is listed | PASS | prompt field guide `policy/prompts.py:22-41`; `test_ambiguity_preserves_default:271-290` |
| Default-merge: model `rules` merged over `load_default_rules()` before `Rules.model_validate` | PASS | `_validate_payload:157-160`; `test_omitted_fields_merge_from_defaults:293-300` |
| Only the Anthropic SDK; no other LLM provider; no real network in pytest | PASS | `policy/compile.py:8-11`; `offline` fixture blocks `socket.connect` and the client factory `tests/test_policy.py:58-72` |

## Round-2 prompt fix verification

| Requirement | Status | Trace |
|---|---|---|
| Invariant: a sentence is unmapped ONLY if it sets/implies no `Rules` field; confirming a default still counts as mapping | PASS | `policy/prompts.py:33-34`; `test_system_prompt_contains_unmapped_invariant_and_retention_guidance:148-154` |
| Retention guidance: confirmation wording sets `retention_requires_confirmation=true`; false only for automatic retention without confirmation | PASS | `policy/prompts.py:26-27`; `test_system_prompt_contains_unmapped_invariant_and_retention_guidance:148-154` |
| Second worked example (one mapped, one genuinely unmapped visiting-hours sentence, one ambiguous) added without removing the required general-pool ambiguity example | PASS | `policy/prompts.py:36-41`; `test_system_prompt_contains_worked_example_unmapped_sentence:157-160` |
| `SAMPLE_POLICY` unchanged and exactly equal to CONTRACT §6 | PASS | `policy/prompts.py:7-12`; `test_sample_policy_text_is_exact:163-169` |

## Acceptance criteria (baby PRD)

1. Offline, no-key, mocked client — `pytest tests/test_policy.py` passes. **Met** (43 passed).
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

## Non-blocking observations

- **Key redaction scope.** Redaction runs in the API-error path (`_api_error`), the realistic
  leak vector since the SDK surfaces network/auth failures as `anthropic.APIError`. The outer
  catch-all (`:42`) and the validation-fallback messages do not re-run redaction; no in-scope
  path routes the key through them, so this is defense-in-depth only, not a defect. Optional:
  redact in `_fallback` too. No code change required to pass.
- **Process artifacts outside the §2 file list.** `policy/AUDIT.md` sits under Session B's owned
  `policy/` folder (CONTRACT §2) but is not among the files PRD §2 enumerates; `BUILD_COMPLETE.md`
  lives at the repo root, outside Session B's owned paths. Both are multi-loopr-mandated process
  artifacts required by the dispatch instructions, not product code, and neither touches another
  session's folder or a shared/frozen file. Recorded for transparency; not a build spec violation.

## Out-of-scope confirmed untouched

Other LLM providers; free-text parsing; streaming; multi-call/agentic compilation; new `Rules`
fields; caching/persistence; OR-Tools; real network in pytest; `shared/`, `data/`, `engine/`,
`app/`. None were introduced.

## Status

Phase 1 of 1 is complete. The policy compiler is built, reviewed, and green offline (43 passed).
The only remaining action outside this turn is the one-time real-key smoke run (PRD §8), which the
reviewer turn cannot and should not perform.

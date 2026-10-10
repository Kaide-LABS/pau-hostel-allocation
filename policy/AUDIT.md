# Policy Compiler Traceability Audit

Final pytest result: `50 passed, 1 warning in 10.34s`

## PRD Section 3 Behaviours

| PRD item | Code trace | Test trace |
|---|---|---|
| 3.1 outer wrapper never raises, fallback is defensive | `policy/compile.py` `compile_policy` lines 37-42; `_fallback` lines 224-242; `_safe_default_rules` lines 217-221 | `test_generic_exception_never_raises` lines 324-328; `test_load_default_rules_raising_still_falls_back` lines 331-335; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.2 input guards for non-str, empty, whitespace, too long | `policy/compile.py` `_compile` lines 45-48; `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.3 API key from env or `.env`, no key fallback before client | `policy/compile.py` `_compile` lines 50-52; `_load_api_key` lines 104-112; `_DOTENV_PATH` line 32 | `offline` fixture lines 58-72; `test_missing_key_falls_back_without_client` lines 182-186 |
| 3.4 client factory uses Anthropic with no retries and timeout | `policy/compile.py` `_make_client` lines 81-84 | `offline` fixture monkeypatches factory lines 64-67; `install_fake` lines 75-79 |
| 3.5 model env var default | `policy/compile.py` `_DEFAULT_MODEL` line 33; `_call_model` line 117 | `test_call_shape_and_model` lines 121-139; `test_default_model_when_unset` lines 142-145 |
| 3.6 one call per attempt, max_tokens 1024, forced tool, no sampling params | `policy/compile.py` `_call_model` lines 115-123 | `test_call_shape_and_model` lines 121-139; `test_invalid_output_then_valid_retries_once` lines 172-186 |
| 3.7 emit_rules schema built from `Rules.model_json_schema()` at call time | `policy/compile.py` `_emit_rules_tool` lines 135-148 | `test_call_shape_and_model` lines 133-137 |
| 3.8 read first matching tool_use only; text-only/truncated invalid | `policy/compile.py` `_call_model` lines 124-132 | `test_invalid_output_forms_retry_then_fallback` lines 279-292; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.9 validation, null-drop/default merge, source_text forcing, verbatim snap/dedupe | `policy/compile.py` `_validate_payload` lines 151-165; `_coerce_clause_list` lines 168-185; `_snap_to_source` lines 188-202; `_sentences` lines 205-207; `_tokens` lines 210-211; `_normalise` lines 214-215; `_drop_null_values` lines 218-219 | `test_omitted_fields_merge_from_defaults` lines 303-310; `test_null_retention_deadline_keeps_default` lines 313-322; `test_non_null_retention_deadline_is_preserved` lines 325-335; `test_unmapped_clause_preserved_and_whitespace_snapped` lines 251-263; `test_unsalvageable_unmapped_clause_is_invalid` lines 266-278; `test_ambiguity_preserves_default` lines 281-300 |
| 3.10 exactly one retry with rejection message, then fallback | `policy/compile.py` `_compile` lines 59-70; `policy/prompts.py` `build_retry_message` lines 51-58 | `test_invalid_output_then_valid_retries_once` lines 172-186; `test_invalid_then_invalid_falls_back` lines 189-203 |
| 3.11 API exceptions are not retried and key is redacted | `policy/compile.py` `_compile` lines 67-70; `_api_error` lines 245-249; `_api_exceptions` lines 252-260 | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 295-304; `test_anthropic_auth_error_falls_back_without_retry` lines 307-321 |
| 3.12 success returns `CompileResult` without fallback/error | `policy/compile.py` `_compile` lines 72-78 | `test_sample_policy_compiles_expected_rules` lines 82-108; `test_thirty_percent_variant` lines 111-118 |
| 3.13 fallback uses default rules, source_text, empty clause lists, truncated error | `policy/compile.py` `_fallback` lines 224-242 | `test_invalid_then_invalid_falls_back` lines 165-179; `test_missing_key_falls_back_without_client` lines 182-186; `test_load_default_rules_raising_still_falls_back` lines 331-335 |

## PRD Section 6 Edge Cases

| Edge case | Code trace | Test trace |
|---|---|---|
| Empty string | `policy/compile.py` `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| Whitespace only | `policy/compile.py` `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| `None` | `policy/compile.py` `_input_guard` lines 94-101; `_fallback` lines 224-242 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| `bytes` | `policy/compile.py` `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| `int` | `policy/compile.py` `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 20,001-character text | `policy/compile.py` `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 10,000 characters of garbage | `policy/compile.py` `_coerce_clause_list` lines 167-184 | `test_ten_thousand_character_garbage_never_raises` lines 196-204; `test_compile_policy_never_raises_sweep` lines 350-373 |
| Prompt-injection line remains data in policy tags | `policy/prompts.py` `build_system_prompt` lines 18-20; `build_user_message` lines 50-51 | `test_prompt_injection_remains_inside_policy_tags` lines 397-406 |
| Percentage out of range from model | `policy/compile.py` `_validate_payload` lines 151-165 | `test_invalid_output_then_valid_retries_once` lines 182-196; `test_invalid_output_forms_retry_then_fallback` lines 338-351 |
| Model returns text only | `policy/compile.py` `_call_model` lines 126-132 | `test_invalid_output_forms_retry_then_fallback` lines 338-351; `test_compile_policy_never_raises_sweep` lines 409-432 |
| `stop_reason == "max_tokens"` | `policy/compile.py` `_call_model` lines 124-125 | `test_invalid_output_forms_retry_then_fallback` lines 338-351; `test_compile_policy_never_raises_sweep` lines 409-432 |
| `rules` is a string | `policy/compile.py` `_validate_payload` lines 151-154 | `test_invalid_output_forms_retry_then_fallback` lines 338-351; `test_compile_policy_never_raises_sweep` lines 409-432 |
| Clause altered whitespace or minor paraphrase snaps, unsalvageable invalid | `policy/compile.py` `_coerce_clause_list` lines 168-185; `_snap_to_source` lines 188-202 | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 251-263; `test_unsalvageable_unmapped_clause_is_invalid` lines 266-278 |
| Duplicate clauses dedupe by normalized text | `policy/compile.py` `_coerce_clause_list` lines 171-184 | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 251-263 |
| API connection error | `policy/compile.py` `_api_exceptions` lines 257-265; `_api_error` lines 250-254 | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 354-363; `test_compile_policy_never_raises_sweep` lines 409-432 |
| API auth error | `policy/compile.py` `_api_exceptions` lines 257-265; `_api_error` lines 250-254 | `test_anthropic_auth_error_falls_back_without_retry` lines 366-380 |
| Key in exception message redacted | `policy/compile.py` `_api_error` lines 250-254 | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 354-363 |
| `load_default_rules` raises | `policy/compile.py` `_safe_default_rules` lines 222-226; `_fallback` lines 229-247 | `test_load_default_rules_raising_still_falls_back` lines 390-394 |
| `ANTHROPIC_MODEL` set and unset | `policy/compile.py` `_call_model` line 117 | `test_call_shape_and_model` lines 122-140; `test_default_model_when_unset` lines 143-146 |

## PRD Section 7 Required Tests

| Required test | Test trace | Code trace |
|---|---|---|
| 1. Sample policy yields expected 40/vacated/offer/retention/source/success | `test_sample_policy_compiles_expected_rules` lines 82-108 | `policy/compile.py` `_validate_payload` lines 151-164; success lines 72-78 |
| 2. 30% variant yields 30 and matching source_text | `test_thirty_percent_variant` lines 111-118 | `policy/compile.py` `_validate_payload` lines 151-164 |
| 3. Call shape, no sampling params, schema, forced tool, model set/unset, prompt up-to-X | `test_call_shape_and_model` lines 122-140; `test_default_model_when_unset` lines 143-146; `test_system_prompt_contains_unmapped_invariant_and_retention_guidance` lines 149-155; `test_system_prompt_contains_reservation_base_guidance` lines 158-164; `test_system_prompt_contains_worked_example_unmapped_sentence` lines 167-170 | `policy/compile.py` `_call_model` lines 115-123; `_emit_rules_tool` lines 135-148; `policy/prompts.py` lines 15-46 |
| 4. Invalid then valid retries once with first error in message | `test_invalid_output_then_valid_retries_once` lines 172-186 | `policy/compile.py` retry lines 59-70; `policy/prompts.py` `build_retry_message` lines 51-58 |
| 5. Invalid then invalid falls back to defaults | `test_invalid_then_invalid_falls_back` lines 189-203 | `policy/compile.py` retry/fallback lines 59-70; `_fallback` lines 224-242 |
| 6. Missing key falls back and client is not called | `test_missing_key_falls_back_without_client` lines 206-210; `offline` fixture lines 64-67 | `policy/compile.py` key guard lines 50-52 |
| 7. Empty/whitespace/non-str/too-long/garbage never raise; guard cases make no API call | `test_guard_inputs_never_raise_or_call_client` lines 213-217; `test_ten_thousand_character_garbage_never_raises` lines 220-228 | `policy/compile.py` `_input_guard` lines 94-101; `_fallback` lines 224-242 |
| 8. Garbage text can return unmapped clauses successfully | `test_large_garbage_can_be_compiled_as_unmapped` lines 241-248 | `policy/compile.py` `_coerce_clause_list` lines 168-185 |
| 9. Unmapped clause preserved, whitespace snapped, unsalvageable invalid | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 251-263; `test_unsalvageable_unmapped_clause_is_invalid` lines 266-278 | `policy/compile.py` `_coerce_clause_list` lines 168-185; `_snap_to_source` lines 188-202 |
| 10. Ambiguity preserves default | `test_ambiguity_preserves_default` lines 281-300 | `policy/compile.py` merge/validate lines 151-165 |
| 11. Omitted fields merge from defaults | `test_omitted_fields_merge_from_defaults` lines 303-310; `test_null_retention_deadline_keeps_default` lines 313-322; `test_non_null_retention_deadline_is_preserved` lines 325-335 | `policy/compile.py` null-drop and merge lines 157-164; `_drop_null_values` lines 218-219 |
| 12. Invalid output forms are rejected | `test_invalid_output_forms_retry_then_fallback` lines 338-351 | `policy/compile.py` `_call_model` lines 124-132; `_validate_payload` lines 151-165 |
| 13. API exceptions fall back once and redact key | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 319-328; `test_anthropic_auth_error_falls_back_without_retry` lines 331-345; `test_generic_exception_never_raises` lines 348-352 | `policy/compile.py` API handling lines 67-70; `_api_error` lines 245-249; outer wrapper lines 37-42 |
| 14. `load_default_rules` raising uses `Rules()` | `test_load_default_rules_raising_still_falls_back` lines 355-359 | `policy/compile.py` `_safe_default_rules` lines 217-221; `_fallback` lines 224-242 |
| 15. Parametrized invariant sweep: `compile_policy` never raises | `test_compile_policy_never_raises_sweep` lines 374-397 | `policy/compile.py` outer wrapper lines 37-42; `_fallback` lines 224-242 |

## Round 2 Prompt Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| Invariant: `unmapped_clauses` contains only sentences stating or implying no `Rules` field; mapped/default-confirming sentences must not be unmapped | `policy/prompts.py` `build_system_prompt` lines 34-38 | `test_system_prompt_contains_unmapped_invariant_and_retention_guidance` lines 149-155 |
| Retention guidance: confirmation wording sets `retention_requires_confirmation=true`; false only for automatic retention without confirmation | `policy/prompts.py` `build_system_prompt` lines 28-29 | `test_system_prompt_contains_unmapped_invariant_and_retention_guidance` lines 149-155 |
| Worked example uses a different policy with one mapped sentence, one genuinely unmapped visiting-hours sentence, and one ambiguous sentence | `policy/prompts.py` `build_system_prompt` lines 41-44 | `test_system_prompt_contains_worked_example_unmapped_sentence` lines 167-170 |
| `SAMPLE_POLICY` remains exact and unchanged | `policy/prompts.py` `SAMPLE_POLICY` lines 7-12 | `test_sample_policy_text_is_exact` lines 173-179 |

## Round 3 Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| Explicit `None` values from model rules mean not stated and are dropped before merging defaults, preserving default `retention_deadline` | `policy/compile.py` `_validate_payload` lines 157-164; `_drop_null_values` lines 218-219 | `test_null_retention_deadline_keeps_default` lines 313-322 |
| Non-null `retention_deadline` emitted by the model is preserved | `policy/compile.py` `_validate_payload` lines 157-164; `_drop_null_values` lines 218-219 | `test_non_null_retention_deadline_is_preserved` lines 325-335 |
| Reservation-base prompt says available-bed sentences from graduating/non-confirming students set `vacated_beds` and must not be unmapped; all/total beds sets `total_beds`; unsure means ambiguous, not unmapped | `policy/prompts.py` `build_system_prompt` lines 24-26 and 37 | `test_system_prompt_contains_reservation_base_guidance` lines 158-164 |

## Round 4 Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| 1. Resolved API key never appears in any `CompileResult.error`: `_fallback` redacts (key replaced with `***`) before truncating to 500 chars, covering the outer catch-all, validation-failure-after-retry and API-error paths | `policy/compile.py` `_fallback` lines 229-247; `_redact` lines 250-253; `_safe_error` lines 256-262; `_api_error` lines 265-266; `compile_policy` catch-all lines 37-42 | `test_key_in_exception_message_never_reaches_error` (OSError and RuntimeError, lines 435-446); `test_key_in_validation_error_never_reaches_error` (invalid `reservation_base` equal to the key, lines 449-463) |
| 2. Offline integration: mocked-compile Rules for the 40% sample and the 30% variant drive `engine.allocate.allocate` over the fixtures at `now=2026-07-20 12:00`; `reserved_for_freshers` differs and equals `floor(pct/100 * available_beds)` (CONTRACT section 9); null `retention_deadline` keeps the default so the 40% run carries `RETENTION_AFTER_DEADLINE`. Skips if `engine.allocate` or `data/hostel.json` is missing | `policy/compile.py` `_validate_payload` null-drop and default merge lines 157-164 | `test_compiled_rules_drive_allocation_forty_vs_thirty` and helper `_allocate_with` lines 466-505 |

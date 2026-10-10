# Policy Compiler Traceability Audit

Final pytest result: `40 passed in 5.88s`

## PRD Section 3 Behaviours

| PRD item | Code trace | Test trace |
|---|---|---|
| 3.1 outer wrapper never raises, fallback is defensive | `policy/compile.py` `compile_policy` lines 37-42; `_fallback` lines 224-242; `_safe_default_rules` lines 217-221 | `test_generic_exception_never_raises` lines 324-328; `test_load_default_rules_raising_still_falls_back` lines 331-335; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.2 input guards for non-str, empty, whitespace, too long | `policy/compile.py` `_compile` lines 45-48; `_input_guard` lines 94-101 | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.3 API key from env or `.env`, no key fallback before client | `policy/compile.py` `_compile` lines 50-52; `_load_api_key` lines 104-112; `_DOTENV_PATH` line 32 | `offline` fixture lines 58-72; `test_missing_key_falls_back_without_client` lines 182-186 |
| 3.4 client factory uses Anthropic with no retries and timeout | `policy/compile.py` `_make_client` lines 81-84 | `offline` fixture monkeypatches factory lines 64-67; `install_fake` lines 75-79 |
| 3.5 model env var default | `policy/compile.py` `_DEFAULT_MODEL` line 33; `_call_model` line 117 | `test_call_shape_and_model` lines 121-139; `test_default_model_when_unset` lines 142-145 |
| 3.6 one call per attempt, max_tokens 1024, forced tool, no sampling params | `policy/compile.py` `_call_model` lines 115-123 | `test_call_shape_and_model` lines 121-139; `test_invalid_output_then_valid_retries_once` lines 148-162 |
| 3.7 emit_rules schema built from `Rules.model_json_schema()` at call time | `policy/compile.py` `_emit_rules_tool` lines 135-148 | `test_call_shape_and_model` lines 133-137 |
| 3.8 read first matching tool_use only; text-only/truncated invalid | `policy/compile.py` `_call_model` lines 124-132 | `test_invalid_output_forms_retry_then_fallback` lines 279-292; `test_compile_policy_never_raises_sweep` lines 350-373 |
| 3.9 validation, default merge, source_text forcing, verbatim snap/dedupe | `policy/compile.py` `_validate_payload` lines 151-164; `_coerce_clause_list` lines 167-184; `_snap_to_source` lines 187-201; `_sentences` lines 204-206; `_tokens` lines 209-210; `_normalise` lines 213-214 | `test_omitted_fields_merge_from_defaults` lines 269-276; `test_unmapped_clause_preserved_and_whitespace_snapped` lines 217-229; `test_unsalvageable_unmapped_clause_is_invalid` lines 232-244; `test_ambiguity_preserves_default` lines 247-266 |
| 3.10 exactly one retry with rejection message, then fallback | `policy/compile.py` `_compile` lines 59-70; `policy/prompts.py` `build_retry_message` lines 44-51 | `test_invalid_output_then_valid_retries_once` lines 148-162; `test_invalid_then_invalid_falls_back` lines 165-179 |
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
| Prompt-injection line remains data in policy tags | `policy/prompts.py` `build_system_prompt` lines 18-20; `build_user_message` lines 40-41 | `test_prompt_injection_remains_inside_policy_tags` lines 338-347 |
| Percentage out of range from model | `policy/compile.py` `_validate_payload` lines 151-164 | `test_invalid_output_then_valid_retries_once` lines 148-162; `test_invalid_output_forms_retry_then_fallback` lines 279-292 |
| Model returns text only | `policy/compile.py` `_call_model` lines 126-132 | `test_invalid_output_forms_retry_then_fallback` lines 279-292; `test_compile_policy_never_raises_sweep` lines 350-373 |
| `stop_reason == "max_tokens"` | `policy/compile.py` `_call_model` lines 124-125 | `test_invalid_output_forms_retry_then_fallback` lines 279-292; `test_compile_policy_never_raises_sweep` lines 350-373 |
| `rules` is a string | `policy/compile.py` `_validate_payload` lines 151-154 | `test_invalid_output_forms_retry_then_fallback` lines 279-292; `test_compile_policy_never_raises_sweep` lines 350-373 |
| Clause altered whitespace or minor paraphrase snaps, unsalvageable invalid | `policy/compile.py` `_coerce_clause_list` lines 167-184; `_snap_to_source` lines 187-201 | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 217-229; `test_unsalvageable_unmapped_clause_is_invalid` lines 232-244 |
| Duplicate clauses dedupe by normalized text | `policy/compile.py` `_coerce_clause_list` lines 170-183 | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 217-229 |
| API connection error | `policy/compile.py` `_api_exceptions` lines 252-260; `_api_error` lines 245-249 | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 295-304; `test_compile_policy_never_raises_sweep` lines 350-373 |
| API auth error | `policy/compile.py` `_api_exceptions` lines 252-260; `_api_error` lines 245-249 | `test_anthropic_auth_error_falls_back_without_retry` lines 307-321 |
| Key in exception message redacted | `policy/compile.py` `_api_error` lines 245-249 | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 295-304 |
| `load_default_rules` raises | `policy/compile.py` `_safe_default_rules` lines 217-221; `_fallback` lines 224-242 | `test_load_default_rules_raising_still_falls_back` lines 331-335 |
| `ANTHROPIC_MODEL` set and unset | `policy/compile.py` `_call_model` line 117 | `test_call_shape_and_model` lines 121-139; `test_default_model_when_unset` lines 142-145 |

## PRD Section 7 Required Tests

| Required test | Test trace | Code trace |
|---|---|---|
| 1. Sample policy yields expected 40/vacated/offer/retention/source/success | `test_sample_policy_compiles_expected_rules` lines 82-108 | `policy/compile.py` `_validate_payload` lines 151-164; success lines 72-78 |
| 2. 30% variant yields 30 and matching source_text | `test_thirty_percent_variant` lines 111-118 | `policy/compile.py` `_validate_payload` lines 151-164 |
| 3. Call shape, no sampling params, schema, forced tool, model set/unset, prompt up-to-X | `test_call_shape_and_model` lines 121-139; `test_default_model_when_unset` lines 142-145 | `policy/compile.py` `_call_model` lines 115-123; `_emit_rules_tool` lines 135-148; `policy/prompts.py` lines 15-37 |
| 4. Invalid then valid retries once with first error in message | `test_invalid_output_then_valid_retries_once` lines 148-162 | `policy/compile.py` retry lines 59-70; `policy/prompts.py` `build_retry_message` lines 44-51 |
| 5. Invalid then invalid falls back to defaults | `test_invalid_then_invalid_falls_back` lines 165-179 | `policy/compile.py` retry/fallback lines 59-70; `_fallback` lines 224-242 |
| 6. Missing key falls back and client is not called | `test_missing_key_falls_back_without_client` lines 182-186; `offline` fixture lines 64-67 | `policy/compile.py` key guard lines 50-52 |
| 7. Empty/whitespace/non-str/too-long/garbage never raise; guard cases make no API call | `test_guard_inputs_never_raise_or_call_client` lines 189-193; `test_ten_thousand_character_garbage_never_raises` lines 196-204 | `policy/compile.py` `_input_guard` lines 94-101; `_fallback` lines 224-242 |
| 8. Garbage text can return unmapped clauses successfully | `test_large_garbage_can_be_compiled_as_unmapped` lines 207-214 | `policy/compile.py` `_coerce_clause_list` lines 167-184 |
| 9. Unmapped clause preserved, whitespace snapped, unsalvageable invalid | `test_unmapped_clause_preserved_and_whitespace_snapped` lines 217-229; `test_unsalvageable_unmapped_clause_is_invalid` lines 232-244 | `policy/compile.py` `_coerce_clause_list` lines 167-184; `_snap_to_source` lines 187-201 |
| 10. Ambiguity preserves default | `test_ambiguity_preserves_default` lines 247-266 | `policy/compile.py` merge/validate lines 151-164 |
| 11. Omitted fields merge from defaults | `test_omitted_fields_merge_from_defaults` lines 269-276 | `policy/compile.py` merge lines 157-163 |
| 12. Invalid output forms are rejected | `test_invalid_output_forms_retry_then_fallback` lines 279-292 | `policy/compile.py` `_call_model` lines 124-132; `_validate_payload` lines 151-164 |
| 13. API exceptions fall back once and redact key | `test_api_exception_falls_back_without_retry_and_redacts_key` lines 295-304; `test_anthropic_auth_error_falls_back_without_retry` lines 307-321; `test_generic_exception_never_raises` lines 324-328 | `policy/compile.py` API handling lines 67-70; `_api_error` lines 245-249; outer wrapper lines 37-42 |
| 14. `load_default_rules` raising uses `Rules()` | `test_load_default_rules_raising_still_falls_back` lines 331-335 | `policy/compile.py` `_safe_default_rules` lines 217-221; `_fallback` lines 224-242 |
| 15. Parametrized invariant sweep: `compile_policy` never raises | `test_compile_policy_never_raises_sweep` lines 350-373 | `policy/compile.py` outer wrapper lines 37-42; `_fallback` lines 224-242 |

# Policy Compiler Traceability Audit

Final pytest result: `71 passed, 1 warning in 4.58s` (the warning is pytest's `PytestCacheWarning: could not create cache path ... WinError 183`, an environment cache-directory message, not a test warning; with `-p no:cacheprovider` the line is `71 passed in 5.37s`)

## PRD Section 3 Behaviours

| PRD item | Code trace | Test trace |
|---|---|---|
| 3.1 outer wrapper never raises, fallback is defensive | `policy/compile.py` `compile_policy`; `_fallback`; `_safe_default_rules` | `test_generic_exception_never_raises`; `test_load_default_rules_raising_still_falls_back`; `test_compile_policy_never_raises_sweep` |
| 3.2 input guards for non-str, empty, whitespace, too long | `policy/compile.py` `_compile`; `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| 3.3 API key from env or `.env`, no key fallback before client | `policy/compile.py` `_compile`; `_load_api_key`; `_DOTENV_PATH` | `offline` fixture; `test_missing_key_falls_back_without_client` |
| 3.4 client factory uses Anthropic with no retries and timeout | `policy/compile.py` `_make_client` | `offline` fixture monkeypatches factory; `install_fake` |
| 3.5 model env var default | `policy/compile.py` `_DEFAULT_MODEL`; `_call_model` | `test_call_shape_and_model`; `test_default_model_when_unset` |
| 3.6 one call per attempt, max_tokens 1024, forced tool, no sampling params | `policy/compile.py` `_call_model` | `test_call_shape_and_model`; `test_invalid_output_then_valid_retries_once` |
| 3.7 emit_rules schema built from `Rules.model_json_schema()` at call time | `policy/compile.py` `_emit_rules_tool` | `test_call_shape_and_model` |
| 3.8 read first matching tool_use only; text-only/truncated invalid | `policy/compile.py` `_call_model` | `test_invalid_output_forms_retry_then_fallback`; `test_compile_policy_never_raises_sweep` |
| 3.9 validation, null-drop/default merge, source_text forcing, verbatim snap/dedupe | `policy/compile.py` `_validate_payload`; `_coerce_clause_list`; `_snap_to_source`; `_sentences`; `_tokens`; `_normalise`; `_drop_null_values` | `test_omitted_fields_merge_from_defaults`; `test_null_retention_deadline_keeps_default`; `test_non_null_retention_deadline_is_preserved`; `test_unmapped_clause_preserved_and_whitespace_snapped`; `test_unsalvageable_unmapped_clause_is_invalid`; `test_ambiguity_preserves_default` |
| 3.10 exactly one retry with rejection message, then fallback | `policy/compile.py` `_compile`; `policy/prompts.py` `build_retry_message` | `test_invalid_output_then_valid_retries_once`; `test_invalid_then_invalid_falls_back` |
| 3.11 API exceptions are not retried and key is redacted | `policy/compile.py` `_compile`; `_api_error`; `_api_exceptions` | `test_api_exception_falls_back_without_retry_and_redacts_key`; `test_anthropic_auth_error_falls_back_without_retry` |
| 3.12 success returns `CompileResult` without fallback/error | `policy/compile.py` `_compile` | `test_sample_policy_compiles_expected_rules`; `test_thirty_percent_variant` |
| 3.13 fallback uses default rules, source_text, empty clause lists, truncated error | `policy/compile.py` `_fallback` | `test_invalid_then_invalid_falls_back`; `test_missing_key_falls_back_without_client`; `test_load_default_rules_raising_still_falls_back` |

## PRD Section 6 Edge Cases

| Edge case | Code trace | Test trace |
|---|---|---|
| Empty string | `policy/compile.py` `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| Whitespace only | `policy/compile.py` `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| `None` | `policy/compile.py` `_input_guard`; `_fallback` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| `bytes` | `policy/compile.py` `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| `int` | `policy/compile.py` `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| 20,001-character text | `policy/compile.py` `_input_guard` | `test_guard_inputs_never_raise_or_call_client`; `test_compile_policy_never_raises_sweep` |
| 10,000 characters of garbage | `policy/compile.py` `_coerce_clause_list` | `test_ten_thousand_character_garbage_never_raises`; `test_compile_policy_never_raises_sweep` |
| Prompt-injection line remains data in policy tags | `policy/prompts.py` `build_system_prompt`; `build_user_message` | `test_prompt_injection_remains_inside_policy_tags` |
| Percentage out of range from model | `policy/compile.py` `_validate_payload` | `test_invalid_output_then_valid_retries_once`; `test_invalid_output_forms_retry_then_fallback` |
| Model returns text only | `policy/compile.py` `_call_model` | `test_invalid_output_forms_retry_then_fallback`; `test_compile_policy_never_raises_sweep` |
| `stop_reason == "max_tokens"` | `policy/compile.py` `_call_model` | `test_invalid_output_forms_retry_then_fallback`; `test_compile_policy_never_raises_sweep` |
| `rules` is a string | `policy/compile.py` `_validate_payload` | `test_invalid_output_forms_retry_then_fallback`; `test_compile_policy_never_raises_sweep` |
| Clause altered whitespace or minor paraphrase snaps, unsalvageable invalid | `policy/compile.py` `_coerce_clause_list`; `_snap_to_source` | `test_unmapped_clause_preserved_and_whitespace_snapped`; `test_unsalvageable_unmapped_clause_is_invalid` |
| Duplicate clauses dedupe by normalized text | `policy/compile.py` `_coerce_clause_list` | `test_unmapped_clause_preserved_and_whitespace_snapped` |
| API connection error | `policy/compile.py` `_api_exceptions`; `_api_error` | `test_api_exception_falls_back_without_retry_and_redacts_key`; `test_compile_policy_never_raises_sweep` |
| API auth error | `policy/compile.py` `_api_exceptions`; `_api_error` | `test_anthropic_auth_error_falls_back_without_retry` |
| Key in exception message redacted | `policy/compile.py` `_api_error` | `test_api_exception_falls_back_without_retry_and_redacts_key` |
| `load_default_rules` raises | `policy/compile.py` `_safe_default_rules`; `_fallback` | `test_load_default_rules_raising_still_falls_back` |
| `ANTHROPIC_MODEL` set and unset | `policy/compile.py` `_call_model` | `test_call_shape_and_model`; `test_default_model_when_unset` |

## PRD Section 7 Required Tests

| Required test | Test trace | Code trace |
|---|---|---|
| 1. Sample policy yields expected 40/vacated/offer/retention/source/success | `test_sample_policy_compiles_expected_rules` | `policy/compile.py` `_validate_payload`; success |
| 2. 30% variant yields 30 and matching source_text | `test_thirty_percent_variant` | `policy/compile.py` `_validate_payload` |
| 3. Call shape, no sampling params, schema, forced tool, model set/unset, prompt up-to-X | `test_call_shape_and_model`; `test_default_model_when_unset`; `test_system_prompt_contains_unmapped_invariant_and_retention_guidance`; `test_system_prompt_contains_reservation_base_guidance`; `test_system_prompt_contains_worked_example_unmapped_sentence` | `policy/compile.py` `_call_model`; `_emit_rules_tool`; `policy/prompts.py` |
| 4. Invalid then valid retries once with first error in message | `test_invalid_output_then_valid_retries_once` | `policy/compile.py` retry; `policy/prompts.py` `build_retry_message` |
| 5. Invalid then invalid falls back to defaults | `test_invalid_then_invalid_falls_back` | `policy/compile.py` retry/fallback; `_fallback` |
| 6. Missing key falls back and client is not called | `test_missing_key_falls_back_without_client`; `offline` fixture | `policy/compile.py` key guard |
| 7. Empty/whitespace/non-str/too-long/garbage never raise; guard cases make no API call | `test_guard_inputs_never_raise_or_call_client`; `test_ten_thousand_character_garbage_never_raises` | `policy/compile.py` `_input_guard`; `_fallback` |
| 8. Garbage text can return unmapped clauses successfully | `test_large_garbage_can_be_compiled_as_unmapped` | `policy/compile.py` `_coerce_clause_list` |
| 9. Unmapped clause preserved, whitespace snapped, unsalvageable invalid | `test_unmapped_clause_preserved_and_whitespace_snapped`; `test_unsalvageable_unmapped_clause_is_invalid` | `policy/compile.py` `_coerce_clause_list`; `_snap_to_source` |
| 10. Ambiguity preserves default | `test_ambiguity_preserves_default` | `policy/compile.py` merge/validate |
| 11. Omitted fields merge from defaults | `test_omitted_fields_merge_from_defaults`; `test_null_retention_deadline_keeps_default`; `test_non_null_retention_deadline_is_preserved` | `policy/compile.py` null-drop and merge; `_drop_null_values` |
| 12. Invalid output forms are rejected | `test_invalid_output_forms_retry_then_fallback` | `policy/compile.py` `_call_model`; `_validate_payload` |
| 13. API exceptions fall back once and redact key | `test_api_exception_falls_back_without_retry_and_redacts_key`; `test_anthropic_auth_error_falls_back_without_retry`; `test_generic_exception_never_raises` | `policy/compile.py` API handling; `_api_error`; outer wrapper |
| 14. `load_default_rules` raising uses `Rules()` | `test_load_default_rules_raising_still_falls_back` | `policy/compile.py` `_safe_default_rules`; `_fallback` |
| 15. Parametrized invariant sweep: `compile_policy` never raises | `test_compile_policy_never_raises_sweep` | `policy/compile.py` outer wrapper; `_fallback` |

## Round 2 Prompt Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| Invariant: `unmapped_clauses` contains only sentences stating or implying no `Rules` field; mapped/default-confirming sentences must not be unmapped | `policy/prompts.py` `build_system_prompt` | `test_system_prompt_contains_unmapped_invariant_and_retention_guidance` |
| Retention guidance: confirmation wording sets `retention_requires_confirmation=true`; false only for automatic retention without confirmation | `policy/prompts.py` `build_system_prompt` | `test_system_prompt_contains_unmapped_invariant_and_retention_guidance` |
| Worked example uses a different policy with one mapped sentence, one genuinely unmapped visiting-hours sentence, and one ambiguous sentence | `policy/prompts.py` `build_system_prompt` | `test_system_prompt_contains_worked_example_unmapped_sentence` |
| `SAMPLE_POLICY` remains exact and unchanged | `policy/prompts.py` `SAMPLE_POLICY` | `test_sample_policy_text_is_exact` |

## Round 3 Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| Explicit `None` values from model rules mean not stated and are dropped before merging defaults, preserving default `retention_deadline` | `policy/compile.py` `_validate_payload`; `_drop_null_values` | `test_null_retention_deadline_keeps_default` |
| Non-null `retention_deadline` emitted by the model is preserved | `policy/compile.py` `_validate_payload`; `_drop_null_values` | `test_non_null_retention_deadline_is_preserved` |
| Reservation-base prompt says available-bed sentences from graduating/non-confirming students set `vacated_beds` and must not be unmapped; all/total beds sets `total_beds`; unsure means ambiguous, not unmapped | `policy/prompts.py` `build_system_prompt` | `test_system_prompt_contains_reservation_base_guidance` |

## Round 4 Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| 1. Resolved API key never appears in any `CompileResult.error`: `_fallback` redacts (key replaced with `***`) before truncating to 500 chars, covering the outer catch-all, validation-failure-after-retry and API-error paths | `policy/compile.py` `_fallback`; `_redact`; `_safe_error`; `_api_error`; `compile_policy` catch-all | `test_key_in_exception_message_never_reaches_error` (OSError and RuntimeError); `test_key_in_validation_error_never_reaches_error` (invalid `reservation_base` equal to the key) |
| 2. Offline integration: mocked-compile Rules for the 40% sample and the 30% variant drive `engine.allocate.allocate` over the fixtures at `now=2026-07-20 12:00`; `reserved_for_freshers` differs and equals `floor(pct/100 * available_beds)` (CONTRACT section 9); null `retention_deadline` keeps the default so the 40% run carries `RETENTION_AFTER_DEADLINE`. Skips if `engine.allocate` or any of `data/hostel.json`, `data/students.json`, `data/default_rules.json` is missing | `policy/compile.py` `_validate_payload` null-drop and default merge | `test_compiled_rules_drive_allocation_forty_vs_thirty` and helper `_allocate_with` |

## Round 5 Fix Traceability

| Requirement | Code trace | Test trace |
|---|---|---|
| A. Timezone-aware `retention_deadline` (`Z` or an offset) becomes a naive datetime with the wall-clock time as written (no zone shift), so `engine.allocate` cannot raise on mixed naive and aware datetimes. Documented in PRD section 3 step 9 | `policy/compile.py` `_validate_payload`, `_naive_deadline` | `test_tz_aware_deadline_becomes_naive_wall_clock` (`Z`, `+01:00`, `-05:30`); `test_naive_deadline_is_untouched`; `test_tz_aware_deadline_runs_through_allocator_without_raising` (runs `engine.allocate.allocate` on the fixtures) |
| A. Prompt tells the model to emit the date-time without a timezone suffix | `policy/prompts.py` `build_system_prompt` (retention_deadline guidance) | `test_system_prompt_forbids_timezone_suffix` |
| B. Every place that formats an exception is safe even when `__str__` raises; the last-resort fallback cannot raise | `policy/compile.py` `compile_policy`, `_exc_text`, `_api_error`, `_fallback` (nested last-resort `CompileResult`) | `test_exception_with_raising_str_still_falls_back` (`BadStrError` via the catch-all, `BadStrOSError` via the API-error path); `test_fallback_survives_default_rules_raising_bad_str_exception` |
| C1. Real `anthropic.APIConnectionError` and `anthropic.AuthenticationError` take the specific `Anthropic API call failed:` path, one `create` call, key redacted | `policy/compile.py` `_api_exceptions`, `_api_error` | `test_real_api_connection_error_uses_api_error_path_and_redacts_key`; `test_real_authentication_error_uses_api_error_path_and_redacts_key` (exceptions built with `httpx2`, the HTTP library the pinned SDK uses) |
| C2. A key straddling the 500-character truncation boundary leaves no prefix longer than 6 characters (redact, then truncate) | `policy/compile.py` `_safe_error`, `_redact` | `test_key_straddling_truncation_boundary_is_redacted_in_api_error`; `..._in_catch_all`; `..._in_validation_error` |
| C3. A key that came from `.env` (no environment variable) is redacted | `policy/compile.py` `_load_api_key`, `_safe_error` | `test_dotenv_sourced_key_is_redacted` (OSError and RuntimeError) |
| C4. A `tool_use` block with a different name is invalid (retry, then fallback); a text block before the real `emit_rules` block is accepted | `policy/compile.py` `_call_model` | `test_tool_use_block_with_other_name_is_invalid`; `test_text_block_before_emit_rules_block_is_accepted` |
| C5. `KeyboardInterrupt` and `SystemExit` propagate out of `compile_policy` | `policy/compile.py` `compile_policy` (`except Exception` only) | `test_keyboard_interrupt_and_system_exit_propagate` |
| C6. The retry message carries the real first validation error, not just the fixed phrase | `policy/prompts.py` `build_retry_message`; `policy/compile.py` `_compile` | `test_invalid_output_then_valid_retries_once` (asserts the field name, Pydantic message and `input_value=140`) |
| D. Integration tests skip (not fail) if `engine.allocate`, `data/hostel.json`, `data/students.json` or `data/default_rules.json` is missing | n/a | `_require_fixtures`, used by `_allocate_with` |

Mutations verified to make at least one test fail (each applied temporarily, then restored): removing `anthropic.APIError` from `_api_exceptions`; truncating before redacting; dropping `_naive_deadline`; formatting exceptions without the `__str__` guard; redacting only the environment key (ignoring `.env`); accepting any `tool_use` block name; catching `BaseException` in `compile_policy`; dropping the real error from the retry message; removing redaction from `_safe_error`; removing the timezone sentence from the prompt.

# Policy compiler traceability audit

Final pytest result: `28 passed in 8.55s`

## PRD section 3 behaviour

| Item | Code | Test coverage |
|---|---|---|
| 1. Outermost wrapper never raises; defensive fallback | `policy/compile.py:37`, `policy/compile.py:224` | `test_generic_exception_never_raises` (`tests/test_policy.py:324`), `test_load_default_rules_raising_still_falls_back` (`tests/test_policy.py:331`) |
| 2. Input guards for non-string, empty/whitespace, >20,000 chars | `policy/compile.py:46`, `policy/compile.py:94` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| 3. API key from env or dotenv; no key falls back before client | `policy/compile.py:50`, `policy/compile.py:104` | `test_missing_key_falls_back_without_client` (`tests/test_policy.py:182`), fixture blocks client by default (`tests/test_policy.py:58`) |
| 4. Client factory uses Anthropic with no retries and timeout | `policy/compile.py:81` | Factory is monkeypatched for offline tests at `tests/test_policy.py:67`; no direct construction assertion in offline suite |
| 5. Model from `ANTHROPIC_MODEL` or default | `policy/compile.py:117` | `test_call_shape_and_model` (`tests/test_policy.py:121`), `test_default_model_when_unset` (`tests/test_policy.py:142`) |
| 6. One `messages.create` per attempt, `max_tokens=1024`, forced tool, no sampling params | `policy/compile.py:115` | `test_call_shape_and_model` (`tests/test_policy.py:121`), `test_invalid_output_then_valid_retries_once` (`tests/test_policy.py:148`) |
| 7. `emit_rules` tool schema built from `Rules.model_json_schema()` | `policy/compile.py:135` | `test_call_shape_and_model` (`tests/test_policy.py:121`) |
| 8. Read only first matching tool-use block; text/truncation invalid | `policy/compile.py:124`, `policy/compile.py:126` | `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| 9. Validate dict payload, default-merge, force `source_text`, verbatim snap/de-dupe | `policy/compile.py:151`, `policy/compile.py:167`, `policy/compile.py:187` | `test_omitted_fields_merge_from_defaults` (`tests/test_policy.py:269`), `test_unmapped_clause_preserved_and_whitespace_snapped` (`tests/test_policy.py:217`), `test_unsalvageable_unmapped_clause_is_invalid` (`tests/test_policy.py:232`) |
| 10. Exactly one retry with rejected-output message; second invalid falls back | `policy/compile.py:61`, `policy/prompts.py:44` | `test_invalid_output_then_valid_retries_once` (`tests/test_policy.py:148`), `test_invalid_then_invalid_falls_back` (`tests/test_policy.py:165`) |
| 11. API/network/auth errors are not retried and key is redacted | `policy/compile.py:67`, `policy/compile.py:69`, `policy/compile.py:245`, `policy/compile.py:252` | `test_api_exception_falls_back_without_retry_and_redacts_key` (`tests/test_policy.py:295`), `test_anthropic_auth_error_falls_back_without_retry` (`tests/test_policy.py:307`) |
| 12. Success returns `CompileResult` with fallback false and no error | `policy/compile.py:72` | `test_sample_policy_compiles_expected_rules` (`tests/test_policy.py:82`) |
| 13. Fallback returns default rules, empty audit lists, source text, truncated error | `policy/compile.py:224` | `test_invalid_then_invalid_falls_back` (`tests/test_policy.py:165`), `test_load_default_rules_raising_still_falls_back` (`tests/test_policy.py:331`) |

## PRD section 6 edge cases

| Edge case | Code | Test coverage |
|---|---|---|
| Empty string | `policy/compile.py:97` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| Whitespace only | `policy/compile.py:97` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| `None` | `policy/compile.py:95` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| `bytes` | `policy/compile.py:95` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| `int` | `policy/compile.py:95` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| 20,001-character text | `policy/compile.py:99` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`) |
| 10,000 characters of garbage | `policy/compile.py:151`, `policy/compile.py:167` | `test_ten_thousand_character_garbage_never_raises` (`tests/test_policy.py:196`) |
| Prompt-injection line remains policy data | `policy/prompts.py:40` | `test_prompt_injection_remains_inside_policy_tags` (`tests/test_policy.py:338`) |
| Percentage out of range from model | `policy/compile.py:159` | `test_invalid_output_then_valid_retries_once` (`tests/test_policy.py:148`), `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| Model returns text only | `policy/compile.py:126` | `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| Model returns `stop_reason="max_tokens"` | `policy/compile.py:124` | `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| Model returns `rules` as a string | `policy/compile.py:152` | `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| Unmapped clause whitespace/paraphrase snap or invalid | `policy/compile.py:167`, `policy/compile.py:187` | `test_unmapped_clause_preserved_and_whitespace_snapped` (`tests/test_policy.py:217`), `test_unsalvageable_unmapped_clause_is_invalid` (`tests/test_policy.py:232`) |
| Duplicate clauses | `policy/compile.py:180` | `test_unmapped_clause_preserved_and_whitespace_snapped` (`tests/test_policy.py:217`) |
| API connection error | `policy/compile.py:69`, `policy/compile.py:252` | `test_api_exception_falls_back_without_retry_and_redacts_key` (`tests/test_policy.py:295`) |
| API auth error | `policy/compile.py:69`, `policy/compile.py:258` | `test_anthropic_auth_error_falls_back_without_retry` (`tests/test_policy.py:307`) |
| Key present in exception is redacted | `policy/compile.py:245` | `test_api_exception_falls_back_without_retry_and_redacts_key` (`tests/test_policy.py:295`) |
| `load_default_rules` raising | `policy/compile.py:217`, `policy/compile.py:224` | `test_load_default_rules_raising_still_falls_back` (`tests/test_policy.py:331`) |
| `ANTHROPIC_MODEL` set and unset | `policy/compile.py:117` | `test_call_shape_and_model` (`tests/test_policy.py:121`), `test_default_model_when_unset` (`tests/test_policy.py:142`) |

## PRD section 7 required tests

| Required test | Code | Test name |
|---|---|---|
| 1. Sample policy yields 40%, `vacated_beds`, offer-letter required, retention confirmation, source text, no fallback | `policy/compile.py:151`, `policy/compile.py:163`, `policy/prompts.py:7` | `test_sample_policy_compiles_expected_rules` (`tests/test_policy.py:82`) |
| 2. 30% variant yields 30 and variant source text | `policy/compile.py:151`, `policy/compile.py:163` | `test_thirty_percent_variant` (`tests/test_policy.py:111`) |
| 3. Call shape, no sampling params, schema, tool choice, model default/env, prompt contains up-to-X rule | `policy/compile.py:115`, `policy/compile.py:135`, `policy/prompts.py:15` | `test_call_shape_and_model` (`tests/test_policy.py:121`), `test_default_model_when_unset` (`tests/test_policy.py:142`) |
| 4. Invalid then valid retries once with first error in message | `policy/compile.py:61`, `policy/prompts.py:44` | `test_invalid_output_then_valid_retries_once` (`tests/test_policy.py:148`) |
| 5. Invalid then invalid falls back | `policy/compile.py:65` | `test_invalid_then_invalid_falls_back` (`tests/test_policy.py:165`) |
| 6. Missing key falls back and client is never called | `policy/compile.py:50`, `policy/compile.py:104` | `test_missing_key_falls_back_without_client` (`tests/test_policy.py:182`) |
| 7. Guard cases and garbage never raise; guard cases avoid API | `policy/compile.py:94`, `policy/compile.py:151` | `test_guard_inputs_never_raise_or_call_client` (`tests/test_policy.py:189`), `test_ten_thousand_character_garbage_never_raises` (`tests/test_policy.py:196`) |
| 8. Garbage text can compile with every sentence unmapped | `policy/compile.py:167` | `test_large_garbage_can_be_compiled_as_unmapped` (`tests/test_policy.py:207`) |
| 9. Unmapped clause exact/snap/invalid behavior | `policy/compile.py:167`, `policy/compile.py:187` | `test_unmapped_clause_preserved_and_whitespace_snapped` (`tests/test_policy.py:217`), `test_unsalvageable_unmapped_clause_is_invalid` (`tests/test_policy.py:232`) |
| 10. Ambiguity listed and default value preserved | `policy/compile.py:155`, `policy/compile.py:157`, `policy/prompts.py:31` | `test_ambiguity_preserves_default` (`tests/test_policy.py:247`) |
| 11. Omitted fields merge from defaults | `policy/compile.py:157` | `test_omitted_fields_merge_from_defaults` (`tests/test_policy.py:269`) |
| 12. Out-of-range pct, text-only response, max_tokens, non-dict rules invalid | `policy/compile.py:124`, `policy/compile.py:126`, `policy/compile.py:152`, `policy/compile.py:159` | `test_invalid_output_forms_retry_then_fallback` (`tests/test_policy.py:279`) |
| 13. API exception and generic exception fallback; no retry; redaction | `policy/compile.py:41`, `policy/compile.py:69`, `policy/compile.py:245` | `test_api_exception_falls_back_without_retry_and_redacts_key` (`tests/test_policy.py:295`), `test_anthropic_auth_error_falls_back_without_retry` (`tests/test_policy.py:307`), `test_generic_exception_never_raises` (`tests/test_policy.py:324`) |
| 14. `load_default_rules` raising falls back to `Rules()` | `policy/compile.py:217`, `policy/compile.py:224` | `test_load_default_rules_raising_still_falls_back` (`tests/test_policy.py:331`) |
| 15. `compile_policy` never raises across covered cases | `policy/compile.py:37`, `policy/compile.py:224` | Parametrized and exception-focused coverage across `tests/test_policy.py:189`, `tests/test_policy.py:196`, `tests/test_policy.py:324`, `tests/test_policy.py:331` |

# SESSION B — Policy compiler

You are SESSION B in a 6-hour hackathon build. Code freeze is 16:00 WAT today. No pushes after.

## Where you are

- There are THREE worktrees (CONTRACT.md section 2a):
  - `../hostel-a`, branch `session-a`: the allocation engine, which also owns `data/`.
  - `../hostel-b`, branch `session-b`: YOU.
  - `../hostel-c`, branch `session-c`: the Streamlit UI.
- Work only in `../hostel-b`. Never edit the other two.
- Read their pushed work with `git fetch origin && git show origin/session-a:<path>`.
- Read CONTRACT.md in full before anything else. If any part of it is wrong, contradictory or missing something you need, STOP and report the exact problem. Do not invent a workaround.

## Ownership

- Write ONLY in `policy/`, `tests/test_policy.py`, and `specs/session-b-prd.md`.
- Import the models from `shared/models.py` and `load_default_rules` from `shared/store.py` exactly as given. Never edit `shared/` or create `data/` files.
- List new packages in `policy/NEEDS.txt`.

## LLM

- Claude only, via the `anthropic` Python SDK.
- Key from env `ANTHROPIC_API_KEY`. Model from env `ANTHROPIC_MODEL`, default `claude-haiku-5-5`.
- No Gemini, OpenAI or other provider. Never hardcode or commit a key; `.env` is gitignored.
- Total real-API spend this session: under $2.

## Step 1 — Spec phase, using the multi-loopr MCP server

Run multi-loopr's full spec pipeline (interrogation, documentation and research layer, PRD) under CONTRACT.md section 2b:

- 25-minute timebox; start building by 12:05.
- Save the PRD to `specs/session-b-prd.md`.
- Research scope: Anthropic Python SDK tool use and `tool_choice`, Pydantic v2 JSON schema generation.
- Hard constraints: CONTRACT.md sections 1, 2, 2a, 3, 4, 6, 9 and 10. Your PRD adds depth (prompt design, retry and error handling, edge cases, extra tests). It must never change a model, signature or fallback rule. Log any disagreement under "## Contract conflicts" and tell the owner.

## Step 2 — Build, through multi-loopr

Dispatch implementation and review rounds through the multi-loopr MCP server with these role pinnings, set explicitly on every run:
- **Spec / PRD author and orchestrator:** Claude (this session).
- **Executor (writes ALL code):** Codex.
- **Reviewer:** Claude. It gets the spec artifacts plus the diff, never this conversation.

This matches multi-loopr's default rule that the reviewer is the provider that did not write the diff. If multi-loopr rejects this pinning, or would let one provider review its own diff, STOP and report it. Do not fall back silently. Pass CONTRACT.md, this file and your PRD as the spec artifacts.

1. `policy/compile.py`: `compile_policy(text: str) -> CompileResult`, implementing section 6 EXACTLY. It must NEVER raise.
   - One `messages.create` call at temperature 0, `max_tokens` ≤ 1024.
   - Structured output forced through the single `emit_rules` tool with `tool_choice`.
   - Validate with `Rules.model_validate`. Retry once with the validation error appended.
   - On any failure, a missing key, or no network: return `load_default_rules()` with `used_fallback=True` and `error` set.
   - "Up to X%" maps to `fresher_reservation_pct = X`.
   - Sentences that fit no field go verbatim into `unmapped_clauses`.
   - Sentences that could be read more than one way keep the default value and go into `ambiguities`.
2. `policy/prompts.py`: the system prompt and the sample-policy constant (exact text in section 6).
3. `tests/test_policy.py`: NO real network calls; mock the Anthropic client. Cover:
   - the sample policy yielding 40%, `vacated_beds`, offer letter required, retention requires confirmation;
   - a 30% variant;
   - invalid output, then retry, then fallback;
   - a missing key falling back;
   - empty text and garbage text never raising;
   - an unmapped clause preserved verbatim.
4. `policy/smoke.py`: one real API call on the sample policy that prints the CompileResult. Run it once and report the output.

If `data/default_rules.json` has not landed yet, `load_default_rules()` already returns `Rules()` defaults. Use that.

Before declaring done, run multi-loopr's evidence check and report its result honestly. Never report a failing check as passing.

## Checkpoints

- **13:00:** items 1-3 pushed, tests green. The owner merges to `main`. Then run `git fetch origin && git rebase origin/main`.
- **14:30:** everything pushed and green. Bug fixes only after this.

## Done means

- `pytest tests/test_policy.py` passes offline.
- The smoke run returns valid Rules with `used_fallback=False`.
- multi-loopr evidence passes.

## Commits

Small and frequent, imperative messages. No AI attribution lines and no co-author trailers. Stage only files in your folders.

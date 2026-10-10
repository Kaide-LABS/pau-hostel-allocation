# SESSION A — Allocation engine

You are SESSION A in a 6-hour hackathon build. Code freeze is 16:00 WAT today. No pushes after.

## Where you are

- There are THREE worktrees (CONTRACT.md section 2a):
  - `../hostel-a`, branch `session-a`: YOU.
  - `../hostel-b`, branch `session-b`: the policy compiler.
  - `../hostel-c`, branch `session-c`: the Streamlit UI.
- Work only in `../hostel-a`. Never edit the other two.
- Read their pushed work with `git fetch origin && git show origin/session-b:<path>`.
- Read CONTRACT.md in full before anything else. If any part of it is wrong, contradictory or missing something you need, STOP and report the exact problem. Do not invent a workaround.

## Ownership

- Write ONLY in `engine/`, `tests/test_engine.py`, `data/`, and `specs/session-a-prd.md`.
- Import the models from `shared/models.py` and the I/O from `shared/store.py` exactly as given. Never edit `shared/`.
- If you need a new package, list it in `engine/NEEDS.txt`.

## Step 0 — BEFORE the spec phase, by 12:00: fixtures

The other two sessions are blocked on these. Build `data/` exactly per CONTRACT.md section 8:

- **`hostel.json`:** 1 invented hostel, 10 rooms, 24 beds total, a mix of single, double and quad.
- **`students.json`:** 32 invented students.
  - 14 RETURNING: 10 confirmed on time, 1 confirmed after the deadline, 3 unconfirmed.
  - 6 TRANSFER.
  - 12 FRESHER: 10 with an offer letter, 2 without.
  - Use mixed `applied_at` times and preferences.
- **`default_rules.json`:** the `Rules` defaults, with `retention_deadline` set.

Invented names only, never real people. Prove every record loads with `load_students()`, `load_hostel()` and `load_default_rules()`. Commit and push to `session-a` immediately.

## Step 1 — Spec phase, using the multi-loopr MCP server

Run multi-loopr's full spec pipeline (interrogation, documentation and research layer, PRD) under CONTRACT.md section 2b:

- 25-minute timebox.
- Save the PRD to `specs/session-a-prd.md`.
- Research scope: Python, Pydantic v2, pytest.
- Hard constraints: CONTRACT.md sections 1, 2, 2a, 3, 4, 5, 8, 9 and 10. Your PRD adds depth (edge cases, internal structure, extra tests). It must never change a model, signature, reason code or algorithm step. Log any disagreement under "## Contract conflicts" and tell the owner.

## Step 2 — Build, through multi-loopr

Dispatch implementation and review rounds through the multi-loopr MCP server with these role pinnings, set explicitly on every run:
- **Spec / PRD author and orchestrator:** Claude (this session).
- **Executor (writes ALL code):** Codex.
- **Reviewer:** Claude. It gets the spec artifacts plus the diff, never this conversation.

This matches multi-loopr's default rule that the reviewer is the provider that did not write the diff. If multi-loopr rejects this pinning, or would let one provider review its own diff, STOP and report it. Do not fall back silently. Pass CONTRACT.md, this file and your PRD as the spec artifacts.

1. `engine/retention.py`: `confirm_retention(student, now)` per section 4.
2. `engine/allocate.py`: `allocate(hostel, students, rules, now) -> AllocationResult`, implementing section 5 steps 1-7 EXACTLY. Deterministic priority logic only. No OR-Tools, no randomness, no LLM.
3. `engine/explain.py`: one template per reason code, worded per section 5. Every number comes from the run. No unfilled placeholders.
4. `tests/test_engine.py`: every section 9 invariant, including the 40%→30% test, which proves `reserved` changes and the outcomes shift.

Before declaring any deliverable done, run multi-loopr's evidence check and report its result honestly. Never report a failing check as passing.

## Checkpoints

- **13:00:** items 1-3 pushed, tests green. The owner merges to `main`. Then run `git fetch origin && git rebase origin/main`.
- **14:30:** everything pushed and green. Bug fixes only after this.

## Done means

- `pytest tests/test_engine.py` passes.
- `allocate()` on the fixtures gives a non-empty waitlist and exercises every reason code the fixtures can produce.
- multi-loopr evidence passes.

## Commits

Small and frequent, imperative messages. No AI attribution lines and no co-author trailers. Stage only files in your folders.

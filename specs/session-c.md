# SESSION C — Streamlit UI

You are SESSION C in a 6-hour hackathon build. Code freeze is 16:00 WAT today. No pushes after.

## Where you are

- There are THREE worktrees (CONTRACT.md section 2a):
  - `../hostel-a`, branch `session-a`: the allocation engine, which also owns `data/`.
  - `../hostel-b`, branch `session-b`: the policy compiler.
  - `../hostel-c`, branch `session-c`: YOU.
- Work only in `../hostel-c`. Never edit the other two.
- Read their pushed work with `git fetch origin && git show origin/session-a:<path>`.
- Read CONTRACT.md in full before anything else. If any part of it is wrong, contradictory or missing something you need, STOP and report the exact problem. Do not invent a workaround.

## Ownership

- Write ONLY in `app/` and `specs/session-c-prd.md`.
- Import the models from `shared/models.py` exactly as given. Never edit `shared/`, `engine/`, `policy/` or `data/`.
- List new packages in `app/NEEDS.txt`: Streamlit plus at most pandas, nothing heavier.

## Step 1 — Spec phase, using the multi-loopr MCP server

Run multi-loopr's full spec pipeline (interrogation, documentation and research layer, PRD) under CONTRACT.md section 2b:

- 25-minute timebox; start building by 12:05.
- Save the PRD to `specs/session-c-prd.md`.
- Research scope: Streamlit layout, tabs, `st.session_state`, metrics, dataframe styling, theming for a projector.
- Hard constraints: CONTRACT.md sections 1, 2, 2a, 3, 4, 7, 9 and 10. Your PRD adds depth (layout, interaction states, error messages, visual polish). It must never change a model, signature or the demo path. Log any disagreement under "## Contract conflicts" and tell the owner.

## Step 2 — Build, through multi-loopr

Dispatch implementation and review rounds through the multi-loopr MCP server with these role pinnings, set explicitly on every run:
- **Spec / PRD author and orchestrator:** Claude (this session).
- **Executor (writes ALL code):** Codex.
- **Reviewer:** Claude. It gets the spec artifacts plus the diff, never this conversation.

This matches multi-loopr's default rule that the reviewer is the provider that did not write the diff. If multi-loopr rejects this pinning, or would let one provider review its own diff, STOP and report it. Do not fall back silently. Pass CONTRACT.md, this file and your PRD as the spec artifacts.

1. `app/mock.py`: hand-built objects matching section 3 EXACTLY:
   - one Hostel and about 12 invented Students across all three categories;
   - a Rules object;
   - a CompileResult with one ambiguity and one unmapped clause;
   - an AllocationResult whose outcomes cover every reason code in section 5;
   - stub `allocate`, `confirm_retention` and `compile_policy` functions with the section 4 signatures, returning this data.
2. `app/main.py`: one Streamlit app with the three tabs from section 7.
   - **Student:**
     - a student selector;
     - "Confirm I'm keeping my room" (RETURNING only), which shows the receipt id and timestamp;
     - "My result", which shows status, room or waitlist position, and the explanation.
   - **Hostel manager:**
     - a policy textarea prefilled with the sample policy;
     - "Compile policy", which shows the Rules as a readable table, with yellow warnings for ambiguities, red for unmapped clauses, and a banner on fallback;
     - "Run allocation", which shows summary metrics plus an outcomes table filterable by status.
   - **Student Affairs audit:** pass/fail lines for "every confirmed on-time retention honoured" and "reserved seats within the policy limit". Cut this tab first if you're late.
3. A single switch at the top of `main.py`: `USE_MOCK = os.getenv("USE_MOCK", "1") == "1"`.
   - True: import from `app/mock.py`.
   - False: import `engine.allocate.allocate`, `engine.retention.confirm_retention`, `policy.compile.compile_policy`, and the `shared.store` loaders.
4. Robustness:
   - Every button survives bad or missing input, using `st.error` or `st.warning`. Never show a stack trace.
   - State lives in `st.session_state`, so results persist across tabs.
5. Projector-ready polish:
   - a clear title and one-line subtitle;
   - large summary metrics;
   - status colours (allocated green, waitlisted amber, rejected red);
   - no real student names anywhere.

Before declaring done, run multi-loopr's evidence check and report its result honestly. Never report a failing check as passing.

## Checkpoints

- **13:00:** items 1-3 pushed and running on mock data.
- **14:30:** after the owner merges A and B into `main`, run `git fetch origin && git rebase origin/main`. Run with `USE_MOCK=0` against the real engine and compiler, fix integration breakage inside `app/` only, and push.
- **15:30:** bug fixes only after this.

## Done means

- `streamlit run app/main.py` works with both `USE_MOCK=1` and `USE_MOCK=0`.
- The demo path in CONTRACT.md section 10 runs end to end without errors.
- multi-loopr evidence passes.

## Commits

Small and frequent, imperative messages. No AI attribution lines and no co-author trailers. Stage only files in your folder.

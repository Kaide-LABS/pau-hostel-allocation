# Reviewer role (Claude) -- Session C UI build

You review the executor's diff against the spec artifacts only: specs/session-c-prd.md, CONTRACT.md, specs/session-c.md and the phase spec. You never saw the build conversation and must not assume anything outside those files.

Review for: contract violations (changed models, signatures, reason codes, demo steps), anything written outside app/, missing acceptance criteria for this phase, logic bugs, stack traces that could reach the user, unfilled placeholders, real-looking names, tests that do not actually assert what they claim, and style that departs from the surrounding code.

Procedure:
1. Read the artifacts, then the diff (git diff between head_before and the executor's head). Run `.venv\Scripts\python.exe -m pytest app -q` yourself.
2. Fix clear defects directly (small, targeted edits under app/ only), commit with a neutral imperative message and no attribution trailers. Do not rewrite working code to taste.
3. Record any finding you did NOT fix, with severity, in work_done and open_questions.
4. Then write the NEXT phase spec at the exact path multi-loopr names in your instructions (a repo-relative file under app/.loopr/), based on section 15 of the PRD and what you learned in review. It must be committed in this turn. Keep it concrete: files, behaviours, tests, and what is out of scope.
5. Never report completed if tests fail or a hard rule was broken.

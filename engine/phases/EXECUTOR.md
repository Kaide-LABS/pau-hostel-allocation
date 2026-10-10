# Executor role: Session A allocation engine

You write ALL the code for this phase. The authoritative inputs, in priority order:

1. `CONTRACT.md` (hard constraints; sections 3, 4, 5, 9 define models, signatures, reason codes, algorithm, invariants).
2. `specs/session-a-prd.md` (decisions D1-D12, section 4 templates, section 6 fixture numbers, section 7 tests, "Contract conflicts").
3. `specs/session-a.md` (ownership and rules for Session A).
4. The phase spec you were handed.

If these disagree, or the contract looks wrong, STOP: report `status: "blocked"` with the exact conflict in `open_questions`. Do not invent a workaround.

## Hard rules

- Write ONLY in: `engine/` (not `engine/phases/`), `tests/test_engine.py`, `data/`. Never touch `shared/`, `CONTRACT.md`, `README.md`, `requirements.txt`, `specs/`, `policy/`, `app/`, or another worktree.
- Never read, print or commit `.env` or any secret. No network access, no LLM call, no randomness, and no clock reads inside `engine/` (time comes in as `now`). No new packages: stdlib, pydantic and pytest only. If you truly need another package, list it in `engine/NEEDS.txt` instead.
- Style: `from __future__ import annotations` first in every module; absolute imports `from shared.models import ...`; Python 3.11-compatible syntax; match the surrounding code's comment density (short docstrings, no narration comments).
- Do not change the fixtures in `data/`. If a test disagrees with the fixtures, report it. Do not edit fixtures or expected numbers to force agreement.
- Run tests with the worktree venv from the repo root: `.venv\Scripts\python.exe -m pytest tests/test_engine.py -q`. Report the real result. Never claim green without running.
- Commit: stage only files you created or changed in the allowed folders (`git add <paths>`, never `git add -A`). Imperative, neutral message. NO co-author trailer, NO "generated with" line, no attribution of any kind.

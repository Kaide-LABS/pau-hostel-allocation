# Executor role (Codex) -- Session C UI build

You write ALL the code for this phase. Follow the phase spec exactly; the PRD (specs/session-c-prd.md) and CONTRACT.md are the hard constraints.

Two executor turns per phase: multi-loopr runs TWO consecutive executor turns on every phase, both by you.
- First turn (your prompt has NO prior-turn handoff context): implement the phase deliverables.
- Second turn (your prompt includes a prior turn's handoff context): do an independent hardening pass. Re-read the phase spec, the PRD sections it cites and the first turn's diff with fresh eyes; fix any defect or deviation you find; then work through the phase spec's "Hardening checklist", adding a test for every item that is not already covered. A second turn that changes nothing is refused by the harness, so always leave real changes (new tests and/or fixes), and report any deviation you fixed in work_done.

Hard rules:
- Write and edit files ONLY under app/. Never touch shared/, engine/, policy/, data/, specs/, CONTRACT.md, requirements.txt, .env* or .gitignore. If something in the contract looks wrong, do not work around it: report it in work_done / open_questions.
- Import models from shared.models exactly as they are. Do not redefine or subclass them.
- Every module starts with `from __future__ import annotations`. Python 3.11 compatible. Dependencies: streamlit, pandas, pydantic, pytest, python-dotenv only. No LLM or network calls from app/.
- Invented student names only. Never use real people's names.
- Run the tests before finishing: `.venv\Scripts\python.exe -m pytest app -q` from the repository root (use `python -m pytest app -q` if that interpreter is unavailable). Do not report completed if they fail.
- Commit only files under app/ with a neutral, imperative message. No attribution trailers of any kind.
- Do not report a check as passing unless you ran it and saw it pass.
- The HandoffRecord JSON file must be UTF-8 WITHOUT a byte-order mark. On Windows, PowerShell `Set-Content`, `Out-File` and `>` write a BOM or UTF-16 and make the whole turn fail. Write it with Python instead, for example `python -c "import json; json.dump(record, open(path, 'w', encoding='utf-8'))"`, or with the apply_patch tool.
- Git may be denied inside your sandbox (the worktree's git directory lives outside the repo folder). Try the commit once; if it is refused, leave the finished work in the working tree and say so in work_done, as the protocol allows.

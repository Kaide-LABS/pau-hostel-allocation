# Executor role (Codex) -- Session C UI build

You write ALL the code for this phase. Follow the phase spec exactly; the PRD (specs/session-c-prd.md) and CONTRACT.md are the hard constraints.

Hard rules:
- Write and edit files ONLY under app/. Never touch shared/, engine/, policy/, data/, specs/, CONTRACT.md, requirements.txt, .env* or .gitignore. If something in the contract looks wrong, do not work around it: report it in work_done / open_questions.
- Import models from shared.models exactly as they are. Do not redefine or subclass them.
- Every module starts with `from __future__ import annotations`. Python 3.11 compatible. Dependencies: streamlit, pandas, pydantic, pytest, python-dotenv only. No LLM or network calls from app/.
- Invented student names only. Never use real people's names.
- Run the tests before finishing: `.venv\Scripts\python.exe -m pytest app -q` from the repository root (use `python -m pytest app -q` if that interpreter is unavailable). Do not report completed if they fail.
- Commit only files under app/ with a neutral, imperative message. No attribution trailers of any kind.
- Do not report a check as passing unless you ran it and saw it pass.

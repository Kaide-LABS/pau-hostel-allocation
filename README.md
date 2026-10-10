# PAU Hostel Allocation Engine

A fair, explainable hostel allocation tool that hostels run and Student Affairs can audit.

Built for the PAU Technology Innovation Club Mini Hackathon, Challenge 03 (Hostel Management).

## The problem

Returning students who confirmed room retention verbally lost their rooms, with no record of the confirmation and no explanation of the decision. Policy changes reached students by word of mouth, so nobody could check the rule applied. Student Affairs' published rule is that hostels reserve up to 40% of available bed spaces for newly admitted students holding a valid Offer of Provisional Admission letter. "Available" means beds vacated by graduating students or by students who did not confirm they are returning. Hostels are privately run and set their own allocation, so the gap is not central control. The gap is a fair, transparent way to apply the rule.

## What it does

- **Digital retention confirmation** with a timestamped receipt.
- **AI policy compiler:** plain-English policy in, validated rules out, with unmapped or ambiguous clauses flagged for the manager.
- **Deterministic allocator** that applies the rules exactly, with the same result every run.
- **Per-student "why" explanation** built from the rules that decided each outcome, plus a Student Affairs audit of retention and the reservation limit.

## How it works

```
policy text --> Claude compiler --> validated Rules --> deterministic allocator --> outcomes + explanations
                                                                ^
                          retention receipts -------------------+
```

**The AI reads the policy; it never allocates.** Claude turns the policy text into structured rules. A deterministic engine applies those rules identically to every student, and every explanation comes from a fixed template, not model-written prose.

- The AI only reads policy. It never decides who gets a room.
- Explanations cannot invent reasons: templates are filled with numbers from the run.
- If the API is unavailable, the compiler falls back to the default rules and says so, so the app works offline.

## Demo walkthrough

1. A returning student confirms they are keeping their room and receives a receipt with a timestamp.
2. The hostel manager compiles the sample policy into a rules table, then runs the allocation to see the summary and the waitlist.
3. Clicking a waitlisted student shows the reason for their position, with real numbers.
4. The manager edits the policy from 40% to 30%, recompiles and reruns. The numbers and explanations change live. This step needs `ANTHROPIC_API_KEY`; without it the compiler keeps the default 40% rules.

   If a returning student confirms live first (as in the demo): at 40%, 11 retained, 13 available, 5 reserved, 6 waitlisted; at 30%, 3 reserved and 7 waitlisted. Without a live confirmation: 10 retained, 14 available, 5 reserved at 40%, and 4 reserved at 30%. Reserved seats are rounded down.
5. The audit tab shows whether every confirmed retention was honoured and whether the reservation stayed within the policy limit.

## How to run

With `USE_MOCK=0` the page shows "Data source: live engine". Without it the app runs on built-in mock data.

Windows (Command Prompt; in PowerShell use `$env:USE_MOCK="0"` instead of `set`):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
set USE_MOCK=0
streamlit run app/main.py
python -m pytest -q
```

macOS/Linux:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export USE_MOCK=0
streamlit run app/main.py
python -m pytest -q
```

Set `ANTHROPIC_API_KEY` in `.env`. It is optional: without it the compiler uses the default rules.

## Project structure

| Folder | Contents |
|---|---|
| `shared/` | Pydantic models and JSON storage helpers |
| `engine/` | The allocator, retention receipts and explanation templates |
| `policy/` | The Claude policy compiler, with validation, one retry and offline fallback |
| `app/` | The Streamlit interface: student, hostel manager and audit tabs |
| `data/` | Invented hostel, student and default rules fixtures |
| `specs/` | Build briefs and PRDs for each part |
| `tests/` | pytest suites for the engine and the compiler |

`CONTRACT.md` defines the shared models, interfaces and algorithm.

## Tech stack and credits

Python 3.11 or newer, Streamlit, Pydantic v2, pandas, python-dotenv, pytest, and the Anthropic Claude API (`claude-haiku-5-5`) for policy compilation. Built with Claude Code and OpenAI Codex, orchestrated with multi-loopr (MIT, github.com/Kaide-LABS/multi-loopr), with Claude reviewing Codex's code. All demo data is invented.

**Cost and deployment.** Each policy compile is a single small Claude API call (claude-haiku-5-5, at most 1024 output tokens). Allocation itself runs locally with no API calls. Storage is local JSON files, with no database. If the API key or network is unavailable, the compiler falls back to the published default rules and the app keeps working. Any hostel or university can adapt it by pasting its own policy text.

## Limitations

- The demo covers a single hostel.
- There is no authentication: anyone can pick any student.
- All fixture data is invented.
- Admission letters are a flag on the student record, not a verified document.
- Retention confirmations are held in the app session for the demo and are not yet saved to disk.
- No login or authentication yet; any user can act as any student in the demo.
- One hostel per run.

## Roadmap

- Instant payment verification.
- Multi-hostel allocation across PAU.
- Admission-letter verification.
- Queueing and reservation timers for booking day.
- Student Affairs audit export and email or WhatsApp notifications.
- Adaptability: other universities paste their own policy.
- Persist confirmations and receipts, and add student and manager login.
- Multiple hostels and a hosted deployment for Student Affairs.

## Team

**Team Hafeedh Balogun**

- Chineye Oforma
- Tayo Abimbola
- Adongo Kelvin
- Hafeedh Balogun

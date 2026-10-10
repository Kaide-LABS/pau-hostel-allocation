# PAU Hostel Allocation Engine

A fair, explainable hostel allocation tool that hostels run and Student Affairs can audit.

## The problem

Returning students who confirmed room retention verbally lost their rooms, with no record of the confirmation and no explanation of the decision. Policy changes reached students by word of mouth, so nobody could check what rule was actually applied. Student Affairs' published rule is that hostels reserve up to 40% of available bed spaces for newly admitted students holding a valid Offer of Provisional Admission letter. "Available" means beds vacated by graduating students or by students who did not confirm they are returning. Hostels are privately run and set their own allocation, so the gap is not central control. The gap is a fair, transparent way to apply the rule, with a record that anyone can inspect.

## What it does

- **Digital retention confirmation** with a timestamped receipt, so a confirmation is a record and not a conversation.
- **AI policy compiler:** plain-English policy in, validated rules out, with unmapped or ambiguous clauses flagged for the manager.
- **Deterministic allocator** that applies the rules exactly and gives the same result for the same inputs.
- **Per-student "why" explanation** built from the rules that decided each outcome, plus a Student Affairs audit of retention and the reservation limit.

## How it works

```
policy text --> Claude compiler --> validated Rules --> deterministic allocator --> outcomes + explanations
                                                                ^
                          retention receipts -------------------+
```

- The AI only reads policy. It never decides who gets a room.
- Explanations come from fixed templates filled with numbers from the run, never from LLM prose, so they cannot invent reasons.
- If the API is unavailable, the compiler falls back to the default rules and says so, so the app works offline.

## Demo walkthrough

1. A returning student confirms they are keeping their room and receives a receipt with a timestamp.
2. The hostel manager compiles the sample policy into a rules table, then runs the allocation to see the summary and the waitlist.
3. Clicking a waitlisted student shows the reason for their position, with the real numbers from the run.
4. The manager edits the policy from 40% to 30%, recompiles and reruns. The numbers and explanations change live: reserved seats fall from 5 to 4. This step needs `ANTHROPIC_API_KEY`; without it the compiler keeps the default 40% rules.
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
| `shared/` | Pydantic models and JSON storage helpers used by every other folder |
| `engine/` | The allocator, retention receipts and explanation templates |
| `policy/` | The Claude policy compiler, with validation, one retry and offline fallback |
| `app/` | The Streamlit interface: student, hostel manager and audit tabs |
| `data/` | Invented hostel, student and default rules fixtures |
| `specs/` | Build briefs and product requirement documents for each part |
| `tests/` | pytest suites for the engine and the compiler |

`CONTRACT.md` defines the models, function interfaces, reason codes and algorithm that every part follows.

## Tech stack and credits

Python 3.11 or newer, Streamlit, Pydantic v2, pytest, and the Anthropic Claude API (`claude-haiku-5-5`) for policy compilation. Built with Claude Code and OpenAI Codex, orchestrated with multi-loopr (MIT, github.com/Kaide-LABS/multi-loopr), with Claude reviewing Codex's code. All demo data is invented.

## Limitations

- The demo covers a single hostel.
- There is no authentication: anyone can pick any student.
- All fixture data is invented.
- Admission letters are a flag on the student record, not a verified document.

## Roadmap

- Instant payment verification.
- Multi-hostel allocation across PAU.
- Admission-letter verification.
- Queueing and reservation timers for booking day.
- Student Affairs audit export and email or WhatsApp notifications.
- Adaptability: other universities paste their own policy.

## Team

**Team Hafeedh Balogun**

- Chineye Oforma
- Tayo Abimbola
- Adongo Kelvin
- Hafeedh Balogun

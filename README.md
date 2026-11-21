***Welcome Manzebu1, here you will be grounded to write codes!***

# Rota Rescue

When a worker calls in sick, or the shop suddenly needs more people, a manager
spends an hour phoning around. **Rota Rescue** does it for them: an AI agent
(the *Shift Filler*) invites the right workers in the app, handles Yes / No /
Partly / no answer, updates the rota and tells the manager. Every worked shift
is saved, so monthly hours and pay come out of one click.

Track 1: Autonomous Agents & Intelligent Systems.

## What it does (nothing more)

1. **Sick call**: a worker taps "Report sick". 1 spot opens. The agent asks
   available workers one at a time until someone says Yes.
2. **Demand surge**: the manager changes "needed" (for example 15 to 20). 5 spots
   open. The agent invites people in waves and stops when full. No overbooking.
3. **Monthly pay**: "Close day" saves the day's shifts. The monthly report shows
   hours x one hourly rate = gross pay, with CSV export. Sick = 0 hours.

"Available" only means "not already on that shift". No skills, licences or other rules.

## Setup (once)

You need Python 3.10 or newer.

```bash
git clone https://github.com/Tika0502/HackathonAI2026.git
cd HackathonAI2026
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

Then copy `.env.example` to a new file called `.env` and paste your OpenAI API key
into it (from https://platform.openai.com/api-keys). **Never commit `.env`**
(it is already in `.gitignore`).

No key? The app still works: it uses the plain-code rules instead of the AI agent.

## Run

```bash
python -m app.seed                       # (re)create demo data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 on the laptop. On a phone on the same Wi-Fi, open
`http://<laptop IP>:8000` (find the IP with `ipconfig` on Windows or
`ipconfig getifaddr en0` on Mac).

## Demo logins

| Name | PIN | Role |
|---|---|---|
| Manager | 0000 | Manager dashboard |
| Eva Horvath | 5555 | Works today's evening shift: use her to **Report sick** |
| Anna Kovacs | 1111 | Few hours this month, so the agent asks her first |
| Bence Nagy | 2222 | 2nd in line |
| Csilla Toth | 3333 | 3rd in line |
| David Szabo | 4444 | 4th in line |
| Everyone else | 1234 | Fake workers. If "Fake workers answer by themselves" is on, they answer automatically |

## Demo script (about 3 minutes)

1. Manager page: set **Answer timeout** to 20 seconds (speeds up the demo).
2. Eva taps **Report sick** on today's evening shift. Manager page shows 1 open spot
   and the agent's reason.
3. Anna's phone gets the offer and taps **No**. The agent moves on by itself to Bence.
4. Bence taps **Partly**, until 21:00. The spot is split; the agent asks Csilla for
   21:00-22:00. Csilla taps **Yes**. Rota updated, manager notified.
5. Manager changes Evening "Needed" from 15 to 20. The agent sends a wave. When all
   are filled, a late Yes gets "Already filled, thanks": no overbooking.
6. **Close day**, open **Monthly report**, **Download CSV**.

Use **Reset demo data** on the manager page before the real pitch.

## How it works

```
phone / laptop browser  (static/*.html, refreshes every 3 s)
        |
FastAPI  (app/main.py)  ── background loop every 1 s:
        |                   timeouts, fake-worker answers, run agent if something happened
        |
engine.py   plain code: open spots, send offers, first-Yes-wins lock, Partly split,
        |               timeouts, close day, monthly report
agent.py    Shift Filler agent (OpenAI Agents SDK): decides WHO to ask and HOW MANY
        |   tools: get_open_needs, list_available_workers, send_offers, give_up
SQLite  (rota.db, created by app/seed.py)
```

The AI decides; plain code does everything that must be exact (locks, timeouts,
booking, pay). If the AI call fails, the plain rules take over, so the demo never breaks.

## Files and who works on what

| File | What it is | Owner |
|---|---|---|
| `app/db.py` | Tables and database helpers | Dev A (backend) |
| `app/engine.py` | "Fill N spots" engine, timeouts, pay report | Dev A |
| `app/agent.py` | The Shift Filler agent (prompt + tools) | Dev A |
| `app/main.py` | API routes and background loop | Dev A |
| `app/seed.py` | Demo data (workers, shifts, past hours) | Dev A |
| `static/login.html` | Login (name + PIN) | Dev B (pages) |
| `static/staff.html` | My shifts, Report sick, Inbox with Yes / No / Partly | Dev B |
| `static/manager.html` | Live rota, needed box, agent log, settings | Dev B |
| `static/report.html` | Monthly hours and pay, CSV | Dev B |
| `static/style.css`, `static/common.js` | Shared look and helpers | Dev B |

Ideas for the day (only if the core demo already works): tune the agent prompt
in `agent.py`, make the pages prettier, add a browser notification sound.

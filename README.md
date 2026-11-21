***Welcome Manzebu1, here you will be grounded to write codes!***

# Rota Rescue

When a worker calls in sick, or the shop suddenly needs more people, a manager
spends an hour phoning around. **Rota Rescue** does it for them: an AI agent
(the *Shift Filler*) invites the right workers in the app, handles Accept / Decline /
no answer, updates the rota and tells the manager. Every worked shift
is saved, so monthly hours and pay come out of one click.

Track 1: Autonomous Agents & Intelligent Systems.

## What it does (nothing more)

1. **Plan next week**: this week is already staffed in the demo data. On the manager
   page, part 1 sets each shift's hours and default number of people; part 2 shows
   those hours per day and lets you change any single day. **Send to agent** starts the
   invitations: one shift per day per person, fewest hours first. The manager page
   panels can be opened, closed and dragged into any order (remembered in the browser).
2. **Sick call / can't come**: a worker taps "Report sick / can't come", or the manager
   opens "Show people" on a shift and taps "Mark sick / absent" (when someone phones in). 1 spot opens. The agent asks one person
   at a time until someone accepts.
3. **Change the number needed** (current week): on the rota, the manager changes
   "Needed" for a shift.
   - **More people**: new spots open and the agent invites people. Nobody loses a shift.
   - **Fewer people**: open spots are cancelled first. If still too many, the most
     recently booked people are removed, and each gets one message in their inbox.
4. **Monthly pay**: "Close day" saves the day's shifts. The monthly report shows
   hours x one hourly rate = gross pay, with CSV export. Sick = 0 hours. Removed
   bookings are not paid.

**Answers and timing.** Workers answer **Accept** or **Decline**. They have
**3 minutes** to answer (5 minutes is an option on the manager page). If there is no
answer after **2 minutes**, the agent also asks the next person. The first person to
accept gets the shift, and the other invitations for that shift are cancelled
automatically ("No longer needed").

**No spam.** A worker never has more than one invitation waiting at a time, is never
asked twice for the same shift, and gets each message only once. The AI is only
called when there is something to do, at most every 3 seconds.

"Available" means: not already working that day, not asked for that shift before,
and no other invitation waiting. No skills, licences or other rules.

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

| Name | PIN | Note |
|---|---|---|
| Manager | 0000 | Manager dashboard |
| Anna Kovacs | 1111 | Fewest hours this month, so the agent asks her first |
| Bence Nagy | 2222 | 2nd in line |
| Csilla Toth | 3333 | 3rd in line |
| David Szabo | 4444 | 4th in line |
| Eva Horvath | 5555 | 5th in line |
| Everyone else | 1234 | Fake workers. If "Fake workers answer by themselves" is on, they answer automatically |

## Demo script (about 3 minutes)

1. Manager page, Demo settings: set **Demo speed** to 10x (3 minutes becomes 18
   seconds, the 2-minute step becomes 12 seconds).
2. **Sick call**: Eva (5555) taps **Report sick / can't come** on today's evening shift.
   The live rota shows 1 open spot and the agent asks Anna first (fewest hours).
3. Anna does nothing: after "2 minutes" the agent also asks Bence. Anna then taps
   **Accept** first: she gets the shift and Bence's invitation is cancelled automatically.
4. **More people**: raise today's Morning "Needed" from 15 to 18. The agent invites in
   waves and stops when full. **Fewer people**: lower it to 14. Open spots are cancelled
   first, then the most recently booked people are removed and each gets one message.
5. **Next week**: in part 1 set the hours and default people, in part 2 raise Saturday,
   press **Send to agent**.
6. **Close day**, open **Monthly report**, **Download CSV**.

Use **Reset demo data** on the manager page before the real pitch, and set Demo speed
back to Real time for real use.

## How it works

```
phone / laptop browser  (static/*.html, refreshes every 3 s)
        |
FastAPI  (app/main.py)  ── background loop every 1 s:
        |                   timeouts, fake-worker answers, run agent if something happened
        |
engine.py   plain code: open spots, send offers, first-Accept-wins lock, cancel other invitations,
        |               2-min escalation, timeouts, close day, monthly report
agent.py    Shift Filler agent (OpenAI Agents SDK): decides WHO to ask and HOW MANY
        |   tools: get_open_needs, list_available_workers, send_offers, give_up
        |   (only called when something can be done, at most every 3 s)
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
| `static/staff.html` | My shifts, Report sick, Inbox with Accept / Decline and messages | Dev B |
| `static/manager.html` | Live rota, needed box, agent log, settings | Dev B |
| `static/report.html` | Monthly hours and pay, CSV | Dev B |
| `static/style.css`, `static/common.js` | Shared look and helpers | Dev B |

Ideas for the day (only if the core demo already works): tune the agent prompt
in `agent.py`, make the pages prettier, add a browser notification sound.

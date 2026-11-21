# Rota Rescue: pitch outline (about 5 minutes)

## 0. Opening question (show of hands)
- "Who has ever had a colleague call in sick an hour before a shift?"
- "Who here was the one phoning around to find a replacement?"

## 1. Problem (30 s)
A shift manager in a supermarket, warehouse or restaurant gets a sick call at 6:30.
They now phone and text people one by one, wait for answers, and often two people say
yes, or nobody does. Same story when the store suddenly needs 10 more people.
**User:** the shift manager of a 30 to 100 person hourly team (and the workers on the rota).

## 2. Evidence (30 s)
- [Fill in: survey or article on time managers spend filling last-minute shifts]
- [Fill in: article on absence / no-show rates in retail or hospitality]
- Ask one real manager before the pitch and quote them (even one line works).

## 3. Cost of the problem (20 s)
- [Fill in: minutes per sick call x sick calls per month = hours lost per manager]
- Unfilled shift = understaffed floor, overtime, lost sales.
- Unfair: the same reliable people get asked every time.

## 4. Solution + live demo (2 min)
"Rota Rescue is an AI shift filler. The manager says what is needed; the agent finds
the people, fairly, and books the first who says yes."
Live demo (see README "Demo script"):
1. Eva reports sick on her phone.
2. The agent asks Anna (fewest hours this month). Log shows who decided and why.
3. No answer in 2 minutes: the agent also asks Bence. Anna accepts first, Bence's
   invitation is cancelled. No double booking.
4. Manager raises the shift from 15 to 18: the agent invites in waves, stops when full.
5. Monthly report: hours x rate, CSV for payroll.

## 5. Why agentic (30 s)
- The agent acts on its own when something happens: decides who to ask, how many, and
  when to give up and alert the manager.
- Tools, not chat: get_open_needs, list_available_workers, send_offers, give_up.
- Guard rails in plain code: locks, timeouts, max invitations. If the AI fails or is
  slow, the rules take over and the log says so. It never stalls.

## 6. Before and after (20 s)
| | Before | After |
|---|---|---|
| Time to fill a sick call | [Fill in: e.g. 30-60 min of calls] | [Fill in: measured in demo] |
| Manager effort | phone + texts | 0 clicks (worker reports sick) |
| Fairness | same people asked | fewest hours asked first |
| Double booking | happens | impossible (first Accept wins) |

Tech: Python, FastAPI, OpenAI Agents SDK, SQLite, mobile web pages (no app to install).

## 7. Market (15 s)
Any business with hourly shift workers: retail, warehouses, hospitality, care homes,
campus cafeterias. [Fill in: number of shift workers in Hungary / EU]

## 8. Team (15 s)
- Tilyekbyerdi Khabai: [role]
- Baitik Orospekov: [role]
- [teammate]: [role]

## Q&A prep
- "What if nobody answers?" The agent gives up and alerts the manager with what is open.
- "What if the AI is wrong or down?" Plain rules finish the job; every decision is logged.
- "Privacy?" Only name, PIN and hours are stored. Real use would add proper login.

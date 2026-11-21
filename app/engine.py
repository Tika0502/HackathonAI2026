"""The "fill N open spots" engine: plain code for everything that must be exact.

- opening spots (7-day plan, sick call, more people needed)
- removing people when fewer are needed
- sending offers (with anti-spam limits)
- answers: first Accept wins (no double booking), the other offers are cancelled
- 2-minute escalation and the answer timeout
- closing a day into shift_records, monthly report

The AI agent (agent.py) only DECIDES who to ask. It calls the functions in
this file to do the actual work.
"""
import math
import random
from datetime import datetime, timedelta

from . import db

# needs_agent_run: set to True whenever something happens. The background loop
# in main.py sees it and runs the agent (at most every few seconds).
# escalated: offers that already passed the 2-minute mark, so the agent is
# woken only once per offer.
state = {"needs_agent_run": False, "escalated": set(), "decider": "Rules"}

ESCALATE_AFTER_MINUTES = 2   # no answer after 2 min -> also ask the next person


def wake_agent():
    state["needs_agent_run"] = True


def now():
    return datetime.now()


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def speed():
    return max(float(db.get_setting("demo_speed") or 1), 1)


def timeout_seconds():
    """How long a worker has to answer (3 or 5 minutes, divided by the demo speed)."""
    return float(db.get_setting("offer_timeout_minutes")) * 60 / speed()


def escalate_seconds():
    """After this long without an answer, the next worker is asked too."""
    return ESCALATE_AFTER_MINUTES * 60 / speed()


def age_seconds(sent_at):
    return (now() - datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S")).total_seconds()


def hours_between(start, end):
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")
    if e <= s:  # shift goes past midnight
        e += timedelta(days=1)
    return round((e - s).total_seconds() / 3600, 2)


def log(text, spot_id=None, kind="agent"):
    db.execute(
        "INSERT INTO decision_log(time, spot_id, kind, text) VALUES (?, ?, ?, ?)",
        (now_str(), spot_id, kind, text),
    )


def message_worker(worker_id, text):
    """A one-time message in the worker's inbox (e.g. "your shift was cancelled")."""
    db.execute("INSERT INTO messages(worker_id, time, text) VALUES (?, ?, ?)", (worker_id, now_str(), text))


def worker_name(worker_id):
    row = db.query_one("SELECT name FROM workers WHERE id = ?", (worker_id,))
    return row["name"] if row else f"worker {worker_id}"


def shift_label(shift_id):
    s = db.query_one("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    return f"{s['date']} {s['name']} {s['start']}-{s['end']}"


# ------------------------------------------------------------ the plan ---

def create_plan(rows):
    """Manager sends a 7-day staffing request to the agent.

    rows = [{date, name, start, end, needed}, ...]
    A new shift is created with `needed` open spots (nobody is booked yet).
    If the same shift (date + name) already exists, its number is changed
    instead. Then the agent is woken up to invite workers.
    """
    created, changed, spots = 0, 0, 0
    for r in rows:
        needed = int(r["needed"])
        if needed <= 0:
            continue
        old = db.query_one("SELECT id FROM shifts WHERE date = ? AND name = ?", (r["date"], r["name"]))
        if old:
            spots += set_needed(old["id"], needed, quiet=True).get("opened", 0)
            changed += 1
            continue
        shift_id = db.execute(
            "INSERT INTO shifts(date, name, start, end, needed) VALUES (?, ?, ?, ?, ?)",
            (r["date"], r["name"], r["start"], r["end"], needed),
        )
        for _ in range(needed):
            db.execute(
                "INSERT INTO open_spots(shift_id, start, end, reason, created_at) VALUES (?, ?, ?, 'plan', ?)",
                (shift_id, r["start"], r["end"], now_str()),
            )
        created += 1
        spots += needed
    if spots:
        dates = sorted({r["date"] for r in rows})
        log(f"Staffing request from the manager: {created + changed} shift(s), {dates[0]} to {dates[-1]}, "
            f"{spots} worker(s) to find. Agent is starting.", kind="manager")
        wake_agent()
    return {"ok": True, "shifts": created + changed, "spots": spots}


# ---------------------------------------------------------------- events ---

def report_sick(worker_id, assignment_id):
    """Worker taps "Report sick": mark them sick and open 1 spot."""
    a = db.query_one(
        "SELECT * FROM assignments WHERE id = ? AND worker_id = ? AND status = 'working'",
        (assignment_id, worker_id),
    )
    if not a:
        return {"ok": False, "error": "Shift not found"}
    db.execute("UPDATE assignments SET status = 'sick' WHERE id = ?", (assignment_id,))
    spot_id = db.execute(
        "INSERT INTO open_spots(shift_id, start, end, reason, created_at) VALUES (?, ?, ?, 'sick', ?)",
        (a["shift_id"], a["start"], a["end"], now_str()),
    )
    log(f"{worker_name(worker_id)} reported sick for {shift_label(a['shift_id'])}. 1 spot opened.",
        spot_id, kind="system")
    wake_agent()
    return {"ok": True, "spot_id": spot_id}


def count_slots(shift_id):
    """(people working, open spots) for a shift."""
    working = db.query_one(
        "SELECT COUNT(*) AS n FROM assignments WHERE shift_id = ? AND status = 'working'", (shift_id,)
    )["n"]
    open_ = db.query_one(
        "SELECT COUNT(*) AS n FROM open_spots WHERE shift_id = ? AND status = 'open'", (shift_id,)
    )["n"]
    return working, open_


def set_needed(shift_id, new_needed, quiet=False):
    """Manager changes the number of people needed for a shift.

    More people: open new spots, the agent invites workers. Nobody loses a shift.
    Fewer people: 1) cancel open spots first (nobody is booked on them),
                  2) if still too many, remove the most recently booked workers
                     and send each of them ONE message.
    """
    shift = db.query_one("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    if not shift:
        return {"ok": False, "error": "Shift not found"}
    new_needed = max(int(new_needed), 0)
    old = shift["needed"]
    db.execute("UPDATE shifts SET needed = ? WHERE id = ?", (new_needed, shift_id))
    working, open_ = count_slots(shift_id)
    missing = new_needed - working - open_
    label = shift_label(shift_id)

    if missing > 0:
        for _ in range(missing):
            db.execute(
                "INSERT INTO open_spots(shift_id, start, end, reason, created_at) VALUES (?, ?, ?, 'surge', ?)",
                (shift_id, shift["start"], shift["end"], now_str()),
            )
        if not quiet:
            log(f"Manager changed {label} from {old} to {new_needed} people. {missing} spot(s) opened.",
                kind="system")
        wake_agent()
        return {"ok": True, "opened": missing, "removed": []}
    if missing == 0:
        return {"ok": True, "opened": 0, "removed": []}

    extra = -missing
    # 1) Cancel open spots first.
    spots = db.query(
        "SELECT id FROM open_spots WHERE shift_id = ? AND status = 'open' ORDER BY id DESC LIMIT ?",
        (shift_id, extra),
    )
    for s in spots:
        db.execute("UPDATE open_spots SET status = 'cancelled' WHERE id = ?", (s["id"],))
    extra -= len(spots)
    conn = db.connect()
    try:
        withdrawn = cancel_offers_if_full(conn, shift_id)
    finally:
        conn.close()

    # 2) Still too many people: remove the most recently booked.
    removed = []
    if extra > 0:
        people = db.query(
            "SELECT id, worker_id FROM assignments WHERE shift_id = ? AND status = 'working' "
            "ORDER BY id DESC LIMIT ?",
            (shift_id, extra),
        )
        for p in people:
            db.execute("UPDATE assignments SET status = 'removed' WHERE id = ?", (p["id"],))
            message_worker(p["worker_id"], f"Your shift {label} is cancelled because fewer people are needed. "
                                           f"Sorry, and thank you!")
            removed.append(worker_name(p["worker_id"]))

    text = f"Manager changed {label} from {old} to {new_needed}."
    if spots:
        text += f" {len(spots)} open spot(s) cancelled."
    if withdrawn:
        text += f" {withdrawn} invitation(s) withdrawn."
    if removed:
        text += f" Removed the most recently booked: {', '.join(removed)} (each got one message)."
    log(text, kind="manager")
    return {"ok": True, "opened": 0, "removed": removed}


# ---------------------------------------------------------------- offers ---

def available_workers(spot_id, strict=True):
    """Who could take this spot, sorted by fewest hours this month (fairness).

    Always excluded: already on that shift (also removed or sick), already asked
    for that shift, already working another shift that day (one shift per day).
    strict=True also excludes anyone with ANY invitation waiting, so nobody gets
    several invitations at once (no spam).
    """
    spot = db.query_one(
        "SELECT sp.*, s.date FROM open_spots sp JOIN shifts s ON s.id = sp.shift_id WHERE sp.id = ?",
        (spot_id,),
    )
    if not spot:
        return []
    month = now().strftime("%Y-%m")
    busy = "AND w.id NOT IN (SELECT worker_id FROM offers WHERE status = 'waiting')" if strict else ""
    return db.query(
        f"""
        SELECT w.id, w.name,
               COALESCE((SELECT SUM(hours) FROM shift_records r
                         WHERE r.worker_id = w.id AND substr(r.date, 1, 7) = ?), 0) AS hours_this_month
        FROM workers w
        WHERE w.is_manager = 0
          AND w.id NOT IN (SELECT worker_id FROM assignments WHERE shift_id = ?)
          AND w.id NOT IN (SELECT o.worker_id FROM offers o JOIN open_spots s ON s.id = o.spot_id
                           WHERE s.shift_id = ?)
          AND w.id NOT IN (SELECT a.worker_id FROM assignments a JOIN shifts s ON s.id = a.shift_id
                           WHERE s.date = ? AND a.status = 'working')
          {busy}
        ORDER BY hours_this_month ASC, w.name ASC
        """,
        (month, spot["shift_id"], spot["shift_id"], spot["date"]),
    )


def waiting_offers(shift_id):
    """Invitations still waiting for an answer on this shift, oldest first."""
    return db.query(
        """SELECT o.* FROM offers o JOIN open_spots s ON s.id = o.spot_id
           WHERE s.shift_id = ? AND o.status = 'waiting' ORDER BY o.id""",
        (shift_id,),
    )


def target_waiting(open_count):
    """How many fresh invitations should be out: 1 for a single spot,
    about 1.3 per spot when many are open (so a few Declines don't slow us down)."""
    return 1 if open_count == 1 else math.ceil(open_count * 1.3)


def open_needs():
    """One "need" per shift with open spots, e.g. "evening shift needs 5 more people".

    fresh_waiting = invitations sent less than 2 minutes ago.
    old_waiting   = invitations older than 2 minutes: still open (first Accept
                    wins), but no longer counted, so the next person gets asked.
    to_send       = how many new invitations the rules allow right now.
    """
    rows = db.query(
        """SELECT shift_id, MIN(id) AS spot_id, COUNT(*) AS open_count, GROUP_CONCAT(DISTINCT reason) AS reasons
           FROM open_spots WHERE status = 'open' GROUP BY shift_id ORDER BY MIN(id)"""
    )
    esc = escalate_seconds()
    for r in rows:
        r["shift"] = shift_label(r["shift_id"])
        offers = waiting_offers(r["shift_id"])
        r["fresh_waiting"] = sum(1 for o in offers if age_seconds(o["sent_at"]) < esc)
        r["old_waiting"] = len(offers) - r["fresh_waiting"]
        r["to_send"] = max(target_waiting(r["open_count"]) - r["fresh_waiting"], 0)
        r["answers_so_far"] = db.query(
            """SELECT w.name, o.status FROM offers o JOIN open_spots s ON s.id = o.spot_id
               JOIN workers w ON w.id = o.worker_id
               WHERE s.shift_id = ? AND o.status NOT IN ('waiting', 'cancelled') ORDER BY o.id""",
            (r["shift_id"],),
        )
        r["available_now"] = len(available_workers(r["spot_id"]))
        r["anyone_left"] = len(available_workers(r["spot_id"], strict=False)) > 0
    return rows


def needs_action():
    """Needs where something can be done right now. If this is empty, the
    agent is not called at all (saves time and API cost)."""
    out = []
    for n in open_needs():
        can_send = n["to_send"] > 0 and n["available_now"] > 0
        must_give_up = not n["anyone_left"] and n["fresh_waiting"] + n["old_waiting"] == 0
        if can_send or must_give_up:
            out.append(n)
    return out


def send_offers(spot_id, worker_ids, reason=""):
    """Invite workers to an open spot. Safety checks are done here, not by the AI:
    only allowed workers, never more than the rules allow (no spam)."""
    spot = db.query_one("SELECT * FROM open_spots WHERE id = ? AND status = 'open'", (spot_id,))
    if not spot:
        return {"ok": False, "error": f"Spot {spot_id} is not open"}
    need = next((n for n in open_needs() if n["shift_id"] == spot["shift_id"]), None)
    limit = need["to_send"] if need else 0
    allowed = {w["id"]: w for w in available_workers(spot_id)}
    wave = (db.query_one(
        "SELECT MAX(o.wave) AS w FROM offers o JOIN open_spots s ON s.id = o.spot_id WHERE s.shift_id = ?",
        (spot["shift_id"],),
    )["w"] or 0) + 1
    sent, skipped = [], []
    for wid in worker_ids:
        wid = int(wid)
        if wid not in allowed or len(sent) >= limit:
            skipped.append(wid)
            continue
        db.execute(
            "INSERT INTO offers(spot_id, worker_id, wave, sent_at) VALUES (?, ?, ?, ?)",
            (spot_id, wid, wave, now_str()),
        )
        sent.append(allowed[wid]["name"])
    if sent:
        who = "AI agent" if state["decider"] == "AI" else "Rules"
        log(f"[{who}] {shift_label(spot['shift_id'])}: asked {', '.join(sent)}. {reason}".strip(), spot_id)
    return {"ok": True, "sent_to": sent, "skipped_ids": skipped, "limit": limit}


def give_up(spot_id, message):
    """Nobody left to ask: mark the shift's open spots unfilled and tell the manager."""
    spot = db.query_one("SELECT * FROM open_spots WHERE id = ?", (spot_id,))
    if not spot:
        return {"ok": False}
    if waiting_offers(spot["shift_id"]):
        return {"ok": False, "error": "Invitations are still waiting. Wait for their answers."}
    db.execute("UPDATE open_spots SET status = 'unfilled' WHERE shift_id = ? AND status = 'open'",
               (spot["shift_id"],))
    who = "AI agent" if state["decider"] == "AI" else "Rules"
    log(f"[{who}] {message}", spot_id, kind="manager")
    return {"ok": True}


def cancel_offers_if_full(conn, shift_id):
    """When a shift has no open spots left, withdraw all its waiting invitations
    (they show "No longer needed" in the worker's inbox). Returns how many."""
    open_count = conn.execute(
        "SELECT COUNT(*) FROM open_spots WHERE shift_id = ? AND status = 'open'", (shift_id,)
    ).fetchone()[0]
    if open_count:
        return 0
    cur = conn.execute(
        """UPDATE offers SET status = 'cancelled', answered_at = ?
           WHERE status = 'waiting' AND spot_id IN (SELECT id FROM open_spots WHERE shift_id = ?)""",
        (now_str(), shift_id),
    )
    return cur.rowcount


def answer_offer(offer_id, worker_id, answer):
    """Worker taps Accept ("yes") or Decline ("no"). Runs in ONE locked
    transaction so two people accepting at the same moment can never both get
    the spot. When the shift is full, all other invitations are cancelled."""
    if answer not in ("yes", "no"):
        return {"ok": False, "message": "Unknown answer"}
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")  # lock the database until COMMIT
        offer = conn.execute(
            "SELECT * FROM offers WHERE id = ? AND worker_id = ?", (offer_id, worker_id)
        ).fetchone()
        if not offer or offer["status"] != "waiting":
            conn.execute("ROLLBACK")
            return {"ok": False, "message": "This offer is closed."}
        spot = conn.execute("SELECT * FROM open_spots WHERE id = ?", (offer["spot_id"],)).fetchone()
        t = now_str()

        if answer == "no":
            conn.execute("UPDATE offers SET status = 'no', answered_at = ? WHERE id = ?", (t, offer_id))
            conn.execute("COMMIT")
            log(f"{worker_name(worker_id)} declined.", spot["id"], kind="system")
            wake_agent()
            return {"ok": True, "message": "Thanks, no problem."}

        # Accept: find a spot on this shift that is still open (first Accept wins).
        target = spot if spot["status"] == "open" else conn.execute(
            "SELECT * FROM open_spots WHERE shift_id = ? AND status = 'open' ORDER BY id LIMIT 1",
            (spot["shift_id"],),
        ).fetchone()
        if not target:
            conn.execute("UPDATE offers SET status = 'too_late', answered_at = ? WHERE id = ?", (t, offer_id))
            conn.execute("COMMIT")
            log(f"{worker_name(worker_id)} accepted, but the shift was already full.", spot["id"], kind="system")
            return {"ok": True, "message": "Already filled, thanks anyway!"}

        busy = conn.execute(
            """SELECT 1 FROM assignments a JOIN shifts s ON s.id = a.shift_id
               WHERE a.worker_id = ? AND a.status = 'working'
                 AND s.date = (SELECT date FROM shifts WHERE id = ?)""",
            (worker_id, target["shift_id"]),
        ).fetchone()
        if busy:
            conn.execute("UPDATE offers SET status = 'no', answered_at = ? WHERE id = ?", (t, offer_id))
            conn.execute("COMMIT")
            wake_agent()
            return {"ok": True, "message": "You already work a shift that day, so we asked someone else."}

        conn.execute(
            "INSERT INTO assignments(shift_id, worker_id, start, end, status, is_replacement) "
            "VALUES (?, ?, ?, ?, 'working', ?)",
            (target["shift_id"], worker_id, target["start"], target["end"], int(target["reason"] == "sick")),
        )
        conn.execute(
            "UPDATE open_spots SET status = 'filled', filled_by = ? WHERE id = ?", (worker_id, target["id"])
        )
        conn.execute("UPDATE offers SET status = 'yes', answered_at = ? WHERE id = ?", (t, offer_id))
        cancelled = cancel_offers_if_full(conn, target["shift_id"])
        conn.execute("COMMIT")
    finally:
        conn.close()

    text = f"{worker_name(worker_id)} accepted. Booked for {shift_label(target['shift_id'])}."
    if count_slots(target["shift_id"])[1] == 0:
        text += " The shift is now full."
        if cancelled:
            text += f" {cancelled} other invitation(s) cancelled automatically."
    log(text, target["id"], kind="manager")
    wake_agent()
    return {"ok": True, "message": "You're booked. Thank you!"}


def process_timeouts():
    """Plain code, not AI:
    - after 2 minutes without an answer, wake the agent once so it asks the next
      person too (the first invitation stays open: whoever accepts first wins);
    - after the full timeout (3 or 5 minutes), the invitation expires."""
    limit, esc = timeout_seconds(), escalate_seconds()
    for o in db.query("SELECT * FROM offers WHERE status = 'waiting'"):
        age = age_seconds(o["sent_at"])
        if age >= limit:
            db.execute("UPDATE offers SET status = 'timeout', answered_at = ? WHERE id = ? AND status = 'waiting'",
                       (now_str(), o["id"]))
            log(f"{worker_name(o['worker_id'])} did not answer in time. Invitation expired.",
                o["spot_id"], kind="system")
            wake_agent()
        elif age >= esc and o["id"] not in state["escalated"]:
            state["escalated"].add(o["id"])
            shift_id = db.query_one("SELECT shift_id FROM open_spots WHERE id = ?", (o["spot_id"],))["shift_id"]
            log(f"No answer from {worker_name(o['worker_id'])} after {ESCALATE_AFTER_MINUTES} min "
                f"({shift_label(shift_id)}). Their invitation stays open; asking the next person too.",
                o["spot_id"], kind="system")
            wake_agent()


def bots_tick():
    """Demo helper: fake workers (not is_demo) answer by themselves, so a big
    plan can be shown without 50 phones. Turn off in settings."""
    if db.get_setting("bots_on") != "1":
        return
    rows = db.query(
        """SELECT o.* FROM offers o JOIN workers w ON w.id = o.worker_id
           WHERE o.status = 'waiting' AND w.is_demo = 0"""
    )
    for o in rows:
        rnd = random.Random(o["id"])          # same decision every time for the same offer
        delay = rnd.uniform(10, 150) / speed()
        choice = rnd.choices(["yes", "no", "silent"], weights=[45, 40, 15])[0]
        if choice != "silent" and age_seconds(o["sent_at"]) >= delay:
            answer_offer(o["id"], o["worker_id"], choice)


# ------------------------------------------------------- plain-code filler ---

def plain_fill():
    """The no-AI version of the Shift Filler. Used when there is no API key,
    when use_ai = 0, or if the AI call fails. Same rules the agent is told."""
    for need in needs_action():
        spot_id = need["spot_id"]
        if need["to_send"] > 0 and need["available_now"] > 0:
            chosen = available_workers(spot_id)[:need["to_send"]]
            reason = "Fewest hours this month first (" + ", ".join(
                f"{c['name']} {c['hours_this_month']:g}h" for c in chosen) + ")."
            send_offers(spot_id, [c["id"] for c in chosen], reason)
        elif not need["anyone_left"]:
            give_up(spot_id, f"Nobody left to ask for {need['shift']}. "
                             f"{need['open_count']} spot(s) still open. Manager, please help.")


# ----------------------------------------------------------- pay records ---

def close_day(date):
    """Turn the day's rota into shift_records (sick = 0 hours). Safe to run twice.
    Removed bookings are not paid."""
    db.execute("DELETE FROM shift_records WHERE date = ?", (date,))
    rows = db.query(
        """SELECT a.*, s.date FROM assignments a JOIN shifts s ON s.id = a.shift_id
           WHERE s.date = ? AND a.status IN ('working', 'sick')""",
        (date,),
    )
    for a in rows:
        sick = a["status"] == "sick"
        db.execute(
            "INSERT INTO shift_records(worker_id, date, start, end, hours, is_replacement, is_sick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (a["worker_id"], date, a["start"], a["end"],
             0 if sick else hours_between(a["start"], a["end"]), a["is_replacement"], int(sick)),
        )
    log(f"Day {date} closed: {len(rows)} shift record(s) saved for pay.", kind="system")
    return {"ok": True, "records": len(rows)}


def monthly_report(month):
    """month = '2026-11'. Hours x one hourly rate = gross pay. No overtime, no tax."""
    rate = float(db.get_setting("hourly_rate"))
    rows = db.query(
        """
        SELECT w.id, w.name,
               COUNT(CASE WHEN r.is_sick = 0 THEN 1 END) AS shifts,
               COUNT(CASE WHEN r.is_sick = 1 THEN 1 END) AS sick_days,
               COUNT(CASE WHEN r.is_replacement = 1 AND r.is_sick = 0 THEN 1 END) AS cover_shifts,
               COALESCE(SUM(r.hours), 0) AS hours
        FROM workers w
        LEFT JOIN shift_records r ON r.worker_id = w.id AND substr(r.date, 1, 7) = ?
        WHERE w.is_manager = 0
        GROUP BY w.id ORDER BY w.name
        """,
        (month,),
    )
    for r in rows:
        r["hours"] = round(r["hours"], 2)
        r["gross_pay"] = round(r["hours"] * rate, 2)
    return {"month": month, "hourly_rate": rate, "currency": db.get_setting("currency"), "rows": rows}

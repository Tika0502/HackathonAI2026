"""The "fill N open spots" engine: plain code for everything that must be exact.

- opening spots (sick call, demand surge)
- sending offers
- answers: first Yes wins (no double booking), Partly splits the spot
- timeouts
- closing a day into shift_records, monthly report

The AI agent (agent.py) only DECIDES who to ask and how many. It calls the
functions in this file to do the actual work.
"""
import math
import random
from datetime import datetime, timedelta

from . import db

# Set to True whenever something happens. The background loop in main.py
# sees it and runs the agent once.
state = {"needs_agent_run": False}


def wake_agent():
    state["needs_agent_run"] = True


def now():
    return datetime.now()


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


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


def worker_name(worker_id):
    row = db.query_one("SELECT name FROM workers WHERE id = ?", (worker_id,))
    return row["name"] if row else f"worker {worker_id}"


def shift_label(shift_id):
    s = db.query_one("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    return f"{s['date']} {s['name']} {s['start']}-{s['end']}"


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
    """How many people the shift has (or is looking for) from its start time.

    A slot = a working assignment or an open spot that starts when the shift starts.
    (If a slot was split by a "Partly" answer, only the first half starts at the
    shift start, so it is still counted once.)
    """
    shift = db.query_one("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    working = db.query_one(
        "SELECT COUNT(*) AS n FROM assignments WHERE shift_id = ? AND status = 'working' AND start = ?",
        (shift_id, shift["start"]),
    )["n"]
    open_ = db.query_one(
        "SELECT COUNT(*) AS n FROM open_spots WHERE shift_id = ? AND status = 'open' AND start = ?",
        (shift_id, shift["start"]),
    )["n"]
    return working, open_


def set_needed(shift_id, new_needed):
    """Manager changes the number needed (demand surge)."""
    shift = db.query_one("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    if not shift:
        return {"ok": False, "error": "Shift not found"}
    new_needed = int(new_needed)
    old = shift["needed"]
    db.execute("UPDATE shifts SET needed = ? WHERE id = ?", (new_needed, shift_id))
    working, open_ = count_slots(shift_id)
    missing = new_needed - working - open_
    if missing > 0:
        for _ in range(missing):
            db.execute(
                "INSERT INTO open_spots(shift_id, start, end, reason, created_at) VALUES (?, ?, ?, 'surge', ?)",
                (shift_id, shift["start"], shift["end"], now_str()),
            )
        log(f"Manager changed {shift_label(shift_id)} from {old} to {new_needed} people. "
            f"{missing} spot(s) opened.", kind="system")
        wake_agent()
    elif missing < 0:
        # Fewer people needed: cancel open surge spots (never remove people already booked).
        extra = -missing
        spots = db.query(
            "SELECT id FROM open_spots WHERE shift_id = ? AND status = 'open' ORDER BY id DESC LIMIT ?",
            (shift_id, extra),
        )
        for s in spots:
            db.execute("UPDATE open_spots SET status = 'cancelled' WHERE id = ?", (s["id"],))
        log(f"Manager changed {shift_label(shift_id)} from {old} to {new_needed}. "
            f"{len(spots)} open spot(s) cancelled.", kind="system")
        close_offers_if_nothing_open(shift_id)
    return {"ok": True, "opened": max(missing, 0)}


# ---------------------------------------------------------------- offers ---

def available_workers(spot_id):
    """Who could take this spot: not already on that shift, not already asked
    for that shift. Sorted by fewest hours this month (fairness)."""
    spot = db.query_one("SELECT * FROM open_spots WHERE id = ?", (spot_id,))
    if not spot:
        return []
    month = now().strftime("%Y-%m")
    return db.query(
        """
        SELECT w.id, w.name,
               COALESCE((SELECT SUM(hours) FROM shift_records r
                         WHERE r.worker_id = w.id AND substr(r.date, 1, 7) = ?), 0) AS hours_this_month
        FROM workers w
        WHERE w.is_manager = 0
          AND w.id NOT IN (SELECT worker_id FROM assignments WHERE shift_id = ?)
          AND w.id NOT IN (SELECT o.worker_id FROM offers o JOIN open_spots s ON s.id = o.spot_id
                           WHERE s.shift_id = ?)
        ORDER BY hours_this_month ASC, w.name ASC
        """,
        (month, spot["shift_id"], spot["shift_id"]),
    )


def open_needs():
    """Open spots grouped by (shift, start, end). Same-time spots are one "need"
    with a count, e.g. "evening shift needs 5 more people"."""
    rows = db.query(
        """
        SELECT s.shift_id, s.start, s.end, MIN(s.id) AS spot_id, COUNT(*) AS open_count,
               GROUP_CONCAT(DISTINCT s.reason) AS reasons
        FROM open_spots s WHERE s.status = 'open'
        GROUP BY s.shift_id, s.start, s.end ORDER BY MIN(s.id)
        """
    )
    for r in rows:
        r["shift"] = shift_label(r["shift_id"])
        r["waiting_offers"] = db.query_one(
            """SELECT COUNT(*) AS n FROM offers o JOIN open_spots s ON s.id = o.spot_id
               WHERE o.status = 'waiting' AND s.shift_id = ? AND s.start = ? AND s.end = ?""",
            (r["shift_id"], r["start"], r["end"]),
        )["n"]
        r["answers_so_far"] = db.query(
            """SELECT w.name, o.status, o.partly_until FROM offers o
               JOIN open_spots s ON s.id = o.spot_id JOIN workers w ON w.id = o.worker_id
               WHERE s.shift_id = ? AND s.start = ? AND s.end = ? AND o.status != 'waiting'
               ORDER BY o.id""",
            (r["shift_id"], r["start"], r["end"]),
        )
        r["available_count"] = len(available_workers(r["spot_id"]))
    return rows


def send_offers(spot_id, worker_ids, reason=""):
    """Invite workers to an open spot. Safety checks are done here, not by the AI."""
    spot = db.query_one("SELECT * FROM open_spots WHERE id = ? AND status = 'open'", (spot_id,))
    if not spot:
        return {"ok": False, "error": f"Spot {spot_id} is not open"}
    allowed = {w["id"]: w for w in available_workers(spot_id)}
    # Hard limit so the agent can never spam everybody at once:
    open_count = db.query_one(
        "SELECT COUNT(*) AS n FROM open_spots WHERE shift_id = ? AND start = ? AND end = ? AND status = 'open'",
        (spot["shift_id"], spot["start"], spot["end"]),
    )["n"]
    max_wave = open_count * 2 + 2
    wave = (db.query_one(
        "SELECT MAX(o.wave) AS w FROM offers o JOIN open_spots s ON s.id = o.spot_id WHERE s.shift_id = ?",
        (spot["shift_id"],),
    )["w"] or 0) + 1
    sent, skipped = [], []
    for wid in worker_ids[:max_wave]:
        wid = int(wid)
        if wid not in allowed:
            skipped.append(wid)
            continue
        db.execute(
            "INSERT INTO offers(spot_id, worker_id, wave, sent_at) VALUES (?, ?, ?, ?)",
            (spot_id, wid, wave, now_str()),
        )
        sent.append(allowed[wid]["name"])
    if sent:
        log(f"Wave {wave}: asked {', '.join(sent)}. {reason}".strip(), spot_id)
    return {"ok": True, "sent_to": sent, "skipped_ids": skipped, "wave": wave}


def give_up(spot_id, message):
    """Nobody left to ask: mark the need unfilled and tell the manager."""
    spot = db.query_one("SELECT * FROM open_spots WHERE id = ?", (spot_id,))
    if not spot:
        return {"ok": False}
    db.execute(
        "UPDATE open_spots SET status = 'unfilled' WHERE shift_id = ? AND start = ? AND end = ? AND status = 'open'",
        (spot["shift_id"], spot["start"], spot["end"]),
    )
    log(message, spot_id, kind="manager")
    return {"ok": True}


def answer_offer(offer_id, worker_id, answer, until=None):
    """Worker taps Yes / No / Partly. Runs in ONE locked transaction so two
    people tapping Yes at the same moment can never both get the spot."""
    if answer not in ("yes", "no", "partly"):
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
            log(f"{worker_name(worker_id)} said No.", spot["id"], kind="system")
            wake_agent()
            return {"ok": True, "message": "Thanks, no problem."}

        # Yes or Partly: find a spot that is still open (first Yes wins).
        target = spot if spot["status"] == "open" else conn.execute(
            """SELECT * FROM open_spots WHERE shift_id = ? AND start = ? AND end = ? AND status = 'open'
               ORDER BY id LIMIT 1""",
            (spot["shift_id"], spot["start"], spot["end"]),
        ).fetchone()
        if not target:
            conn.execute("UPDATE offers SET status = 'too_late', answered_at = ? WHERE id = ?", (t, offer_id))
            conn.execute("COMMIT")
            log(f"{worker_name(worker_id)} said Yes, but the spot was already filled. "
                f"Told them: already filled, thanks.", spot["id"], kind="system")
            return {"ok": True, "message": "Already filled, thanks anyway!"}

        end = target["end"]
        if answer == "partly":
            if not until or not (target["start"] < until < target["end"]):
                conn.execute("ROLLBACK")
                return {"ok": False, "message": f"Pick a time between {target['start']} and {target['end']}."}
            end = until

        conn.execute(
            "INSERT INTO assignments(shift_id, worker_id, start, end, status, is_replacement) "
            "VALUES (?, ?, ?, ?, 'working', 1)",
            (target["shift_id"], worker_id, target["start"], end),
        )
        conn.execute(
            "UPDATE open_spots SET status = 'filled', filled_by = ? WHERE id = ?", (worker_id, target["id"])
        )
        conn.execute(
            "UPDATE offers SET status = ?, partly_until = ?, answered_at = ? WHERE id = ?",
            (answer, until if answer == "partly" else None, t, offer_id),
        )
        new_spot = None
        if answer == "partly":
            cur = conn.execute(
                "INSERT INTO open_spots(shift_id, start, end, reason, created_at) VALUES (?, ?, ?, 'partly', ?)",
                (target["shift_id"], until, target["end"], t),
            )
            new_spot = cur.lastrowid
        conn.execute("COMMIT")
    finally:
        conn.close()

    name = worker_name(worker_id)
    label = shift_label(target["shift_id"])
    if answer == "yes":
        log(f"{name} said Yes. Booked for {label} ({target['start']}-{end}). Rota updated.",
            target["id"], kind="manager")
    else:
        log(f"{name} said Partly: works {target['start']}-{until}. "
            f"New spot opened for {until}-{target['end']}.", target["id"], kind="manager")
    close_offers_if_nothing_open(target["shift_id"])
    wake_agent()
    return {"ok": True, "message": "You're booked. Thank you!", "new_spot": new_spot}


def close_offers_if_nothing_open(shift_id):
    """When a shift has no open spots left, tell the manager it's fully staffed."""
    still_open = db.query_one(
        "SELECT COUNT(*) AS n FROM open_spots WHERE shift_id = ? AND status = 'open'", (shift_id,)
    )["n"]
    if still_open == 0:
        waiting = db.query_one(
            """SELECT COUNT(*) AS n FROM offers o JOIN open_spots s ON s.id = o.spot_id
               WHERE s.shift_id = ? AND o.status = 'waiting'""", (shift_id,)
        )["n"]
        log(f"All spots on {shift_label(shift_id)} are filled."
            + (f" {waiting} invitation(s) still out; late Yes answers will get 'already filled, thanks'."
               if waiting else ""), kind="manager")


def process_timeouts():
    """Offers with no answer after the timeout become 'timeout' (plain code, not AI)."""
    limit = int(db.get_setting("offer_timeout_seconds"))
    cutoff = (now() - timedelta(seconds=limit)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.query("SELECT * FROM offers WHERE status = 'waiting' AND sent_at <= ?", (cutoff,))
    for o in rows:
        db.execute("UPDATE offers SET status = 'timeout', answered_at = ? WHERE id = ? AND status = 'waiting'",
                   (now_str(), o["id"]))
        log(f"{worker_name(o['worker_id'])} did not answer in {limit} s (timeout).", o["spot_id"], kind="system")
    if rows:
        wake_agent()


def bots_tick():
    """Demo helper: fake workers (not is_demo) answer by themselves after a few
    seconds, so a surge can be shown without 50 phones. Turn off in settings."""
    if db.get_setting("bots_on") != "1":
        return
    rows = db.query(
        """SELECT o.* FROM offers o JOIN workers w ON w.id = o.worker_id
           WHERE o.status = 'waiting' AND w.is_demo = 0"""
    )
    for o in rows:
        rnd = random.Random(o["id"])          # same decision every time for the same offer
        delay = rnd.uniform(4, 12)
        choice = rnd.choices(["yes", "no", "silent"], weights=[40, 40, 20])[0]
        sent = datetime.strptime(o["sent_at"], "%Y-%m-%d %H:%M:%S")
        if choice != "silent" and (now() - sent).total_seconds() >= delay:
            answer_offer(o["id"], o["worker_id"], choice)


# ------------------------------------------------------- plain-code filler ---

def plain_fill():
    """The no-AI version of the Shift Filler. Used when there is no API key,
    when use_ai = 0, or if the AI call fails. Same rules the agent is told."""
    for need in open_needs():
        spot_id = need["spot_id"]
        is_sick_like = need["open_count"] == 1
        target_waiting = 1 if is_sick_like else math.ceil(need["open_count"] * 1.3)
        to_send = target_waiting - need["waiting_offers"]
        if to_send <= 0:
            continue
        candidates = available_workers(spot_id)
        if not candidates:
            if need["waiting_offers"] == 0:
                give_up(spot_id, f"Nobody left to ask for {need['shift']} ({need['start']}-{need['end']}). "
                                 f"{need['open_count']} spot(s) still open. Manager, please help.")
            continue
        chosen = candidates[:to_send]
        reason = "Rule: fewest hours this month first (" + ", ".join(
            f"{c['name']} {c['hours_this_month']:g}h" for c in chosen) + ")."
        send_offers(spot_id, [c["id"] for c in chosen], reason)


# ----------------------------------------------------------- pay records ---

def close_day(date):
    """Turn the day's rota into shift_records (sick = 0 hours). Safe to run twice."""
    db.execute("DELETE FROM shift_records WHERE date = ?", (date,))
    rows = db.query(
        """SELECT a.*, s.date FROM assignments a JOIN shifts s ON s.id = a.shift_id WHERE s.date = ?""",
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

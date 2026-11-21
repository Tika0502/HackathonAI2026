"""FastAPI app: JSON API + the HTML pages in /static.

Run:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import asyncio
import csv
import io
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads OPENAI_API_KEY from .env (must run before importing agent)

from fastapi import Cookie, FastAPI, HTTPException, Response  # noqa: E402
from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agent, db, engine  # noqa: E402

STATIC = Path(__file__).resolve().parent.parent / "static"


AGENT_MIN_GAP_SECONDS = 3   # run the agent at most every 3 s; events in between are handled together


async def background_loop():
    """Every second: expire/escalate old offers, let fake workers answer, and run
    the agent if something happened (batched, at most every few seconds)."""
    last_run = 0.0
    loop = asyncio.get_running_loop()
    while True:
        try:
            engine.process_timeouts()
            engine.bots_tick()
            if engine.state["needs_agent_run"] and loop.time() - last_run >= AGENT_MIN_GAP_SECONDS:
                engine.state["needs_agent_run"] = False
                last_run = loop.time()
                await agent.run_filler()
        except Exception as e:
            print("background loop error:", e)
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app):
    if not db.DB_PATH.exists():
        from .seed import seed
        seed()
    db.init_db()
    task = asyncio.create_task(background_loop())
    yield
    task.cancel()


app = FastAPI(title="Rota Rescue", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ------------------------------------------------------------- login ---
# Simple for a hackathon: the cookie holds the worker id. Not secure for real use.

def current_user(worker_id):
    if not worker_id:
        raise HTTPException(401, "Please log in")
    user = db.query_one("SELECT id, name, is_manager FROM workers WHERE id = ?", (worker_id,))
    if not user:
        raise HTTPException(401, "Please log in")
    return user


def require_manager(worker_id):
    user = current_user(worker_id)
    if not user["is_manager"]:
        raise HTTPException(403, "Managers only")
    return user


class Login(BaseModel):
    name: str
    pin: str


@app.get("/api/names")
def names():
    return [r["name"] for r in db.query("SELECT name FROM workers ORDER BY is_manager DESC, is_demo DESC, name")]


@app.post("/api/login")
def login(data: Login, response: Response):
    user = db.query_one("SELECT * FROM workers WHERE name = ? AND pin = ?", (data.name.strip(), data.pin.strip()))
    if not user:
        raise HTTPException(400, "Wrong name or PIN")
    response.set_cookie("worker_id", str(user["id"]), httponly=True, samesite="lax")
    return {"ok": True, "is_manager": bool(user["is_manager"])}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("worker_id")
    return {"ok": True}


@app.get("/api/me")
def me(worker_id: str = Cookie(None)):
    return current_user(worker_id)


# ------------------------------------------------------------- staff ---

@app.get("/api/my-shifts")
def my_shifts(worker_id: str = Cookie(None)):
    user = current_user(worker_id)
    return db.query(
        """SELECT a.id, a.start, a.end, a.status, a.is_replacement, s.date, s.name AS shift_name
           FROM assignments a JOIN shifts s ON s.id = a.shift_id
           WHERE a.worker_id = ? AND s.date >= ? ORDER BY s.date, a.start""",
        (user["id"], date.today().isoformat()),
    )


class Sick(BaseModel):
    assignment_id: int


@app.post("/api/report-sick")
def report_sick(data: Sick, worker_id: str = Cookie(None)):
    user = current_user(worker_id)
    return engine.report_sick(user["id"], data.assignment_id)


@app.get("/api/inbox")
def inbox(worker_id: str = Cookie(None)):
    user = current_user(worker_id)
    rows = db.query(
        """SELECT o.id, o.status, o.sent_at, sp.start, sp.end, s.date, s.name AS shift_name
           FROM offers o JOIN open_spots sp ON sp.id = o.spot_id JOIN shifts s ON s.id = sp.shift_id
           WHERE o.worker_id = ? ORDER BY o.id DESC LIMIT 20""",
        (user["id"],),
    )
    messages = db.query("SELECT id, time, text FROM messages WHERE worker_id = ? ORDER BY id DESC LIMIT 10",
                        (user["id"],))
    return {"timeout_minutes": db.get_setting("offer_timeout_minutes"), "offers": rows, "messages": messages}


class Answer(BaseModel):
    offer_id: int
    answer: str            # yes (Accept) / no (Decline)


@app.post("/api/answer")
def answer(data: Answer, worker_id: str = Cookie(None)):
    user = current_user(worker_id)
    return engine.answer_offer(data.offer_id, user["id"], data.answer)


# ----------------------------------------------------------- manager ---

@app.get("/api/rota")
def rota(day: str | None = None, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    day = day or date.today().isoformat()
    shifts = db.query("SELECT * FROM shifts WHERE date = ? ORDER BY start", (day,))
    for s in shifts:
        s["people"] = db.query(
            """SELECT a.id, w.name, a.start, a.end, a.status, a.is_replacement FROM assignments a
               JOIN workers w ON w.id = a.worker_id WHERE a.shift_id = ? ORDER BY a.status = 'working' DESC, w.name""",
            (s["id"],),
        )
        working, _ = engine.count_slots(s["id"])
        s["working"] = working
        s["open_spots"] = db.query(
            "SELECT id, start, end, reason, status FROM open_spots WHERE shift_id = ? AND status IN ('open','unfilled')",
            (s["id"],),
        )
    days = [r["date"] for r in db.query("SELECT DISTINCT date FROM shifts ORDER BY date")]
    return {"day": day, "days": days, "shifts": shifts}


class PlanRow(BaseModel):
    date: str          # 2026-11-21
    name: str          # Morning
    start: str         # 06:00
    end: str           # 14:00
    needed: int


class Plan(BaseModel):
    rows: list[PlanRow]


@app.post("/api/plan")
def send_plan(data: Plan, worker_id: str = Cookie(None)):
    """The manager's 7-day staffing request. Only now does the agent start inviting workers."""
    require_manager(worker_id)
    if not data.rows:
        raise HTTPException(400, "The plan is empty")
    return engine.create_plan([r.model_dump() for r in data.rows])


class Needed(BaseModel):
    shift_id: int
    needed: int


@app.post("/api/needed")
def change_needed(data: Needed, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    return engine.set_needed(data.shift_id, data.needed)


@app.get("/api/log")
def decision_log(worker_id: str = Cookie(None)):
    require_manager(worker_id)
    return db.query("SELECT * FROM decision_log ORDER BY id DESC LIMIT 80")


@app.get("/api/offers")
def all_offers(worker_id: str = Cookie(None)):
    require_manager(worker_id)
    return db.query(
        """SELECT o.id, w.name, o.wave, o.status, o.sent_at, sp.start, sp.end, s.name AS shift_name, s.date
           FROM offers o JOIN workers w ON w.id = o.worker_id JOIN open_spots sp ON sp.id = o.spot_id
           JOIN shifts s ON s.id = sp.shift_id ORDER BY o.id DESC LIMIT 60"""
    )


@app.get("/api/settings")
def get_settings(worker_id: str = Cookie(None)):
    require_manager(worker_id)
    values = {r["key"]: r["value"] for r in db.query("SELECT * FROM settings")}
    values["ai_ready"] = agent.ai_enabled()
    return values


class Setting(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def save_setting(data: Setting, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    if data.key not in db.DEFAULT_SETTINGS:
        raise HTTPException(400, "Unknown setting")
    if data.key == "offer_timeout_minutes" and data.value not in ("3", "5"):
        raise HTTPException(400, "Timeout must be 3 or 5 minutes")
    db.set_setting(data.key, data.value)
    return {"ok": True}


class Day(BaseModel):
    day: str


@app.post("/api/close-day")
def close_day(data: Day, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    return engine.close_day(data.day)


@app.post("/api/reset")
def reset(worker_id: str = Cookie(None)):
    require_manager(worker_id)
    from .seed import seed
    seed()
    engine.state["escalated"].clear()
    return {"ok": True}


@app.get("/api/report")
def report(month: str | None = None, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    return engine.monthly_report(month or date.today().strftime("%Y-%m"))


@app.get("/api/report.csv")
def report_csv(month: str | None = None, worker_id: str = Cookie(None)):
    require_manager(worker_id)
    data = engine.monthly_report(month or date.today().strftime("%Y-%m"))
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(["Name", "Shifts worked", "Cover shifts", "Sick days", "Hours",
                  f"Hourly rate ({data['currency']})", f"Gross pay ({data['currency']})"])
    for r in data["rows"]:
        out.writerow([r["name"], r["shifts"], r["cover_shifts"], r["sick_days"], r["hours"],
                      data["hourly_rate"], r["gross_pay"]])
    return Response(
        "﻿" + buf.getvalue(),  # ﻿ makes Excel read the accents correctly
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=hours-{data['month']}.csv"},
    )


# ------------------------------------------------------------- pages ---

@app.get("/")
def home():
    return RedirectResponse("/static/login.html")

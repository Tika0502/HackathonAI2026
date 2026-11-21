"""The Shift Filler agent (OpenAI Agents SDK).

It runs once every time something happens (spot opened, someone answered,
an offer timed out). It looks at the open needs, decides who to ask and how
many, and stops. The exact work (locks, timeouts, booking) is done by the
plain code in engine.py.
"""
import json
import os

from agents import Agent, Runner, function_tool

from . import db, engine

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

INSTRUCTIONS = """
You are the Shift Filler for a workplace rota. The manager has sent you a staffing
request: a 7-day schedule of shifts, each with a role (e.g. Cashier, Stock) and a number
of workers. No worker has been contacted before you. Your job: fill every open spot
quickly and fairly by inviting available workers. You run once per event (new request,
someone answered, an invitation timed out), take the next step for ALL open needs, then stop.
You may call tools for several needs at the same time.

Steps:
1. Call get_open_needs. Each need is a group of open spots with the same shift, role and times.
2. For each need, decide how many invitations should be out at the same time:
   - 1 open spot (e.g. a sick call or the rest of a split spot): keep exactly 1 invitation
     waiting. Ask one person at a time.
   - Several open spots (demand surge): keep about open_count x 1.3 invitations waiting
     (rounded up), so a few No answers don't slow us down.
   If waiting_offers is already enough, do nothing for that need.
3. Call list_available_workers for the need's spot_id. It only contains workers with the
   right role who are free that day. The list is already sorted by
   fewest hours this month. Prefer people at the top (fairness), unless the answers so far
   give you a good reason to skip someone.
4. Call send_offers with the chosen worker ids and a SHORT reason the manager will read,
   e.g. "Mon Morning Cashier: asked Anna (8h this month) and Bence (16h), lowest on the list."
5. If nobody is available and no invitations are waiting, call give_up with a short
   message for the manager saying what is still open.

Never invent worker ids. Keep reasons under 25 words. Do not explain at the end; just stop.
"""


@function_tool
def get_open_needs() -> str:
    """List open needs: spot_id, shift, start, end, open_count, waiting_offers,
    available_count and the answers so far."""
    return json.dumps(engine.open_needs())


@function_tool
def list_available_workers(spot_id: int, limit: int = 15) -> str:
    """Workers who can be asked for this spot (not on the shift, not asked yet),
    sorted by fewest hours worked this month."""
    return json.dumps(engine.available_workers(spot_id)[:limit])


@function_tool
def send_offers(spot_id: int, worker_ids: list[int], reason: str) -> str:
    """Invite these workers to the spot. reason = one short sentence for the manager."""
    return json.dumps(engine.send_offers(spot_id, worker_ids, reason))


@function_tool
def give_up(spot_id: int, message: str) -> str:
    """Nobody left to ask. Marks the need unfilled and sends the message to the manager."""
    return json.dumps(engine.give_up(spot_id, message))


shift_filler = Agent(
    name="Shift Filler",
    instructions=INSTRUCTIONS,
    tools=[get_open_needs, list_available_workers, send_offers, give_up],
    model=MODEL,
)


def ai_enabled():
    return db.get_setting("use_ai") == "1" and bool(os.getenv("OPENAI_API_KEY"))


async def run_filler():
    """Called by the background loop in main.py when something happened."""
    if not engine.open_needs():
        return
    if not ai_enabled():
        engine.plain_fill()
        return
    try:
        await Runner.run(shift_filler, "Something changed. Check the open needs and take the next step.",
                         max_turns=40)
    except Exception as e:  # the demo must not break if the AI fails
        engine.log(f"AI agent failed ({type(e).__name__}). Used plain rules instead.", kind="system")
        engine.plain_fill()
